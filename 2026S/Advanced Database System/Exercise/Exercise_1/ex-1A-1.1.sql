----------------------------------
---------- EXERCISE 1.1 ----------
----------------------------------


----- Function -----
CREATE OR REPLACE FUNCTION get_monthly_sales(product_id INT, year INT)
RETURNS TABLE (
  month INT,
  total_sales DECIMAL
) AS $$
BEGIN
  -- Handle invalid input (invalid_parameter_value)
  IF product_id IS NULL THEN
    RAISE NOTICE 'product_id must be an integer';
    RETURN;
  ELSIF year IS NULL THEN
    RAISE NOTICE 'year must be an integer';
    RETURN;
  END IF;

  RETURN QUERY
  WITH
  months AS (  -- generate column month with values ranging from 1-12
    SELECT
      generate_series(1,12) AS month
  ),
  tmp_go_daily_sales AS (  -- calculate total_sales for each record
    SELECT
      product_number AS product_id,
      EXTRACT(YEAR FROM date) AS year,
      EXTRACT(MONTH FROM date) AS month,
      (quantity * unit_sale_price)::DECIMAL AS total_sales
    FROM go_daily_sales
    -- LIMIT 27
  )
  SELECT
    m.month AS month,
    COALESCE(SUM(gds.total_sales), 0) AS total_sales
  FROM months m
  LEFT JOIN tmp_go_daily_sales gds
    ON m.month = gds.month
    AND gds.product_id = get_monthly_sales.product_id
    AND gds.year = get_monthly_sales.year
  GROUP BY m.month
  ORDER BY m.month ASC;

END;
$$ LANGUAGE plpgsql;


----- For testing -----
-- Check some recrods to get a random product --
SELECT * FROM go_daily_sales LIMIT 5;

-- Get 1-month data (Janurary) of the product_number = 115110 --
SELECT
  gds.*,
  gds.quantity * gds.unit_sale_price AS total_sales,
  gp.unit_cost AS gp_unit_cost,
  gp.unit_price AS gp_unit_price,
  gp.unit_price - gp.unit_cost AS check_if_equal_to_unit_sale_price
FROM go_daily_sales gds
LEFT JOIN go_products gp
    on gds.product_number = gp.product_number
WHERE
  TRUE
  AND gds.product_number = 115110
  AND EXTRACT(MONTH FROM gds.date) = 1
  AND EXTRACT(YEAR FROM gds.date) = 2015;

-- Get 1-month data (October) of the product_number = 115110 --
SELECT
  gds.*,
  gds.quantity * gds.unit_sale_price AS total_sales
FROM go_daily_sales gds
WHERE
  TRUE
  AND gds.product_number = 115110
  AND EXTRACT(MONTH FROM gds.date) = 10
  AND EXTRACT(YEAR FROM gds.date) = 2015;

-- Should have data --
SELECT * FROM get_monthly_sales(115110, 2015);

-- ALl zero --
SELECT * FROM get_monthly_sales(115110, 2025);

-- Raise notice and return empty table
SELECT * FROM get_monthly_sales(NULL, 2025);
SELECT * FROM get_monthly_sales(115110, NULL);
