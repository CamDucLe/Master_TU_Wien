import os
from typing import Any
from urllib.parse import urlparse

from pyspark import SparkConf
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import RegexTokenizer, StopWordsRemover, CountVectorizer, IDF, StringIndexer, ChiSqSelector


# Same pattern as in Part 1
DELIMITER_PATTERN = r"""[\s\d()\[\]{}.!?,;:+=\-_"'`~#@&*%€$§\\/]+"""
DEFAULT_SPARK_MASTER = "local[*]"


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


def build_spark_session() -> SparkSession:
    conf = SparkConf().setAppName("PipelineDataFrames")
    if conf.get("spark.master", None) is None:
        conf = conf.setMaster(os.environ.get("SPARK_MASTER", DEFAULT_SPARK_MASTER))

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


def main():
    spark = build_spark_session()

    spark.sparkContext.setLogLevel(os.environ.get("SPARK_LOG_LEVEL", "WARN"))

    # Load data
    reviews_file_path = os.environ.get("REVIEWS_FILE_PATH", "data/reviews_devset.json")
    df = spark.read.json(reviews_file_path)
    # Make sure we only have rows with reviewText and category
    df = df.dropna(subset=["reviewText", "category"])

    # Load stopwords
    stopwords_file_path = os.environ.get("STOPWORDS_FILE_PATH", "data/stopwords.txt")
    stopwords_list = load_stopwords(spark, stopwords_file_path)

    # RegexTokenizer to split reviewText into tokens
    tokenizer = RegexTokenizer(
        inputCol="reviewText",
        outputCol="tokens",
        pattern=DELIMITER_PATTERN,
        gaps=True,
        toLowercase=True
    )

    remover = StopWordsRemover(
        inputCol="tokens",
        outputCol="filtered_tokens",
        stopWords=stopwords_list
    )

    # Use CountVectorizer to map tokens to indices and compute Term Frequency
    cv = CountVectorizer(
        inputCol="filtered_tokens",
        outputCol="raw_features"
    )

    # Compute TF-IDF
    idf = IDF(
        inputCol="raw_features",
        outputCol="features"
    )

    # Label indexer for category
    indexer = StringIndexer(
        inputCol="category",
        outputCol="label"
    )

    # Chi-Square selector for 2000 features
    selector = ChiSqSelector(
        numTopFeatures=2000,
        featuresCol="features",
        labelCol="label",
        outputCol="selected_features"
    )

    # Pipeline to chain all transformations together
    pipeline = Pipeline(stages=[tokenizer, remover, cv, idf, indexer, selector])

    # Fit the pipeline
    model = pipeline.fit(df)

    # Extract the vocabulary and selected features
    # cv_model is at index 2
    cv_model = model.stages[2]
    vocab = cv_model.vocabulary  # type: ignore
    
    # selector_model is at index 5
    selector_model = model.stages[5]
    selected_indices = selector_model.selectedFeatures  # type: ignore

    # Map selected feature indices back to terms
    selected_terms = [vocab[i] for i in selected_indices]

    # We can write the terms to output_ds.txt
    # Sorting them alphabetically just to have a deterministic output
    selected_terms.sort()
    output_file_path = os.environ.get("OUTPUT_FILE_PATH", "output/output_ds.txt")
    write_output_lines(spark, output_file_path, selected_terms)

    # Stop the Spark session
    spark.stop()


if __name__ == "__main__":
    main()
