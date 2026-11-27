----------------------------------
---------- EXERCISE 5.1 ----------
----------------------------------

CREATE MATERIALIZED VIEW monthly_product_sales AS(
  WITH
  tmp_go_daily_sales AS (  -- calculate total_sales for each record
    SELECT
      *,
      EXTRACT(YEAR FROM date) AS year,
      EXTRACT(MONTH FROM date) AS month,
      (quantity * unit_sale_price)::DECIMAL AS total_sales
    FROM go_daily_sales
  )
  SELECT
    product_number,
    year,
    month,
    SUM(total_sales) AS total_sales
  FROM
    tmp_go_daily_sales
  GROUP BY
    product_number, year, month
  ORDER BY
    product_number, year, month
);

----- For testing -----
SELECT * FROM monthly_product_sales LIMIT 3;
WITH a AS (
  SELECT (quantity * unit_sale_price)::DECIMAL AS total_sales
  FROM go_daily_sales
  WHERE
    product_number =  1110
    AND EXTRACT(YEAR FROM date) = 2015
    AND EXTRACT(MONTH FROM date) = 3
)
SELECT SUM(total_sales) FROM a;
