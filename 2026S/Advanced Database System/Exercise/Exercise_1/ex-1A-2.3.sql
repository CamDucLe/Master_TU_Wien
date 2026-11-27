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
