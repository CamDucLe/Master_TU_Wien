import os
from typing import Any
from urllib.parse import urlparse

from pyspark import SparkConf, StorageLevel
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import RegexTokenizer, StopWordsRemover, CountVectorizer, IDF, StringIndexer, ChiSqSelector, Normalizer
from pyspark.ml.classification import LinearSVC, OneVsRest
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.tuning import ParamGridBuilder, TrainValidationSplit


DELIMITER_PATTERN = r"""[\s\d()\[\]{}.!?,;:+=\-_"'`~#@&*%€$§\\/]+"""
MIN_TOKEN_LENGTH = 2
DEFAULT_SPARK_MASTER = "local[*]"
DEFAULT_DRIVER_MEMORY = "4g"
DEFAULT_CV_MIN_DF = 2.0
DEFAULT_CV_VOCAB_SIZE = 50_000
DEFAULT_SAMPLE_FRACTION = 1.0
IS_FULL_GRID_PROFILE = True


def is_remote_path(file_path: str) -> bool:
    """Return True when the path uses a non-local filesystem scheme."""
    scheme = urlparse(file_path).scheme.lower()
    return scheme not in {"", "file"}


def normalize_local_path(file_path: str) -> str:
    """Convert file:// URIs into regular local filesystem paths."""
    parsed_path = urlparse(file_path)
    if parsed_path.scheme.lower() == "file":
        return parsed_path.path

    return file_path


def get_float_env(var_name: str, default_value: float) -> float:
    return float(os.environ.get(var_name, str(default_value)))


def get_int_env(var_name: str, default_value: int) -> int:
    return int(os.environ.get(var_name, str(default_value)))


def build_spark_session() -> SparkSession:
    conf = SparkConf().setAppName("TextClassificationSVM")
    if conf.get("spark.master", None) is None:
        conf = conf.setMaster(os.environ.get("SPARK_MASTER", DEFAULT_SPARK_MASTER))

    conf = conf.set(
        "spark.driver.memory",
        os.environ.get("SPARK_DRIVER_MEMORY", DEFAULT_DRIVER_MEMORY),
    )

    return SparkSession.builder.config(conf=conf).getOrCreate()


def load_stopwords(spark: SparkSession, file_path: str) -> list[str]:
    if is_remote_path(file_path):
        lines = spark.sparkContext.textFile(file_path).collect()
    else:
        local_path = normalize_local_path(file_path)
        with open(local_path, "r", encoding="utf-8") as txt_file:
            lines = txt_file.readlines()

    return [line.strip() for line in lines if line.strip()]


def write_output_lines(spark: SparkSession, file_path: str, lines: list[str]) -> None:
    if is_remote_path(file_path):
        jvm: Any = spark.sparkContext._jvm
        jsc: Any = spark.sparkContext._jsc
        path = jvm.org.apache.hadoop.fs.Path(file_path)
        file_system = path.getFileSystem(jsc.hadoopConfiguration())
        parent = path.getParent()
        if parent is not None:
            file_system.mkdirs(parent)

        writer = jvm.java.io.BufferedWriter(
            jvm.java.io.OutputStreamWriter(
                file_system.create(path, True),
                "UTF-8",
            )
        )
        try:
            for line in lines:
                writer.write(line)
                writer.newLine()
        finally:
            writer.close()
        return

    local_path = normalize_local_path(file_path)
    output_dir = os.path.dirname(local_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(local_path, "w", encoding="utf-8") as output_file:
        for line in lines:
            output_file.write(line + "\n")


def build_param_grid(selector: ChiSqSelector, lsvc: LinearSVC) -> list[dict[Any, Any]]:

    num_top_features = [500, 2000]
    reg_params = [0.1]
    standardization_values = [True]
    max_iter_values = [5]

    if IS_FULL_GRID_PROFILE:
        reg_params = [0.1, 0.01, 0.001]
        standardization_values = [True, False]
        max_iter_values = [2, 5]

    return (
        ParamGridBuilder()
        .addGrid(selector.numTopFeatures, num_top_features)
        .addGrid(lsvc.regParam, reg_params)
        .addGrid(lsvc.standardization, standardization_values)
        .addGrid(lsvc.maxIter, max_iter_values)
        .build()
    )


def main():
    spark = build_spark_session()
    spark.sparkContext.setLogLevel(os.environ.get("SPARK_LOG_LEVEL", "WARN"))

    print("Loading data...")
    reviews_file_path = os.environ.get("REVIEWS_FILE_PATH", "data/reviews_devset.json")
    df = spark.read.json(reviews_file_path).select("reviewText", "category")
    df = df.dropna(subset=["reviewText", "category"])

    sample_fraction = get_float_env("TRAIN_SAMPLE_FRACTION", DEFAULT_SAMPLE_FRACTION)
    if not 0 < sample_fraction <= 1:
        raise ValueError("TRAIN_SAMPLE_FRACTION must be between 0 and 1.")
    if sample_fraction < 1.0:
        df = df.sample(withReplacement=False, fraction=sample_fraction, seed=42)

    # Split into train_val (80%) and test (20%)
    train_val_df, test_df = df.randomSplit([0.8, 0.2], seed=42)
    
    # (Removed the initial persist here because we want to persist the processed text instead)

    stopwords_file_path = os.environ.get("STOPWORDS_FILE_PATH", "data/stopwords.txt")
    stopwords_list = load_stopwords(spark, stopwords_file_path)

    # 1. RegexTokenizer
    tokenizer = RegexTokenizer(
        inputCol="reviewText",
        outputCol="tokens",
        pattern=DELIMITER_PATTERN,
        gaps=True,
        toLowercase=True,
        minTokenLength=MIN_TOKEN_LENGTH,
    )

    # 2. StopWordsRemover
    remover = StopWordsRemover(
        inputCol="tokens",
        outputCol="filtered_tokens",
        stopWords=stopwords_list,
    )

    # 3. CountVectorizer
    count_vectorizer_min_df = get_float_env("COUNT_VECTORIZER_MIN_DF", DEFAULT_CV_MIN_DF)
    count_vectorizer_vocab_size = get_int_env("COUNT_VECTORIZER_VOCAB_SIZE", DEFAULT_CV_VOCAB_SIZE)
    cv = CountVectorizer(
        inputCol="filtered_tokens",
        outputCol="raw_features",
        minDF=count_vectorizer_min_df,
        vocabSize=count_vectorizer_vocab_size,
    )

    # 4. IDF
    idf = IDF(
        inputCol="raw_features",
        outputCol="tfidf_features"
    )

    # 5. StringIndexer for Category
    indexer = StringIndexer(
        inputCol="category",
        outputCol="label",
        handleInvalid="skip",
    )

    # ---------------------------------------------------------
    # PIPELINE OPTIMIZATION: Preprocessing Pipeline (Runs ONCE)
    # ---------------------------------------------------------
    preprocessing_pipeline = Pipeline(stages=[
        tokenizer, remover, cv, idf, indexer
    ])

    print("Fitting preprocessing pipeline...")
    preprocessor_model = preprocessing_pipeline.fit(train_val_df)

    print("Transforming and caching training data...")
    # Transform and persist the heavy text processing
    processed_train_val_df = preprocessor_model.transform(train_val_df)
    processed_train_val_df = processed_train_val_df.persist(StorageLevel.MEMORY_AND_DISK)
    # Force cache materialization
    processed_train_val_df.count()

    # Transform test set (no need to persist unless reusing heavily)
    processed_test_df = preprocessor_model.transform(test_df)

    # 6. ChiSqSelector
    selector = ChiSqSelector(
        featuresCol="tfidf_features",
        labelCol="label",
        outputCol="selected_features"
    )

    # 7. Normalizer (L2 norm)
    normalizer = Normalizer(
        inputCol="selected_features",
        outputCol="features",
        p=2.0
    )

    # 8. Classifier (LinearSVC + OneVsRest)
    lsvc = LinearSVC()
    ovr = OneVsRest(classifier=lsvc, labelCol="label", featuresCol="features")

    # ---------------------------------------------------------
    # PIPELINE OPTIMIZATION: Training Pipeline (Runs in Grid Search)
    # ---------------------------------------------------------
    training_pipeline = Pipeline(stages=[
        selector, normalizer, ovr
    ])

    # Evaluator
    evaluator = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="f1"
    )

    paramGrid = build_param_grid(selector, lsvc)
    tvs_parallelism = get_int_env(
        "TVS_PARALLELISM",
        max(1, min(4, spark.sparkContext.defaultParallelism)),
    )
    category_count = train_val_df.select("category").distinct().count()

    print(
        "Grid search profile:",
        "full" if IS_FULL_GRID_PROFILE else "balanced",
        f"({len(paramGrid)} candidates, {category_count} classes, parallelism={tvs_parallelism})",
    )

    # TrainValidationSplit handles the Train/Validation split internally
    # Pass the smaller training_pipeline here
    tvs = TrainValidationSplit(
        estimator=training_pipeline,
        estimatorParamMaps=paramGrid,
        evaluator=evaluator,
        trainRatio=0.75,
        parallelism=tvs_parallelism,
        seed=42,
    )

    print("Starting Grid Search with TrainValidationSplit...")
    # Fit the grid search on the ALREADY PROCESSED data
    tvs_model = tvs.fit(processed_train_val_df)

    # Evaluate on test set
    print("Evaluating on Test Set...")
    # Make predictions on the ALREADY PROCESSED test data
    predictions = tvs_model.transform(processed_test_df)
    f1_score = evaluator.evaluate(predictions)

    print(f"Test Set F1-Score: {f1_score}")

    # Inspect best model parameters
    best_pipeline = tvs_model.bestModel
    
    # IMPORTANT FIX: In the split pipeline, selector is now at index 0 (not 5)
    best_selector = best_pipeline.stages[0]  # type: ignore
    print(f"Best numTopFeatures: {best_selector.getNumTopFeatures()}")
    
    # IMPORTANT FIX: In the split pipeline, ovr is now at index 2 (not 7)
    best_ovr = best_pipeline.stages[2]  # type: ignore
    # To get the parameters of the underlying LinearSVC model used by OneVsRest
    best_lsvc = best_ovr.getClassifier()
    print(f"Best regParam: {best_lsvc.getRegParam()}")
    print(f"Best standardization: {best_lsvc.getStandardization()}")
    print(f"Best maxIter: {best_lsvc.getMaxIter()}")

    # Output parameters to file to help write the report later
    output_params_file_path = os.environ.get("OUTPUT_PARAMS_FILE_PATH", "output/part3_best_params.txt")
    write_output_lines(
        spark,
        output_params_file_path,
        [
            f"Test F1-Score: {f1_score}",
            f"Best numTopFeatures: {best_selector.getNumTopFeatures()}",
            f"Best regParam: {best_lsvc.getRegParam()}",
            f"Best standardization: {best_lsvc.getStandardization()}",
            f"Best maxIter: {best_lsvc.getMaxIter()}",
        ],
    )

    spark.stop()


if __name__ == "__main__":
    main()
