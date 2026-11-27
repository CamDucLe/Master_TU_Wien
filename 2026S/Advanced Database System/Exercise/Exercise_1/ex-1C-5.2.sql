----------------------------------
---------- EXERCISE 5.2 ----------
----------------------------------

-- CREATE MATERIALIZED VIEW monthly_product_sales AS(
--   WITH
--   tmp_go_daily_sales AS (  -- calculate total_sales for each record
--     SELECT
--       *,
--       EXTRACT(YEAR FROM date) AS year,
--       EXTRACT(MONTH FROM date) AS month,
--       (quantity * unit_sale_price)::DECIMAL AS total_sales
--     FROM go_daily_sales
--   )
--   SELECT
--     product_number,
--     year,
--     month,
--     SUM(total_sales) AS total_sales
--   FROM
--     tmp_go_daily_sales
--   GROUP BY
--     product_number, year, month
--   ORDER BY
--     product_number, year, month
-- );

WITH top_selling_month AS(
  SELECT
    *,
    RANK() OVER (PARTITION BY product_number ORDER BY total_sales DESC) AS rank
  FROM monthly_product_sales
  WHERE year = 2018
)
SELECT *
FROM top_selling_month
WHERE rank = 1;


----- For testing -----
SELECT
  product_number,
  EXTRACT(YEAR FROM date) AS year,
  EXTRACT(MONTH FROM date) AS month,
  SUM((quantity * unit_sale_price)::DECIMAL) AS total_sales
FROM go_daily_sales
WHERE
    product_number IN (1110, 2110, 3110)
    AND EXTRACT(YEAR FROM date) = 2018
GROUP BY product_number, EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
ORDER BY product_number, year, month;
