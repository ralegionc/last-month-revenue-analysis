"""
Metric engine: builds the order-level base table once, then evaluates every
admissible definition against it.

Design note: every definition is a *parameterisation of one query*, not a
separate hand-written query. Hand-writing 64 variants is how definition drift
gets into an audit of definition drift.
"""
import os
import duckdb
import pandas as pd

from definitions import (ANCHORS, STATUS, enumerate_definitions)

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(os.path.dirname(__file__), "..", "out")

# Months are "complete" if the purchase-anchored order count clears this bar.
# Olist's first and last months are partial exports (4, 324, 1, 16 and 4 orders);
# including them would manufacture spread that is an artefact of the export
# boundary rather than of definition choice.
COMPLETE_MONTH_MIN_ORDERS = 500


def connect():
    con = duckdb.connect()
    for name, f in [
        ("orders_raw", "olist_orders_dataset.csv"),
        ("items_raw", "olist_order_items_dataset.csv"),
        ("payments_raw", "olist_order_payments_dataset.csv"),
        ("customers_raw", "olist_customers_dataset.csv"),
    ]:
        con.execute(
            f"CREATE VIEW {name} AS SELECT * FROM "
            f"read_csv_auto('{os.path.join(DATA, f)}', header=true)")
    return con


def build_base(con):
    """One row per order, with every quantity any admissible definition needs."""
    con.execute("""
        CREATE TABLE base AS
        WITH it AS (
            SELECT order_id,
                   sum(price)         AS items_price,
                   sum(freight_value) AS items_freight,
                   count(*)           AS n_items,
                   count(DISTINCT seller_id) AS n_sellers
            FROM items_raw GROUP BY 1
        ), pa AS (
            SELECT order_id,
                   sum(payment_value) AS pay_total,
                   sum(CASE WHEN payment_type = 'voucher'
                            THEN payment_value ELSE 0 END) AS pay_voucher
            FROM payments_raw GROUP BY 1
        )
        SELECT
            o.order_id,
            o.order_status                     AS status,
            c.customer_unique_id,
            o.customer_id,
            o.order_purchase_timestamp         AS ts_purchase,
            o.order_approved_at                AS ts_approved,
            o.order_delivered_carrier_date     AS ts_carrier,
            o.order_delivered_customer_date    AS ts_delivered,
            COALESCE(it.items_price, 0)        AS items_price,
            COALESCE(it.items_freight, 0)      AS items_freight,
            COALESCE(it.n_items, 0)            AS n_items,
            COALESCE(it.n_sellers, 0)          AS n_sellers,
            COALESCE(pa.pay_total, 0)          AS pay_total,
            COALESCE(pa.pay_voucher, 0)        AS pay_voucher,
            (it.order_id IS NOT NULL)          AS has_items,
            (pa.order_id IS NOT NULL)          AS has_payments
        FROM orders_raw o
        LEFT JOIN it USING (order_id)
        LEFT JOIN pa USING (order_id)
        LEFT JOIN customers_raw c USING (customer_id)
    """)

    # Referential integrity: orders is the master. If items or payments contain
    # order_ids absent from orders, the LEFT JOINs above silently drop revenue.
    orphans = con.execute("""
        SELECT
          (SELECT count(*) FROM (SELECT DISTINCT order_id FROM items_raw
                                 EXCEPT SELECT order_id FROM orders_raw)) AS item_orphans,
          (SELECT count(*) FROM (SELECT DISTINCT order_id FROM payments_raw
                                 EXCEPT SELECT order_id FROM orders_raw)) AS pay_orphans,
          (SELECT count(*) FROM base WHERE customer_unique_id IS NULL) AS cust_unmatched
    """).fetchone()
    assert orphans == (0, 0, 0), f"referential integrity failed: {orphans}"

    n = con.execute("SELECT count(*), count(DISTINCT order_id) FROM base").fetchone()
    assert n[0] == n[1], "base table is not one row per order"
    return n[0]


def complete_months(con):
    """Months to include in spread statistics, and why."""
    df = con.execute(f"""
        SELECT strftime(ts_purchase, '%Y-%m') AS ym, count(*) AS n_orders
        FROM base GROUP BY 1 ORDER BY 1
    """).df()
    df["complete"] = df["n_orders"] >= COMPLETE_MONTH_MIN_ORDERS
    return df


def revenue_expr(d):
    if d["source"] == "items":
        return ("items_price + items_freight" if d["freight"] == "incl"
                else "items_price")
    return ("pay_total" if d["voucher"] == "incl" else "pay_total - pay_voucher")


def evaluate(con, definitions):
    """Monthly revenue, order count and AOV for every definition."""
    frames = []
    for d in definitions:
        anchor_col = ANCHORS[d["anchor"]]["col"]
        where = STATUS[d["status"]]["where"]
        rev = revenue_expr(d)
        sql = f"""
            SELECT strftime({anchor_col}, '%Y-%m') AS ym,
                   sum({rev})                      AS revenue,
                   count(*)                        AS n_orders
            FROM base
            WHERE {anchor_col} IS NOT NULL AND ({where})
            GROUP BY 1
        """
        df = con.execute(sql).df()
        df["def_id"] = d["def_id"]
        for k in ("anchor", "source", "freight", "voucher", "status"):
            df[k] = d[k]
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["aov"] = out["revenue"] / out["n_orders"]
    return out


def delivery_time(con):
    """Delivery-time definitions: which clock starts, and calendar vs business days."""
    rows = []
    starts = {"purchase": "ts_purchase", "approved": "ts_approved",
              "carrier": "ts_carrier"}
    for sname, scol in starts.items():
        for daytype in ("calendar", "business"):
            if daytype == "calendar":
                dur = f"date_diff('day', {scol}, ts_delivered)"
            else:
                # business days: calendar days minus weekend days in the span
                dur = (f"date_diff('day', {scol}, ts_delivered) - "
                       f"2 * (date_diff('day', {scol}, ts_delivered) / 7)")
            for scope, where in (("delivered_only", "status = 'delivered'"),
                                 ("any_delivered_ts", "TRUE")):
                df = con.execute(f"""
                    SELECT strftime(ts_purchase, '%Y-%m') AS ym,
                           avg({dur}) AS mean_days,
                           median({dur}) AS median_days,
                           count(*) AS n
                    FROM base
                    WHERE ts_delivered IS NOT NULL AND {scol} IS NOT NULL
                      AND ({where}) AND {dur} >= 0
                    GROUP BY 1
                """).df()
                df["def_id"] = f"{sname}|{daytype}|{scope}"
                df["start"] = sname
                df["daytype"] = daytype
                df["scope"] = scope
                rows.append(df)
    return pd.concat(rows, ignore_index=True)


def repeat_rate(con):
    """Repeat-purchase rate under the two available customer identity keys."""
    out = []
    for key, label in (("customer_id", "Per-order customer_id"),
                       ("customer_unique_id", "Person-level customer_unique_id")):
        for scope, where in (("all", "TRUE"),
                             ("ex_canceled_unavail",
                              "status NOT IN ('canceled','unavailable')")):
            r = con.execute(f"""
                WITH c AS (
                    SELECT {key} AS k, count(*) AS n_orders
                    FROM base WHERE {where} GROUP BY 1
                )
                SELECT count(*) AS n_customers,
                       sum(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) AS n_repeat,
                       100.0 * sum(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END)
                             / count(*) AS repeat_rate_pct
                FROM c
            """).df()
            r["def_id"] = f"{key}|{scope}"
            r["key"] = key
            r["key_label"] = label
            r["scope"] = scope
            out.append(r)
    return pd.concat(out, ignore_index=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    con = connect()
    n_orders = build_base(con)
    defs = enumerate_definitions()

    months = complete_months(con)
    rev = evaluate(con, defs)
    dlv = delivery_time(con)
    rpt = repeat_rate(con)

    months.to_csv(f"{OUT}/months.csv", index=False)
    rev.to_csv(f"{OUT}/revenue_by_definition.csv", index=False)
    dlv.to_csv(f"{OUT}/delivery_by_definition.csv", index=False)
    rpt.to_csv(f"{OUT}/repeat_by_definition.csv", index=False)

    print(f"orders in base table      : {n_orders:,}")
    print(f"admissible definitions    : {len(defs)}")
    print(f"complete months           : {int(months['complete'].sum())} "
          f"of {len(months)}")
    print(f"revenue rows written      : {len(rev):,}")
    print(f"delivery definitions      : {dlv['def_id'].nunique()}")
    print(f"repeat-rate definitions   : {rpt['def_id'].nunique()}")


if __name__ == "__main__":
    main()
