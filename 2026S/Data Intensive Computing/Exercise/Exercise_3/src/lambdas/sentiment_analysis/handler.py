import json
import os
import re
import urllib.parse
from decimal import Decimal

import boto3
import nltk

PACKAGE_NLTK_DATA_DIR = os.path.join(os.path.dirname(__file__), "nltk_data")
TMP_NLTK_DATA_DIR = "/tmp/nltk_data"
os.makedirs(TMP_NLTK_DATA_DIR, exist_ok=True)
NLP_DATA_DIRS = [PACKAGE_NLTK_DATA_DIR, TMP_NLTK_DATA_DIR]
for data_dir in NLP_DATA_DIRS:
    if os.path.isdir(data_dir) and data_dir not in nltk.data.path:
        nltk.data.path.append(data_dir)

endpoint_url = os.getenv("MINISTACK_ENDPOINT")
s3 = boto3.client("s3", endpoint_url=endpoint_url)
ssm = boto3.client("ssm", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)

POSITIVE_WORDS = {"amazing", "awesome", "excellent", "fantastic", "good", "great", "happy", "love", "loved", "perfect", "recommend"}
NEGATIVE_WORDS = {"awful", "bad", "broken", "disappointed", "hate", "hated", "poor", "refund", "terrible", "waste", "worst"}
_vader_ready = None


def _ensure_vader_data():
    global _vader_ready
    if _vader_ready is not None:
        return _vader_ready

    try:
        try:
            nltk.data.find("sentiment/vader_lexicon.zip")
        except LookupError:
            nltk.download("vader_lexicon", download_dir=TMP_NLTK_DATA_DIR, quiet=True, raise_on_error=True)
        _vader_ready = True
    except Exception as exc:
        print(f"VADER data unavailable, using fallback sentiment scoring: {exc}")
        _vader_ready = False
    return _vader_ready


def _rating_signal(overall):
    try:
        rating = float(overall)
    except (TypeError, ValueError):
        return 0.0

    if rating >= 4:
        return 1.0
    if rating <= 2:
        return -1.0
    return 0.0


def _text_signal(text):
    if _ensure_vader_data():
        try:
            from nltk.sentiment import SentimentIntensityAnalyzer

            return float(SentimentIntensityAnalyzer().polarity_scores(text)["compound"])
        except Exception as exc:
            print(f"VADER scoring failed, using fallback sentiment scoring: {exc}")

    words = re.findall(r"[a-z]+", text.lower())
    score = 0
    for word in words:
        if word in POSITIVE_WORDS:
            score += 1
        if word in NEGATIVE_WORDS:
            score -= 1
    if score > 0:
        return min(score / 3, 1.0)
    if score < 0:
        return max(score / 3, -1.0)
    return 0.0


def classify_sentiment(text, overall):
    text_score = _text_signal(text)
    rating_score = _rating_signal(overall)
    combined = (0.7 * text_score) + (0.3 * rating_score)

    if combined >= 0.05:
        return "positive", combined, text_score, rating_score
    if combined <= -0.05:
        return "negative", combined, text_score, rating_score
    return "neutral", combined, text_score, rating_score


def _parameter(name):
    return ssm.get_parameter(Name=name)["Parameter"]["Value"]


def _decimal(value):
    return Decimal(str(round(float(value), 4)))


def handler(event, context):
    records = (event or {}).get("Records", [])
    if not records:
        print("No S3 records in event, skipping.")
        return {"statusCode": 200, "body": "No records to process"}

    reviews_table = dynamodb.Table(_parameter("/serverless-app/tables/reviews_results"))

    for record in records:
        source_bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"], encoding="utf-8")

        response = s3.get_object(Bucket=source_bucket, Key=key)
        review_data = json.loads(response["Body"].read().decode("utf-8"))

        text_to_check = f"{review_data.get('reviewText', '')} {review_data.get('summary', '')}"
        overall = review_data.get("overall")
        sentiment, combined, text_score, rating_score = classify_sentiment(text_to_check, overall)
        review_data["sentiment"] = sentiment

        item = {
            "reviewId": key,
            "customerId": review_data.get("reviewerID", "unknown"),
            "summary": review_data.get("summary", ""),
            "reviewText": review_data.get("reviewText", ""),
            "original_text": text_to_check,
            "preprocessed_text": f"{review_data.get('preprocessed_reviewText', '')} {review_data.get('preprocessed_summary', '')}".strip(),
            "is_profane": bool(review_data.get("is_profane", False)),
            "sentiment": sentiment,
            "overall": _decimal(overall or 0),
            "sentiment_score": _decimal(combined),
            "text_sentiment_score": _decimal(text_score),
            "rating_sentiment_score": _decimal(rating_score),
        }

        reviews_table.put_item(Item=item)
        print(f"Successfully analyzed sentiment for {key} and saved to DynamoDB")

    return {"statusCode": 200, "body": "Success"}
