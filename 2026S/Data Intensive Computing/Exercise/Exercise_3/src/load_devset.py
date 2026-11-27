"""
load_devset.py — Upload all reviews from reviews_devset.json to the pipeline
and print aggregated results once processing is complete.

Usage:
    python load_devset.py --devset path/to/reviews_devset.json
    python load_devset.py --devset path/to/reviews_devset.json --workers 4
"""

import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

ENDPOINT = "http://localhost:4566"

s3 = boto3.client("s3", endpoint_url=ENDPOINT)
ssm = boto3.client("ssm", endpoint_url=ENDPOINT)
dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT)
awslambda = boto3.client("lambda", endpoint_url=ENDPOINT)


def _parameter(name):
    return ssm.get_parameter(Name=name)["Parameter"]["Value"]


def upload_review(bucket, review):
    """Upload a single review JSON to the input S3 bucket."""
    key = f"{review.get('reviewerID', 'unknown')}_{uuid.uuid4()}.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(review),
        ContentType="application/json",
    )
    return key


def wait_for_pipeline(expected_count, reviews_table, timeout=300, poll_interval=5):
    """Poll DynamoDB until all reviews are processed or timeout is reached."""
    print(f"\nWaiting for pipeline to process {expected_count} reviews ", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = reviews_table.scan(Select="COUNT")
        count = response["Count"]
        print(f"\r  Processed: {count}/{expected_count}   ", end="", flush=True)
        if count >= expected_count:
            print()
            return True
        time.sleep(poll_interval)
    print(f"\n  Timed out after {timeout}s — only {count}/{expected_count} processed.")
    return False


def print_results():
    """Invoke the list Lambda and print aggregated results."""
    response = awslambda.invoke(FunctionName="list", Payload=b"{}")
    payload = json.loads(response["Payload"].read().decode("utf-8"))
    body = json.loads(payload["body"])

    print("\n" + "=" * 50)
    print("  PIPELINE RESULTS")
    print("=" * 50)
    print(f"  Total reviews processed : {body.get('total_reviews', 0)}")
    print(f"  Positive                : {body.get('positive', 0)}")
    print(f"  Neutral                 : {body.get('neutral', 0)}")
    print(f"  Negative                : {body.get('negative', 0)}")
    print(f"  Profanity detected      : {body.get('profane_count', 0)}")
    banned = body.get("banned_users", [])
    if banned:
        print(f"  Banned users ({len(banned)})      : {', '.join(banned)}")
    else:
        print("  Banned users            : none")
    print("=" * 50)
    return body


def main():
    parser = argparse.ArgumentParser(description="Load reviews_devset.json into the pipeline.")
    parser.add_argument("--devset", required=True, help="Path to reviews_devset.json")
    parser.add_argument("--workers", type=int, default=4, help="Parallel upload threads (default: 4)")
    parser.add_argument("--timeout", type=int, default=300, help="Max seconds to wait for pipeline (default: 300)")
    args = parser.parse_args()

    # Load devset
    print(f"Loading reviews from {args.devset} ...")
    reviews = []
    with open(args.devset, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                reviews.append(json.loads(line))
    print(f"  Found {len(reviews)} reviews.")

    # Testing: Limit to first 100 reviews to avoid long processing times
    # reviews = reviews[:1000]

    # Get input bucket
    input_bucket = _parameter("/serverless-app/buckets/input")
    reviews_table = dynamodb.Table(_parameter("/serverless-app/tables/reviews_results"))

    # Upload all reviews in parallel
    print(f"\nUploading to s3://{input_bucket} with {args.workers} workers ...")
    uploaded = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(upload_review, input_bucket, r): r for r in reviews}
        for future in as_completed(futures):
            try:
                future.result()
                uploaded += 1
                if uploaded % 50 == 0:
                    print(f"  Uploaded {uploaded}/{len(reviews)} ...")
            except Exception as exc:
                failed += 1
                print(f"  Upload failed: {exc}")

    print(f"  Done — {uploaded} uploaded, {failed} failed.")

    # Wait for pipeline and print results
    wait_for_pipeline(uploaded, reviews_table, timeout=args.timeout)
    print_results()


if __name__ == "__main__":
    main()
