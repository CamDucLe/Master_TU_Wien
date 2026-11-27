----------------------------------
---------- EXERCISE 2.1 ----------
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

-- Trigger --
CREATE TRIGGER trigger_update_last_sale_date
BEFORE UPDATE OF last_sale_date ON go_products
FOR EACH ROW
EXECUTE FUNCTION update_last_sale_date();


----- For testing -----
--Get product --
SELECT * FROM go_products WHERE product_number = 1110;

-- Update last_sale_date correctly --
UPDATE go_products
SET last_sale_date = DATE('2025-03-27')
WHERE product_number = 1110;

-- Check after updating --
SELECT * FROM go_products WHERE product_number = 1110;

-- Update last_sale_date correctly --
UPDATE go_products
SET last_sale_date = DATE('2026-03-27')
WHERE product_number = 1110;

-- Check after updating --
SELECT * FROM go_products WHERE product_number = 1110;

-- Update last_sale_date wrongly --
UPDATE go_products
SET last_sale_date = DATE('2024-03-27')
WHERE product_number = 1110;
