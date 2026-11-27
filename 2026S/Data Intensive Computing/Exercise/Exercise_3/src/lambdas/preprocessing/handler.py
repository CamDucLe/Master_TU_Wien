import json
import os
import re
import urllib.parse

import boto3
import nltk

PACKAGE_NLTK_DATA_DIR = os.path.join(os.path.dirname(__file__), "nltk_data")
TMP_NLTK_DATA_DIR = "/tmp/nltk_data"
os.makedirs(TMP_NLTK_DATA_DIR, exist_ok=True)
NLP_DATA_DIRS = [PACKAGE_NLTK_DATA_DIR, TMP_NLTK_DATA_DIR]
for data_dir in NLP_DATA_DIRS:
    if os.path.isdir(data_dir) and data_dir not in nltk.data.path:
        nltk.data.path.append(data_dir)

FALLBACK_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "or", "she", "that", "the", "this",
    "to", "was", "were", "will", "with", "i", "you", "we", "they", "my", "your", "our",
}

endpoint_url = os.getenv("MINISTACK_ENDPOINT")
s3 = boto3.client("s3", endpoint_url=endpoint_url)
ssm = boto3.client("ssm", endpoint_url=endpoint_url)

_nltk_ready = None


def _ensure_nltk_data():
    global _nltk_ready
    if _nltk_ready is not None:
        return _nltk_ready

    required_resources = [
        ("corpora/wordnet", "wordnet"),
        ("corpora/stopwords", "stopwords"),
        ("tokenizers/punkt", "punkt"),
        ("tokenizers/punkt_tab", "punkt_tab"),
    ]

    try:
        for resource_path, package_name in required_resources:
            try:
                nltk.data.find(resource_path)
            except LookupError:
                nltk.download(package_name, download_dir=TMP_NLTK_DATA_DIR, quiet=True, raise_on_error=True)
        _nltk_ready = True
    except Exception as exc:
        print(f"NLTK data unavailable, using fallback preprocessing: {exc}")
        _nltk_ready = False
    return _nltk_ready


def _fallback_preprocess(text):
    tokens = re.findall(r"[a-z0-9]+", str(text).lower())
    return " ".join(token for token in tokens if token not in FALLBACK_STOP_WORDS)


def preprocess_text(text):
    if not text:
        return ""

    if not _ensure_nltk_data():
        return _fallback_preprocess(text)

    try:
        from nltk.corpus import stopwords
        from nltk.stem import WordNetLemmatizer
        from nltk.tokenize import word_tokenize

        stop_words = set(stopwords.words("english"))
        lemmatizer = WordNetLemmatizer()
        tokens = word_tokenize(str(text).lower())
        normalized = [
            lemmatizer.lemmatize(token)
            for token in tokens
            if token.isalnum() and token not in stop_words
        ]
        return " ".join(normalized)
    except Exception as exc:
        print(f"NLTK preprocessing failed, using fallback: {exc}")
        return _fallback_preprocess(text)


def _target_bucket():
    parameter = ssm.get_parameter(Name="/serverless-app/buckets/preprocessed")
    return parameter["Parameter"]["Value"]


def handler(event, context):
    records = (event or {}).get("Records", [])
    if not records:
        print("No S3 records in event, skipping.")
        return {"statusCode": 200, "body": "No records to process"}

    target_bucket = _target_bucket()

    for record in records:
        source_bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"], encoding="utf-8")

        response = s3.get_object(Bucket=source_bucket, Key=key)
        review_data = json.loads(response["Body"].read().decode("utf-8"))

        review_data["preprocessed_reviewText"] = preprocess_text(review_data.get("reviewText", ""))
        review_data["preprocessed_summary"] = preprocess_text(review_data.get("summary", ""))

        s3.put_object(
            Bucket=target_bucket,
            Key=key,
            Body=json.dumps(review_data),
            ContentType="application/json",
        )
        print(f"Successfully preprocessed {key} and uploaded to {target_bucket}")

    return {"statusCode": 200, "body": "Success"}
