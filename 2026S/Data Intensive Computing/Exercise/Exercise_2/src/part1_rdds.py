import os
import re
import json
from typing import Any
from urllib.parse import urlparse

from pyspark import SparkContext, SparkConf


# Constants
DELIMITER_PATTERN = r"""[\s\d()\[\]{}.!?,;:+=\-_"'`~#@&*%€$§\\/]+"""
COMPILED_DELIMITER_PATTERN = re.compile(DELIMITER_PATTERN)
MIN_TOKEN_LENGTH = 2
TOP_K_TERMS = 75
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


def load_stopwords(
    sc: SparkContext,
    file_path: str,
) -> set[str]:
    """
    Load stopwords from a text file and return a set of stopwords

    Args:
        file_path: Path to the stopwords text file, where each line contains a single stopword

    Returns:
        A set of stopwords loaded from the file
    """
    if is_remote_path(file_path):
        lines = sc.textFile(file_path).collect()
    else:
        local_path = normalize_local_path(file_path)
        with open(local_path, encoding="utf-8") as txt_file:
            lines = txt_file.readlines()

    stopwords = {line.strip() for line in lines if line.strip()}

    return stopwords


def write_output_lines(
    sc: SparkContext,
    file_path: str,
    lines: list[str],
) -> None:
    """Write output lines to a local file or a remote filesystem path."""
    if is_remote_path(file_path):
        jvm: Any = sc._jvm
        jsc: Any = sc._jsc
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

    else:
        local_path = normalize_local_path(file_path)
        output_dir = os.path.dirname(local_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(local_path, "w", encoding="utf-8") as output_file:
            for line in lines:
                output_file.write(line + "\n")


def preprocess_text(
    text: str,
    stopwords: set[str],
) -> set[str]:
    """
    Preprocess a review text by applying the following steps:
        1. Case-fold to lowercase
        2. Tokenize using the predefined delimiter regex pattern
        3. Remove stopwords and tokens shorter than the minimum token length
        4. Deduplicate tokens to get a set of unique terms (for chi-square calculation)

    Args:
        text: The raw review text to preprocess
        stopwords: A set of stopwords to remove from the text

    Returns:
        A set of unique, preprocessed terms extracted from the review text
    """
    lower_text = text.lower()
    tokens = COMPILED_DELIMITER_PATTERN.split(lower_text)

    unique_terms = {
        token
        for token in tokens
        if len(token) >= MIN_TOKEN_LENGTH and token not in stopwords
    }

    return unique_terms


def chi_square_job(sc: SparkContext) -> None:
    # Load stopwords
    stopwords_file_path = os.environ.get("STOPWORDS_FILE_PATH", "data/stopwords.txt")
    stopwords = load_stopwords(
        sc=sc,
        file_path=stopwords_file_path,
    )

    # Broadcast stopwords to all worker nodes
    stopwords_bc = sc.broadcast(stopwords)

    # Read dataset
    review_file_path = os.environ.get("REVIEWS_FILE_PATH", "data/reviews_devset.json")
    raw_rdd = sc.textFile(f"{review_file_path}")

    # Map to (category, unique_terms)
    def parse_review(line: str) -> tuple[str, set[str]] | None:
        """Parse a JSON line representing a review and return a tuple of (category, unique_terms)"""
        try:
            # Parse the JSON line to extract category and review text
            review = json.loads(line)
            category = review["category"]
            text = review["reviewText"]

            # Get unique terms from the review text after preprocessing
            terms = preprocess_text(text, stopwords_bc.value)

            return (category, terms)
        except Exception:
            return None

    def add_counts(left: int, right: int) -> int:
        return left + right

    def keep_parsed_reviews(review: tuple[str, set[str]] | None) -> list[tuple[str, set[str]]]:
        return [review] if review is not None else []

    def to_category_count(review: tuple[str, set[str]]) -> tuple[str, int]:
        return (review[0], int(1))

    def to_term_category_counts(review: tuple[str, set[str]]) -> list[tuple[tuple[str, str], int]]:
        return [((term, review[0]), int(1)) for term in review[1]]

    # Parse reviews and filter out any invalid entries
    # Output: RDD of (category, unique_terms) for each valid review
    parsed_rdd = raw_rdd.map(parse_review).flatMap(keep_parsed_reviews)

    # Optimize the parsed RDD by caching it in memory since it will be used multiple times
    parsed_rdd = parsed_rdd.cache()

    # category_counts: dict of {category: count} for all categories
    category_count1 = parsed_rdd.map(to_category_count)

    # Nc: total reviews per category
    category_counts = category_count1.reduceByKey(add_counts).collectAsMap()

    # N: total reviews
    N = sum(category_counts.values())

    # Broadcast category counts and total count to all worker nodes    
    Nc_bc = sc.broadcast(category_counts)
    N_bc = sc.broadcast(N)

    # term_category_count1_rdd: ((term, category), 1)
    term_category_count1_rdd = parsed_rdd.flatMap(to_term_category_counts)

    # A_rdd: ((term, category), count of reviews in category containing term (A))
    A_rdd = term_category_count1_rdd.reduceByKey(add_counts)

    # Nt_rdd: (term, 1) for each review containing the term, regardless of category
    term_A_rdd = A_rdd.map(lambda x: (x[0][0], x[1]))
    # Get total count of reviews containing term across all categories (Nt)
    # output: RDD of (term, Nt)
    Nt_rdd = term_A_rdd.reduceByKey(add_counts)

    # A_by_term: (term, (category, A))
    A_by_term = A_rdd.map(lambda x: (x[0][0], (x[0][1], x[1])))

    # joined_rdd: (term, ((category, A), Nt))
    joined_rdd = A_by_term.join(Nt_rdd)

    def compute_chi_square(record):
        term, ((category, A), Nt) = record
        N_val = N_bc.value
        Nc_val = Nc_bc.value[category]

        B = Nt - A
        C = Nc_val - A
        D = N_val - (A + B + C)

        # Avoid division by zero
        denominator = (A + B) * (C + D) * (A + C) * (B + D)
        chi_sq = 0.0
        if denominator != 0:
            numerator = (A * D - B * C) ** 2 * (A + B + C + D)
            chi_sq = numerator / denominator

        return (category, (term, chi_sq))

    chi_sq_rdd = joined_rdd.map(compute_chi_square)

    # Group by category and get top K terms with highest chi-square scores
    def get_top_k(iterable):
        sorted_items = sorted(iterable, key=lambda x: (-x[1], x[0]))
        return sorted_items[:TOP_K_TERMS]

    top_terms_rdd = chi_sq_rdd.groupByKey().mapValues(get_top_k)

    # Format the output as specified: "category term1:score1 term2:score2 ..."
    def format_output(record):
        category, terms = record
        terms_str = " ".join([f"{term}:{score:.4f}" for term, score in terms])
        return f"{category} {terms_str}"

    formatted_rdd = top_terms_rdd.sortByKey().map(format_output)

    # Collect the results and write to output file
    results = formatted_rdd.collect()
    output_file_path = os.environ.get("OUTPUT_FILE_PATH", "output/output_rdd.txt")
    write_output_lines(
        sc=sc,
        file_path=output_file_path,
        lines=results,
    )

    return


def main() -> None:
    # Initialize SparkContext
    conf = SparkConf().setAppName("ChiSquareRDD")
    if conf.get("spark.master", None) is None:
        conf = conf.setMaster(os.environ.get("SPARK_MASTER", DEFAULT_SPARK_MASTER))

    sc = SparkContext(conf=conf)
    sc.setLogLevel(os.environ.get("SPARK_LOG_LEVEL", "WARN"))

    # Run the chi-square job
    chi_square_job(sc)

    # Stop SparkContext
    sc.stop()


if __name__ == "__main__":
    main()
