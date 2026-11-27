import json
import os
import typing
from decimal import Decimal

import boto3

if typing.TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient

internal_endpoint_url = None
if os.getenv("STAGE") == "local":
    internal_endpoint_url = "http://localhost:4566"

dynamodb = boto3.resource("dynamodb", endpoint_url=internal_endpoint_url)
ssm: "SSMClient" = boto3.client("ssm", endpoint_url=internal_endpoint_url)

DEFAULT_ALLOWED_ORIGINS = "http://localhost:4566,http://127.0.0.1:4566,https://lbd.tuwien.ac.at"


def get_allowed_origins() -> set[str]:
    configured = os.getenv("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return {origin.strip() for origin in configured.split(",") if origin.strip()}


def get_cors_headers(event) -> dict[str, str]:
    origin = (event or {}).get("headers", {}).get("origin")
    allowed_origins = get_allowed_origins()
    allow_origin = origin if origin in allowed_origins else next(iter(allowed_origins), "*")
    return {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Vary": "Origin",
    }


def decimal_default(value):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    raise TypeError


def scan_all(table):
    items = []
    kwargs = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def handler(event, context):
    event = event or {}
    cors_headers = get_cors_headers(event)

    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": cors_headers, "body": ""}

    reviews_table_name = ssm.get_parameter(Name="/serverless-app/tables/reviews_results")["Parameter"]["Value"]
    customers_table_name = ssm.get_parameter(Name="/serverless-app/tables/customers")["Parameter"]["Value"]

    reviews = scan_all(dynamodb.Table(reviews_table_name))
    customers = scan_all(dynamodb.Table(customers_table_name))

    results = {
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "profane_count": 0,
        "banned_users": [],
        "total_reviews": len(reviews),
    }

    for review in reviews:
        sentiment = review.get("sentiment")
        if sentiment in ("positive", "neutral", "negative"):
            results[sentiment] += 1
        if review.get("is_profane"):
            results["profane_count"] += 1

    for customer in customers:
        if customer.get("is_banned"):
            results["banned_users"].append(customer.get("customerId"))

    results["banned_users"].sort()

    return {
        "statusCode": 200,
        "headers": {**cors_headers, "Content-Type": "application/json"},
        "body": json.dumps(results, default=decimal_default),
    }


if __name__ == "__main__":
    print(handler(None, None))
