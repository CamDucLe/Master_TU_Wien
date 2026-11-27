import sys
import json
import re
from pyspark import SparkContext, SparkConf

# Configuration
DELIMITER_PATTERN = r"""[\s\d()\[\]{}.!?,;:+=\-_"'`~#@&*%€$§\\/]+"""
MIN_TOKEN_LENGTH = 2
TOP_K_TERMS = 75

def load_stopwords(file_path):
    with open(file_path, 'r') as f:
        return {line.strip() for line in f if line.strip()}

def preprocess_text(text, stopwords):
    lower_text = text.lower()
    tokens = re.split(DELIMITER_PATTERN, lower_text)
    unique_terms = {
        token for token in tokens
        if len(token) >= MIN_TOKEN_LENGTH and token not in stopwords
    }
    return unique_terms

def main():
    conf = SparkConf().setAppName("ChiSquareRDD").setMaster("local[*]")
    sc = SparkContext(conf=conf)
    sc.setLogLevel("WARN")

    # Load stopwords
    stopwords = load_stopwords("stopwords.txt")
    stopwords_bc = sc.broadcast(stopwords)

    # Read dataset
    raw_rdd = sc.textFile("reviews_devset.json")

    # Map to (category, unique_terms)
    def parse_review(line):
        try:
            review = json.loads(line)
            category = review["category"]
            text = review["reviewText"]
            terms = preprocess_text(text, stopwords_bc.value)
            return (category, terms)
        except Exception:
            return None

    parsed_rdd = raw_rdd.map(parse_review).filter(lambda x: x is not None)
    
    # total_docs: total reviews
    # category_counts: total reviews per category
    category_counts = parsed_rdd.map(lambda x: (x[0], 1)).reduceByKey(lambda a, b: a + b).collectAsMap()
    total_docs = sum(category_counts.values())

    category_counts_bc = sc.broadcast(category_counts)
    total_docs_bc = sc.broadcast(total_docs)
    
    # term_category_rdd: ((term, category), 1)
    term_category_rdd = parsed_rdd.flatMap(lambda x: [((term, x[0]), 1) for term in x[1]])
    
    # term_category_counts_rdd: ((term, category), term_in_category)
    term_category_counts_rdd = term_category_rdd.reduceByKey(lambda a, b: a + b)
    
    # term_total_docs_rdd: (term, total_term_docs)
    term_counts_mapped_rdd = term_category_counts_rdd.map(lambda x: (x[0][0], x[1]))
    term_total_docs_rdd = term_counts_mapped_rdd.reduceByKey(lambda a, b: a + b)
    
    # category_counts_by_term_rdd: (term, (category, term_in_category))
    category_counts_by_term_rdd = term_category_counts_rdd.map(lambda x: (x[0][0], (x[0][1], x[1])))
    
    # joined_rdd: (term, ((category, term_in_category), total_term_docs))
    joined_rdd = category_counts_by_term_rdd.join(term_total_docs_rdd)
    
    def compute_chi_square(record):
        term, ((category, term_in_category), total_term_docs) = record
        total_docs_val = total_docs_bc.value
        total_category_docs = category_counts_bc.value[category]
        
        term_in_other_categories = total_term_docs - term_in_category
        category_without_term = total_category_docs - term_in_category
        neither_term_nor_category = total_docs_val - (term_in_category + term_in_other_categories + category_without_term)
        
        # Avoid division by zero
        denominator = (term_in_category + term_in_other_categories) * \
                      (category_without_term + neither_term_nor_category) * \
                      (term_in_category + category_without_term) * \
                      (term_in_other_categories + neither_term_nor_category)
        chi_sq = 0.0
        if denominator != 0:
            numerator = (term_in_category * neither_term_nor_category - term_in_other_categories * category_without_term) ** 2 * total_docs_val
            chi_sq = numerator / denominator
            
        return (category, (term, chi_sq))

    chi_sq_rdd = joined_rdd.map(compute_chi_square)
    
    def get_top_k(iterable):
        sorted_items = sorted(iterable, key=lambda x: (-x[1], x[0]))
        return sorted_items[:TOP_K_TERMS]

    top_terms_rdd = chi_sq_rdd.groupByKey().mapValues(get_top_k)
    
    def format_output(record):
        category, terms = record
        terms_str = " ".join([f"{term}:{score:.4f}" for term, score in terms])
        return f"{category} {terms_str}"
        
    formatted_rdd = top_terms_rdd.sortByKey().map(format_output)
    
    results = formatted_rdd.collect()
    with open("output_rdd.txt", "w") as f:
        for line in results:
            f.write(line + "\n")

    sc.stop()

if __name__ == "__main__":
    main()


import sys
import json
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import RegexTokenizer, StopWordsRemover, CountVectorizer, IDF, StringIndexer, ChiSqSelector

# Same pattern as in Part 1
DELIMITER_PATTERN = r"""[\s\d()\[\]{}.!?,;:+=\-_"'`~#@&*%€$§\\/]+"""

def load_stopwords(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    spark = SparkSession.builder \
        .appName("PipelineDataFrames") \
        .master("local[*]") \
        .getOrCreate()
        
    spark.sparkContext.setLogLevel("WARN")

    # Load data
    reviews_df = spark.read.json("reviews_devset.json")
    # Make sure we only have rows with reviewText and category
    reviews_df = reviews_df.dropna(subset=["reviewText", "category"])

    # Load stopwords
    stopwords_list = load_stopwords("stopwords.txt")

    # ML Pipeline
    regex_tokenizer = RegexTokenizer(
        inputCol="reviewText",
        outputCol="tokens",
        pattern=DELIMITER_PATTERN,
        gaps=True,
        toLowercase=True
    )

    sw_remover = StopWordsRemover(
        inputCol="tokens",
        outputCol="filtered_tokens",
        stopWords=stopwords_list
    )

    # Use CountVectorizer to map tokens to indices and compute Term Frequency
    count_vectorizer = CountVectorizer(
        inputCol="filtered_tokens",
        outputCol="raw_features"
    )

    # Compute TF-IDF
    idf_transformer = IDF(
        inputCol="raw_features",
        outputCol="features"
    )

    # Label indexer for category
    category_indexer = StringIndexer(
        inputCol="category",
        outputCol="label"
    )

    # Chi-Square selector for 2000 features
    chi_sq_selector = ChiSqSelector(
        numTopFeatures=2000,
        featuresCol="features",
        labelCol="label",
        outputCol="selected_features"
    )

    feature_selection_pipeline = Pipeline(stages=[regex_tokenizer, sw_remover, count_vectorizer, idf_transformer, category_indexer, chi_sq_selector])
    
    # Fit the pipeline
    fitted_pipeline_model = feature_selection_pipeline.fit(reviews_df)
    
    # Extract the vocabulary and selected features
    # count_vectorizer model is at index 2
    fitted_count_vectorizer = fitted_pipeline_model.stages[2]
    vocabulary_list = fitted_count_vectorizer.vocabulary
    
    # chi_sq_selector model is at index 5
    fitted_chi_sq_selector = fitted_pipeline_model.stages[5]
    top_feature_indices = fitted_chi_sq_selector.selectedFeatures
    
    top_selected_terms = [vocabulary_list[i] for i in top_feature_indices]
    
    # We can write the terms to output_ds.txt
    # Sorting them alphabetically just to have a deterministic output
    top_selected_terms.sort()
    
    with open("output_ds.txt", "w") as f:
        for term in top_selected_terms:
            f.write(term + "\n")

    spark.stop()

if __name__ == "__main__":
    main()


import sys
import json
from pyspark.sql import SparkSession
from pyspark.ml import Pipeline
from pyspark.ml.feature import RegexTokenizer, StopWordsRemover, CountVectorizer, IDF, StringIndexer, ChiSqSelector, Normalizer
from pyspark.ml.classification import LinearSVC, OneVsRest
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.tuning import ParamGridBuilder, TrainValidationSplit

DELIMITER_PATTERN = r"""[\s\d()\[\]{}.!?,;:+=\-_"'`~#@&*%€$§\\/]+"""

def load_stopwords(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def main():
    spark = SparkSession.builder \
        .appName("TextClassificationSVM") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
        
    spark.sparkContext.setLogLevel("WARN")

    print("Loading data...")
    df = spark.read.json("reviews_devset.json")
    df = df.dropna(subset=["reviewText", "category"])

    # Optionally downsample the data to make it run faster during development
    # Uncomment the following line if it's taking too long
    # df = df.sample(fraction=0.1, seed=42)

    # Split into train_val (80%) and test (20%)
    train_val_df, test_df = df.randomSplit([0.8, 0.2], seed=42)

    stopwords_list = load_stopwords("stopwords.txt")

    # 1. RegexTokenizer
    tokenizer = RegexTokenizer(
        inputCol="reviewText",
        outputCol="tokens",
        pattern=DELIMITER_PATTERN,
        gaps=True,
        toLowercase=True
    )

    # 2. StopWordsRemover
    remover = StopWordsRemover(
        inputCol="tokens",
        outputCol="filtered_tokens",
        stopWords=stopwords_list
    )

    # 3. CountVectorizer
    cv = CountVectorizer(
        inputCol="filtered_tokens",
        outputCol="raw_features",
        minDF=2.0 # Filter out extremely rare words to save memory
    )

    # 4. IDF
    idf = IDF(
        inputCol="raw_features",
        outputCol="tfidf_features"
    )

    # 5. StringIndexer for Category
    indexer = StringIndexer(
        inputCol="category",
        outputCol="label"
    )

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

    # Complete Pipeline
    pipeline = Pipeline(stages=[
        tokenizer, remover, cv, idf, indexer, selector, normalizer, ovr
    ])

    # Evaluator
    evaluator = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="f1"
    )

    # Grid Search
    # Compare feature sizes: 2000 vs 500
    # LinearSVC params:
    # regParam (3 values)
    # standardization (2 values)
    # maxIter (2 values)
    paramGrid = ParamGridBuilder() \
        .addGrid(selector.numTopFeatures, [2000, 500]) \
        .addGrid(lsvc.regParam, [0.1, 0.01, 0.001]) \
        .addGrid(lsvc.standardization, [True, False]) \
        .addGrid(lsvc.maxIter, [10, 50]) \
        .build()

    tvs = TrainValidationSplit(
        estimator=pipeline,
        estimatorParamMaps=paramGrid,
        evaluator=evaluator,
        trainRatio=0.75,
        seed=42
    )

    print("Starting Grid Search with TrainValidationSplit...")
    tvs_model = tvs.fit(train_val_df)

    print("Evaluating on Test Set...")
    predictions = tvs_model.transform(test_df)
    f1_score = evaluator.evaluate(predictions)

    print(f"Test Set F1-Score: {f1_score}")

    best_pipeline = tvs_model.bestModel
    
    best_selector = best_pipeline.stages[5]
    print(f"Best numTopFeatures: {best_selector.getNumTopFeatures()}")
    
    best_ovr = best_pipeline.stages[7]
    best_lsvc = best_ovr.getClassifier()
    print(f"Best regParam: {best_lsvc.getRegParam()}")
    print(f"Best standardization: {best_lsvc.getStandardization()}")
    print(f"Best maxIter: {best_lsvc.getMaxIter()}")

    with open("part3_best_params.txt", "w") as f:
        f.write(f"Test F1-Score: {f1_score}\n")
        f.write(f"Best numTopFeatures: {best_selector.getNumTopFeatures()}\n")
        f.write(f"Best regParam: {best_lsvc.getRegParam()}\n")
        f.write(f"Best standardization: {best_lsvc.getStandardization()}\n")
        f.write(f"Best maxIter: {best_lsvc.getMaxIter()}\n")

    spark.stop()

if __name__ == "__main__":
    main()

