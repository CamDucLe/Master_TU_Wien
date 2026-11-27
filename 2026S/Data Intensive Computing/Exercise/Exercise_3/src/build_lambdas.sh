#!/usr/bin/env bash
set -e

BASE_DIR="$(pwd)"

LAMBDA_DIRS=(
  "list"
  "preprocessing"
  "presign"
  "profanity_check"
  "sentiment_analysis"
)

# On macOS, ministack workers run as native host processes so we need native
# binaries. On Linux (LBD cluster) we also install natively since ministack
# runs in the same OS environment.
pip_install_deps() {
  local requirements_file="$1"
  local target_dir="$2"

  if [ "$(uname -s)" = "Darwin" ]; then
    pip install -r "${requirements_file}" -t "${target_dir}" --no-cache-dir
  else
    pip install -r "${requirements_file}" -t "${target_dir}" --no-cache-dir \
      --platform manylinux2014_x86_64 --only-binary=:all:
  fi
}

echo "Building all Lambdas cleanly..."

for dir in "${LAMBDA_DIRS[@]}"; do
  echo ""
  echo "Building $dir..."

  LAMBDA_PATH="$BASE_DIR/lambdas/$dir"

  if [ ! -d "$LAMBDA_PATH" ]; then
    echo "Directory not found: $LAMBDA_PATH — skipping."
    continue
  fi

  cd "$LAMBDA_PATH"

  rm -rf package lambda.zip __pycache__
  mkdir package

  if [ -f requirements.txt ]; then
    pip_install_deps requirements.txt package
  fi

  pip install boto3 -t package --no-cache-dir

  cp handler.py package/

  cd package
  zip -r ../lambda.zip . > /dev/null
  cd "$BASE_DIR"

  echo "Built $dir successfully."
done

echo ""
echo "All Lambdas built."