import json
import os
import time
import typing
import uuid

import boto3
import pytest

if typing.TYPE_CHECKING:
    from mypy_boto3_lambda import LambdaClient
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_ssm import SSMClient

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

endpoint_url = "http://localhost:4566"

s3: "S3Client" = boto3.client("s3", endpoint_url=endpoint_url)
ssm: "SSMClient" = boto3.client("ssm", endpoint_url=endpoint_url)
awslambda: "LambdaClient" = boto3.client("lambda", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)


def _parameter(name):
    return ssm.get_parameter(Name=name)["Parameter"]["Value"]


@pytest.fixture(autouse=True)
def _wait_for_lambdas():
    for function_name in ["presign", "list", "preprocessing", "profanity_check", "sentiment_analysis"]:
        awslambda.get_waiter("function_active").wait(FunctionName=function_name)


def _put_review_and_wait(review_payload, key=None, timeout_seconds=50):
    source_bucket = _parameter("/serverless-app/buckets/input")
    reviews_table = dynamodb.Table(_parameter("/serverless-app/tables/reviews_results"))
    key = key or f"{review_payload['reviewerID']}_{uuid.uuid4()}.json"

    s3.put_object(
        Bucket=source_bucket,
        Key=key,
        Body=json.dumps(review_payload),
        ContentType="application/json",
    )

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = reviews_table.get_item(Key={"reviewId": key})
        if "Item" in response:
            return key, response["Item"]
        time.sleep(2)

    pytest.fail(f"Pipeline failed to process {key} within {timeout_seconds} seconds")


def test_pipeline_normal_review():
    reviewer_id = f"user_{uuid.uuid4()}"
    key = f"{reviewer_id}_test_normal.json"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 5,
        "summary": "Great product!",
        "reviewText": "I absolutely loved this product, it is amazing and works perfectly.",
    }

    _, item = _put_review_and_wait(review_payload, key)

    assert item["customerId"] == reviewer_id
    assert item["sentiment"] == "positive"
    assert item["is_profane"] is False
    assert float(item["overall"]) == 5.0
    assert float(item["sentiment_score"]) > 0
    assert "great" in item["preprocessed_text"].lower() or "loved" in item["preprocessed_text"].lower()
    assert " the " not in f" {item['preprocessed_text'].lower()} "
    assert " and " not in f" {item['preprocessed_text'].lower()} "


def test_pipeline_preprocessing_cleans_text():
    reviewer_id = f"preprocess_user_{uuid.uuid4()}"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 4,
        "summary": "A very Great summary",
        "reviewText": "This is the product that I bought and it works well.",
    }

    _, item = _put_review_and_wait(review_payload, f"{reviewer_id}_preprocess.json")

    preprocessed_text = item["preprocessed_text"].lower()
    assert item["sentiment"] == "positive"
    assert "great" in preprocessed_text
    assert "summary" in preprocessed_text
    assert "product" in preprocessed_text
    assert " the " not in f" {preprocessed_text} "
    assert " and " not in f" {preprocessed_text} "
    assert " is " not in f" {preprocessed_text} "


def test_pipeline_negative_sentiment():
    reviewer_id = f"negative_user_{uuid.uuid4()}"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 1,
        "summary": "Terrible item",
        "reviewText": "This product is awful, broken, and I hate it.",
    }

    _, item = _put_review_and_wait(review_payload, f"{reviewer_id}_negative.json")

    assert item["sentiment"] == "negative"
    assert float(item["sentiment_score"]) < 0
    assert float(item["rating_sentiment_score"]) < 0
    assert float(item["text_sentiment_score"]) < 0


def test_pipeline_neutral_sentiment():
    reviewer_id = f"neutral_user_{uuid.uuid4()}"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 3,
        "summary": "Average item",
        "reviewText": "The package arrived today and nothing else stands out.",
    }

    _, item = _put_review_and_wait(review_payload, f"{reviewer_id}_neutral.json")

    assert item["sentiment"] == "neutral"
    assert float(item["sentiment_score"]) == 0.0
    assert float(item["rating_sentiment_score"]) == 0.0
    assert float(item["text_sentiment_score"]) == 0.0 or float(item["text_sentiment_score"]) > -0.5


def test_pipeline_positive_sentiment():
    reviewer_id = f"positive_user_{uuid.uuid4()}"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 5,
        "summary": "Excellent product",
        "reviewText": "This product is amazing, works perfectly, and I love it.",
    }

    _, item = _put_review_and_wait(review_payload, f"{reviewer_id}_positive.json")

    assert item["sentiment"] == "positive"
    assert float(item["sentiment_score"]) > 0
    assert float(item["rating_sentiment_score"]) > 0
    assert float(item["text_sentiment_score"]) > 0


def test_pipeline_uses_overall_for_sentiment():
    reviewer_id = f"rating_user_{uuid.uuid4()}"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 1,
        "summary": "Not as expected",
        "reviewText": "The item arrived and I used it twice.",
    }

    _, item = _put_review_and_wait(review_payload, f"{reviewer_id}_rating_signal.json")

    assert item["sentiment"] == "negative"
    assert float(item["rating_sentiment_score"]) < 0


def test_pipeline_profanity_and_ban():
    customers_table = dynamodb.Table(_parameter("/serverless-app/tables/customers"))
    reviews_table = dynamodb.Table(_parameter("/serverless-app/tables/reviews_results"))
    reviewer_id = f"banned_user_{uuid.uuid4()}"
    review_payload = {
        "reviewerID": reviewer_id,
        "overall": 1,
        "summary": "Terrible",
        "reviewText": "This is absolute shit and fuck this product.",
    }

    keys = []
    for index in range(4):
        key = f"{reviewer_id}_test_profane_{index}.json"
        keys.append(key)
        _put_review_and_wait(review_payload, key)

    customer = customers_table.get_item(Key={"customerId": reviewer_id}).get("Item")
    assert customer is not None
    assert int(customer["impolite_reviews_count"]) == 4
    assert customer["is_banned"] is True

    for key in keys:
        item = reviews_table.get_item(Key={"reviewId": key})["Item"]
        assert item["is_profane"] is True
        assert item["sentiment"] == "negative"


def test_list_lambda_returns_aggregated_results():
    response = awslambda.invoke(FunctionName="list", Payload=b"{}")
    payload = json.loads(response["Payload"].read().decode("utf-8"))
    body = json.loads(payload["body"])

    assert {"positive", "neutral", "negative", "profane_count", "banned_users", "total_reviews"}.issubset(body)
    assert body["total_reviews"] >= body["positive"] + body["neutral"] + body["negative"]
    assert body["profane_count"] >= 0
    assert isinstance(body["banned_users"], list)
