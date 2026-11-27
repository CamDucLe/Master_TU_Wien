----------------------------------
---------- EXERCISE 1.2 ----------
----------------------------------

----- Rewrite the function using a cursor to improve its efficiency -----
CREATE OR REPLACE FUNCTION get_monthly_sales(product_id INT, year INT)
RETURNS TABLE (
    month INT,
    total_sales DECIMAL
) AS $$
DECLARE
    month INT;
    m_cursor CURSOR FOR
      SELECT generate_series(1,12);
BEGIN
    -- Handle invalid input
    IF product_id IS NULL THEN
        RAISE NOTICE 'product_id must be an integer';
        RETURN;
    ELSIF year IS NULL THEN
        RAISE NOTICE 'year must be an integer';
        RETURN;
    END IF;

    OPEN m_cursor;

    LOOP
        FETCH m_cursor INTO month;
        EXIT WHEN NOT FOUND;  -- safely exit loop

        RETURN QUERY
        SELECT
            month,
            COALESCE(SUM(quantity * unit_sale_price)::DECIMAL, 0) AS total_sales
        FROM go_daily_sales
        WHERE product_number = get_monthly_sales.product_id
          AND EXTRACT(YEAR FROM date) = get_monthly_sales.year
          AND EXTRACT(MONTH FROM date) = month;
    END LOOP;

    CLOSE m_cursor;
END;
$$ LANGUAGE plpgsql;


--- For testing -----
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

-- Raise error
SELECT * FROM get_monthly_sales(NULL, 2025);
SELECT * FROM get_monthly_sales(115110, NULL);
