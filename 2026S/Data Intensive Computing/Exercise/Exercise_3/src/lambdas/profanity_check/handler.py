import json
import os
import re
import urllib.parse

import boto3

try:
    from profanityfilter import ProfanityFilter
except Exception as exc:
    ProfanityFilter = None
    print(f"profanityfilter unavailable, using fallback bad-word list: {exc}")

endpoint_url = os.getenv("MINISTACK_ENDPOINT")
s3 = boto3.client("s3", endpoint_url=endpoint_url)
ssm = boto3.client("ssm", endpoint_url=endpoint_url)
dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)

FALLBACK_BAD_WORDS = {
    "arse", "ass", "asshole", "bastard", "bitch", "bollocks", "bullshit", "crap",
    "cunt", "damn", "dick", "fuck", "fucked", "fucker", "fucking", "motherfucker",
    "piss", "prick", "shit", "shitty", "slut", "twat", "whore",
}

_pf = ProfanityFilter() if ProfanityFilter else None


def contains_profanity(text):
    text = str(text or "")
    if _pf is not None:
        try:
            return bool(_pf.is_profane(text))
        except Exception as exc:
            print(f"profanityfilter failed, using fallback bad-word list: {exc}")

    words = set(re.findall(r"[a-z]+", text.lower()))
    return bool(words.intersection(FALLBACK_BAD_WORDS))


def _parameter(name):
    return ssm.get_parameter(Name=name)["Parameter"]["Value"]


def _increment_impolite_count(customers_table, customer_id):
    response = customers_table.update_item(
        Key={"customerId": customer_id},
        UpdateExpression=(
            "SET impolite_reviews_count = if_not_exists(impolite_reviews_count, :zero) + :inc, "
            "is_banned = if_not_exists(is_banned, :not_banned)"
        ),
        ExpressionAttributeValues={":inc": 1, ":zero": 0, ":not_banned": False},
        ReturnValues="UPDATED_NEW",
    )
    count = int(response["Attributes"].get("impolite_reviews_count", 0))

    if count > 3:
        customers_table.update_item(
            Key={"customerId": customer_id},
            UpdateExpression="SET is_banned = :banned",
            ExpressionAttributeValues={":banned": True},
        )
    return count


def handler(event, context):
    records = (event or {}).get("Records", [])
    if not records:
        print("No S3 records in event, skipping.")
        return {"statusCode": 200, "body": "No records to process"}

    target_bucket = _parameter("/serverless-app/buckets/profanity-checked")
    customers_table = dynamodb.Table(_parameter("/serverless-app/tables/customers"))

    for record in records:
        source_bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"], encoding="utf-8")

        response = s3.get_object(Bucket=source_bucket, Key=key)
        review_data = json.loads(response["Body"].read().decode("utf-8"))

        text_to_check = f"{review_data.get('reviewText', '')} {review_data.get('summary', '')}"
        is_profane = contains_profanity(text_to_check)
        review_data["is_profane"] = is_profane

        if is_profane:
            customer_id = review_data.get("reviewerID") or "unknown"
            count = _increment_impolite_count(customers_table, customer_id)
            review_data["impolite_reviews_count"] = count

        s3.put_object(
            Bucket=target_bucket,
            Key=key,
            Body=json.dumps(review_data),
            ContentType="application/json",
        )
        print(f"Successfully profanity-checked {key} and uploaded to {target_bucket}")

    return {"statusCode": 200, "body": "Success"}
