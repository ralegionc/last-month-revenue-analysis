"""Profile the Olist dataset to establish which definitional ambiguities are real."""
import duckdb, textwrap

con = duckdb.connect()
D = "/home/claude/rda/data"
for name, f in [
    ("orders", "olist_orders_dataset.csv"),
    ("items", "olist_order_items_dataset.csv"),
    ("payments", "olist_order_payments_dataset.csv"),
    ("customers", "olist_customers_dataset.csv"),
    ("reviews", "olist_order_reviews_dataset.csv"),
    ("sellers", "olist_sellers_dataset.csv"),
]:
    con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_csv_auto('{D}/{f}', header=true)")

def q(title, sql):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    print(con.execute(textwrap.dedent(sql)).df().to_string(index=False))

q("Order status distribution", """
    SELECT order_status, count(*) n,
           round(100.0*count(*)/sum(count(*)) over (), 3) pct
    FROM orders GROUP BY 1 ORDER BY n DESC
""")

q("Timestamp availability by status (null counts)", """
    SELECT order_status,
           count(*) n,
           sum(order_purchase_timestamp IS NULL)::int null_purchase,
           sum(order_approved_at IS NULL)::int null_approved,
           sum(order_delivered_carrier_date IS NULL)::int null_carrier,
           sum(order_delivered_customer_date IS NULL)::int null_delivered
    FROM orders GROUP BY 1 ORDER BY n DESC
""")

q("Do orders have items? (items coverage by status)", """
    SELECT o.order_status, count(*) n_orders,
           sum(CASE WHEN i.order_id IS NULL THEN 1 ELSE 0 END)::int orders_without_items
    FROM orders o LEFT JOIN (SELECT DISTINCT order_id FROM items) i USING (order_id)
    GROUP BY 1 ORDER BY n_orders DESC
""")

q("Multi-seller and multi-item orders", """
    WITH a AS (
      SELECT order_id, count(*) n_items, count(DISTINCT seller_id) n_sellers
      FROM items GROUP BY 1)
    SELECT
      count(*) orders_with_items,
      sum(n_items > 1)::int multi_item,
      round(100.0*sum(n_items > 1)/count(*),2) pct_multi_item,
      sum(n_sellers > 1)::int multi_seller,
      round(100.0*sum(n_sellers > 1)/count(*),2) pct_multi_seller
    FROM a
""")

q("items(price+freight) vs payments(payment_value): order-level discrepancy", """
    WITH it AS (SELECT order_id, sum(price) price, sum(freight_value) freight FROM items GROUP BY 1),
         pa AS (SELECT order_id, sum(payment_value) paid FROM payments GROUP BY 1)
    SELECT
      count(*) n_orders_both,
      sum(abs((price+freight) - paid) < 0.01)::int exact_match,
      round(100.0*sum(abs((price+freight) - paid) < 0.01)/count(*),2) pct_exact,
      round(sum(price+freight),2) total_items_value,
      round(sum(paid),2) total_paid,
      round(100.0*(sum(paid)-sum(price+freight))/sum(price+freight),3) pct_diff
    FROM it JOIN pa USING (order_id)
""")

q("Payment types (vouchers are the usual culprit)", """
    SELECT payment_type, count(*) n, round(sum(payment_value),2) total
    FROM payments GROUP BY 1 ORDER BY total DESC
""")

q("Orders present in payments but not items, and vice versa", """
    SELECT
      (SELECT count(*) FROM (SELECT DISTINCT order_id FROM payments EXCEPT SELECT DISTINCT order_id FROM items)) pay_no_items,
      (SELECT count(*) FROM (SELECT DISTINCT order_id FROM items EXCEPT SELECT DISTINCT order_id FROM payments)) items_no_pay
""")

q("Month coverage under each timestamp anchor (purchase)", """
    SELECT strftime(order_purchase_timestamp, '%Y-%m') ym, count(*) n
    FROM orders GROUP BY 1 ORDER BY 1
""")

q("Timestamp ordering violations", """
    SELECT
      sum(order_approved_at < order_purchase_timestamp)::int approved_before_purchase,
      sum(order_delivered_customer_date < order_purchase_timestamp)::int delivered_before_purchase,
      sum(order_delivered_customer_date < order_delivered_carrier_date)::int delivered_before_carrier,
      sum(order_delivered_customer_date > order_estimated_delivery_date)::int delivered_late
    FROM orders
""")

q("Freight share of gross merchandise value", """
    SELECT round(sum(price),2) price, round(sum(freight_value),2) freight,
           round(100.0*sum(freight_value)/sum(price+freight_value),2) freight_pct_of_gross
    FROM items
""")

q("Cancelled/unavailable orders that still have payments recorded", """
    SELECT o.order_status, count(DISTINCT o.order_id) n_orders,
           round(sum(p.payment_value),2) total_payment_value
    FROM orders o JOIN payments p USING (order_id)
    WHERE o.order_status IN ('canceled','unavailable')
    GROUP BY 1
""")

q("Customer identity: customer_id vs customer_unique_id", """
    SELECT count(*) n_rows, count(DISTINCT customer_id) n_customer_id,
           count(DISTINCT customer_unique_id) n_unique
    FROM customers
""")
