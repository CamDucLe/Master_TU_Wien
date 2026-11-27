REVIEWS_FILE_PATH='hdfs:///dic_shared/amazon-reviews/full/reviews_devset.json' \
STOPWORDS_FILE_PATH='data/stopwords.txt' \
SPARK_LOG_LEVEL='ERROR' \
OUTPUT_FILE_PATH="hdfs:///user/$USER/assignment2/output_ds.txt" \
spark-submit \
  --master yarn \
  --deploy-mode client \
  --name part2-dataframes \
  src/part2_dataframes.py

hdfs dfs -cat "/user/$USER/assignment2/output_ds.txt" | head -n 20
