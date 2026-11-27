----------------------------------
---------- EXERCISE 6.1 ----------
----------------------------------

----- Query -----
WITH RECURSIVE
product_unique_sales_dates AS (
  SELECT
    product_number,
    COUNT(DISTINCT date) AS n_unique_sales_dates
  FROM go_daily_sales
  GROUP BY product_number
),
one_distinct_date_per_product AS (
  SELECT DISTINCT
    product_number,
    date
  FROM go_daily_sales
),
streak AS (
  -- Base case: streak_length = 1 for every dates
  SELECT
    product_number,
    date,
    1 AS streak_length
  FROM one_distinct_date_per_product

  UNION

  -- Recursion: streak_length +1 and go to the next day
  SELECT
    st.product_number,
    dp.date,
    st.streak_length + 1 AS streak_length
  FROM streak st
  JOIN one_distinct_date_per_product dp
    ON st.product_number = dp.product_number
    AND dp.date = st.date + INTERVAL '1 day'
),
longest_streak AS (
  SELECT
    product_number,
    MAX(streak_length) AS longest_streak
  FROM streak
  GROUP BY product_number
)
SELECT
  ls.*,
  pusd.n_unique_sales_dates
FROM longest_streak ls
JOIN product_unique_sales_dates pusd
  ON ls.product_number = pusd.product_number
ORDER BY ls.longest_streak DESC;


----- For Testing -----
SELECT *
FROM go_daily_sales
WHERE product_number = 	151120
ORDER BY date ASC;
