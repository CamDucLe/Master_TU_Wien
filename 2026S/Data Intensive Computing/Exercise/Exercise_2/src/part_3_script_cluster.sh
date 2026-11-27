REVIEWS_FILE_PATH='hdfs:///dic_shared/amazon-reviews/full/reviews_devset.json' \
STOPWORDS_FILE_PATH='data/stopwords.txt' \
SPARK_LOG_LEVEL='ERROR' \
OUTPUT_PARAMS_FILE_PATH="hdfs:///user/$USER/assignment2/part3_best_params.txt" \
spark-submit \
  --master yarn \
  --deploy-mode client \
  --name part3-classification \
  src/part3_classification.py

hdfs dfs -cat "/user/$USER/assignment2/part3_best_params.txt" | head -n 20
