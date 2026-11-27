----------------------------------
---------- EXERCISE 2.2 ----------
----------------------------------

SELECT * FROM go_products WHERE product_number = 1110;

ALTER TABLE go_products ADD COLUMN last_sale_date DATE;

-- Function --
CREATE OR REPLACE FUNCTION update_last_sale_date()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.last_sale_date IS NOT NULL AND NEW.last_sale_date < OLD.last_sale_date THEN
    RAISE EXCEPTION 'UPDATE is not allowed';
  ELSE
    RAISE NOTICE 'UPDATE was successfull';
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION auto_maintain_last_sale_date()
RETURNS TRIGGER AS $$
BEGIN
  RAISE NOTICE 'Start execution trigger auto_maintain_last_sale_date';

  UPDATE go_products
  SET last_sale_date = CURRENT_DATE
  WHERE product_number IN (
    SELECT DISTINCT product_number
    FROM new_daily_sales
  );
  
  RAISE NOTICE 'END execution trigger auto_maintain_last_sale_date';

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;


-- Trigger --
CREATE TRIGGER trigger_update_last_sale_date
BEFORE UPDATE OF last_sale_date ON go_products
FOR EACH ROW
EXECUTE FUNCTION update_last_sale_date();

CREATE TRIGGER trigger_auto_maintain_last_sale_date
AFTER INSERT ON go_daily_sales
REFERENCING NEW TABLE AS new_daily_sales
FOR EACH STATEMENT
EXECUTE FUNCTION auto_maintain_last_sale_date();


----- For testing -----
-- new products that not exist in go_products --
INSERT INTO go_daily_sales
(retailer_code, product_number, order_method_code, date, quantity, unit_price, unit_sale_price)
VALUES
(111, 1, 1, CURRENT_DATE, 1, 10.00, 9.50),
(112, 2, 1, CURRENT_DATE, 2, 20.00, 19.00),
(113, 1, 2, CURRENT_DATE, 3, 10.00, 9.00);

SELECT * FROM go_daily_sales ORDER BY product_number ASC LIMIT 3;
SELECT * FROM go_products ORDER BY product_number ASC LIMIT 3;

-- products exist in go_product --
INSERT INTO go_daily_sales
(retailer_code, product_number, order_method_code, date, quantity, unit_price, unit_sale_price)
VALUES
(111, 1110, 1, CURRENT_DATE, 1, 10.00, 9.50),
(112, 2110, 1, CURRENT_DATE, 2, 20.00, 19.00);

INSERT INTO go_daily_sales
(retailer_code, product_number, order_method_code, date, quantity, unit_price, unit_sale_price)
VALUES
(111, 3110, 1, CURRENT_DATE, 1, 10.00, 9.50);

SELECT * FROM go_daily_sales ORDER BY product_number ASC LIMIT 6;
SELECT * FROM go_products ORDER BY product_number ASC LIMIT 6;



