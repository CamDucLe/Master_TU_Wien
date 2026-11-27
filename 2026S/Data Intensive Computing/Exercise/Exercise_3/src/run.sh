#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:4566,http://127.0.0.1:4566,https://lbd.tuwien.ac.at}"
export MINISTACK_ENDPOINT="${MINISTACK_ENDPOINT:-http://localhost:4566}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP="${PYTHON_BIN} -m pip"
AWS="${PYTHON_BIN} -m awscli --endpoint-url=${MINISTACK_ENDPOINT}"

ON_LBD_PROXY=0
if [ -n "${JUPYTERHUB_USER:-}" ] || [ -n "${JUPYTERHUB_SERVICE_PREFIX:-}" ]; then
  ON_LBD_PROXY=1
fi

if [ -z "${S3_ENDPOINT_URL:-}" ]; then
  if [ "${ON_LBD_PROXY}" -eq 1 ] && [ -n "${USER:-}" ] && [ "${USER}" != "root" ]; then
    export S3_ENDPOINT_URL="https://lbd.tuwien.ac.at/user/${USER}/proxy/4566"
  else
    export S3_ENDPOINT_URL=""
  fi
fi

if [ -z "${PUBLIC_BASE_URL:-}" ]; then
  if [ "${ON_LBD_PROXY}" -eq 1 ] && [ -n "${USER:-}" ] && [ "${USER}" != "root" ]; then
    export PUBLIC_BASE_URL="https://lbd.tuwien.ac.at/user/${USER}/proxy/4566"
  else
    export PUBLIC_BASE_URL="http://localhost:4566"
  fi
fi

PRESIGN_LIST_ENV="{\"STAGE\":\"local\",\"ALLOWED_ORIGINS\":\"${ALLOWED_ORIGINS}\""
if [ -n "${S3_ENDPOINT_URL}" ]; then
  PRESIGN_LIST_ENV="${PRESIGN_LIST_ENV},\"S3_ENDPOINT_URL\":\"${S3_ENDPOINT_URL}\""
fi
PRESIGN_LIST_ENV="${PRESIGN_LIST_ENV}}"

pip_install_deps() {
  local requirements_file="$1"
  local target_dir="$2"

  if [ "$(uname -s)" = "Darwin" ]; then
    ${PIP} install -r "${requirements_file}" -t "${target_dir}" --no-cache-dir
  else
    ${PIP} install -r "${requirements_file}" -t "${target_dir}" --no-cache-dir \
      --platform manylinux2014_x86_64 --only-binary=:all:
  fi
}

download_nltk_data() {
  local target_dir="$1"
  shift

  python3 - <<'INNERPY' "$target_dir" "$@" || true
import sys
from pathlib import Path

target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
# Dependencies were installed into the Lambda package directory, not globally.
sys.path.insert(0, str(target.parent.resolve()))
try:
    import nltk
except Exception as exc:
    print(f"Skipping bundled NLTK data download: {exc}")
    raise SystemExit(0)
for package in sys.argv[2:]:
    print(f"Downloading NLTK package {package} into {target}")
    nltk.download(package, download_dir=str(target), quiet=True, raise_on_error=False)
INNERPY
}

package_lambda() {
  local lambda_dir="${ROOT_DIR}/$1"
  local lambda_name
  lambda_name="$(basename "$1")"
  (
    cd "${lambda_dir}"
    rm -rf package lambda.zip __pycache__
    mkdir package
    if [ -f requirements.txt ]; then
      pip_install_deps requirements.txt package
    fi
    ${PIP} install boto3 -t package --no-cache-dir

    if [ "${lambda_name}" = "preprocessing" ]; then
      download_nltk_data "package/nltk_data" wordnet stopwords punkt punkt_tab
    elif [ "${lambda_name}" = "sentiment_analysis" ]; then
      download_nltk_data "package/nltk_data" vader_lexicon
    fi

    cp handler.py package/

    # On macOS, regex installs ARM-compiled C extensions that crash inside
    # MiniStack's Lambda subprocess. Remove the binary so NLTK falls back to
    # the pure-Python 're' module, which works fine for our use case.
    if [ "$(uname -s)" = "Darwin" ]; then
      rm -rf package/regex package/regex-*.dist-info
    fi

    cd package
    zip -r ../lambda.zip . > /dev/null
  )
}

ensure_bucket() {
  local bucket="$1"
  if ${AWS} s3api head-bucket --bucket "${bucket}" >/dev/null 2>&1; then
    echo "Bucket ${bucket} already exists."
  else
    ${AWS} s3 mb "s3://${bucket}"
  fi
}

ensure_table() {
  local table_name="$1"
  local key_name="$2"
  if ${AWS} dynamodb describe-table --table-name "${table_name}" >/dev/null 2>&1; then
    echo "DynamoDB table ${table_name} already exists."
  else
    ${AWS} dynamodb create-table \
      --table-name "${table_name}" \
      --attribute-definitions "AttributeName=${key_name},AttributeType=S" \
      --key-schema "AttributeName=${key_name},KeyType=HASH" \
      --billing-mode PAY_PER_REQUEST >/dev/null
  fi
}

ensure_lambda() {
  local function_name="$1"
  local lambda_dir="$2"
  local timeout="$3"
  local env_json="$4"

  package_lambda "${lambda_dir}"
  if ${AWS} lambda get-function --function-name "${function_name}" >/dev/null 2>&1; then
    ${AWS} lambda update-function-code \
      --function-name "${function_name}" \
      --zip-file "fileb://${lambda_dir}/lambda.zip" >/dev/null
    ${AWS} lambda update-function-configuration \
      --function-name "${function_name}" \
      --timeout "${timeout}" \
      --environment "{\"Variables\":${env_json}}" >/dev/null
  else
    ${AWS} lambda create-function \
      --function-name "${function_name}" \
      --runtime python3.11 \
      --timeout "${timeout}" \
      --zip-file "fileb://${lambda_dir}/lambda.zip" \
      --handler handler.handler \
      --role arn:aws:iam::000000000000:role/lambda-role \
      --environment "{\"Variables\":${env_json}}" >/dev/null
  fi
}

ensure_function_url() {
  local function_name="$1"
  if ${AWS} lambda get-function-url-config --function-name "${function_name}" >/dev/null 2>&1; then
    echo "Function URL for ${function_name} already exists."
  else
    ${AWS} lambda create-function-url-config --function-name "${function_name}" --auth-type NONE >/dev/null
  fi
}

echo "Creating buckets..."
ensure_bucket ministack-reviews-input
ensure_bucket ministack-reviews-preprocessed
ensure_bucket ministack-reviews-profanity-checked
ensure_bucket webapp

echo "Creating DynamoDB tables..."
ensure_table customers customerId
ensure_table reviews_results reviewId

echo "Populating SSM Parameter Store..."
${AWS} ssm put-parameter --name /serverless-app/buckets/input --type String --value ministack-reviews-input --overwrite >/dev/null
${AWS} ssm put-parameter --name /serverless-app/buckets/preprocessed --type String --value ministack-reviews-preprocessed --overwrite >/dev/null
${AWS} ssm put-parameter --name /serverless-app/buckets/profanity-checked --type String --value ministack-reviews-profanity-checked --overwrite >/dev/null
${AWS} ssm put-parameter --name /serverless-app/tables/customers --type String --value customers --overwrite >/dev/null
${AWS} ssm put-parameter --name /serverless-app/tables/reviews_results --type String --value reviews_results --overwrite >/dev/null

echo "Deploying presign Lambda..."
ensure_lambda presign lambdas/presign 10 "${PRESIGN_LIST_ENV}"
ensure_function_url presign

echo "Deploying list Lambda..."
ensure_lambda list lambdas/list 10 "${PRESIGN_LIST_ENV}"
ensure_function_url list

PIPELINE_ENV="{\"MINISTACK_ENDPOINT\":\"${MINISTACK_ENDPOINT}\"}"

echo "Deploying preprocessing Lambda..."
ensure_lambda preprocessing lambdas/preprocessing 60 "${PIPELINE_ENV}"
PREPROCESSING_ARN="$(${AWS} lambda get-function --function-name preprocessing --query 'Configuration.FunctionArn' --output text)"
${AWS} s3api put-bucket-notification-configuration \
  --bucket ministack-reviews-input \
  --notification-configuration "{\"LambdaFunctionConfigurations\": [{\"LambdaFunctionArn\": \"${PREPROCESSING_ARN}\", \"Events\": [\"s3:ObjectCreated:*\"]}]}"

echo "Deploying profanity_check Lambda..."
ensure_lambda profanity_check lambdas/profanity_check 60 "${PIPELINE_ENV}"
PROFANITY_CHECK_ARN="$(${AWS} lambda get-function --function-name profanity_check --query 'Configuration.FunctionArn' --output text)"
${AWS} s3api put-bucket-notification-configuration \
  --bucket ministack-reviews-preprocessed \
  --notification-configuration "{\"LambdaFunctionConfigurations\": [{\"LambdaFunctionArn\": \"${PROFANITY_CHECK_ARN}\", \"Events\": [\"s3:ObjectCreated:*\"]}]}"

echo "Deploying sentiment_analysis Lambda..."
ensure_lambda sentiment_analysis lambdas/sentiment_analysis 60 "${PIPELINE_ENV}"
SENTIMENT_ANALYSIS_ARN="$(${AWS} lambda get-function --function-name sentiment_analysis --query 'Configuration.FunctionArn' --output text)"
${AWS} s3api put-bucket-notification-configuration \
  --bucket ministack-reviews-profanity-checked \
  --notification-configuration "{\"LambdaFunctionConfigurations\": [{\"LambdaFunctionArn\": \"${SENTIMENT_ANALYSIS_ARN}\", \"Events\": [\"s3:ObjectCreated:*\"]}]}"

echo "Creating the static S3 webapp..."
${AWS} s3 website s3://webapp --index-document index.html
${AWS} s3 sync --delete ./website s3://webapp --exclude ".ipynb_checkpoints/*"

echo "Setup complete."
echo "Public web app URL: ${PUBLIC_BASE_URL}/webapp/index.html"
echo "Public presign URL: ${PUBLIC_BASE_URL}/2015-03-31/functions/presign/invocations"
echo "Public list URL: ${PUBLIC_BASE_URL}/2015-03-31/functions/list/invocations"