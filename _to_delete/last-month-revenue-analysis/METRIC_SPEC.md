# Metric specification: monthly revenue and companions

*The definition this audit recommends standardising on, written the way a
semantic layer would enforce it. Version 1.0 — 14 August 2026.*

A specification is only useful if it names the choices it is making **and the
alternatives it is rejecting**. Each section below states the decision, the SQL,
and what it deliberately is not.

---

## 1. `revenue_monthly` — the operating number

| Choice | Decision |
|---|---|
| Period anchor | `order_purchase_timestamp` |
| Measure | line-item `price + freight_value` (gross merchandise value) |
| Status scope | exclude `canceled` and `unavailable` |
| Unit | order |
| Currency | BRL, no conversion |

```sql
SELECT strftime(o.order_purchase_timestamp, '%Y-%m') AS period,
       sum(i.price + i.freight_value)                AS revenue_brl
FROM orders o
JOIN order_items i USING (order_id)
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY 1;
```

**Why the purchase anchor.** It is the only timestamp populated for every order
(approval is missing on 160, carrier handoff on 1,783, delivery on 2,965); it never
revises after month-end; and it matches the demand question an operating review is
usually asking. It carries 96% of the growth-rate variance in the audit, so this
is the choice that had to be made first.

**Why freight is included.** The customer paid it and the marketplace received it.
Excluding it is equally defensible for margin work — but it must then be called
`product_revenue_monthly`, never `revenue`.

**Why cancelled and unavailable are excluded.** Both are terminal non-fulfilment
states. This costs 1.24% of orders and, per the audit, changes essentially
nothing — it is specified for the sake of having *an* answer, not because it
matters.

**What this is not.** It is not a recognised-revenue figure. See §2.

---

## 2. `recognised_revenue_monthly` — the finance number

Maintained **in parallel**, under a **different name**, and never compared
month-to-month against §1.

```sql
SELECT strftime(o.order_delivered_customer_date, '%Y-%m') AS period,
       sum(i.price + i.freight_value)                     AS recognised_revenue_brl
FROM orders o
JOIN order_items i USING (order_id)
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY 1;
```

Control of goods transfers on delivery, so this is the correct basis under
IFRS 15 / ASC 606. In the audit window the two series differ by up to 36% in a typical month (and 72% in the ramp month of January 2017) — that gap is
real timing, not error, and the parallel series exists so nobody has to argue
about which one is "the" revenue.

**Mandatory caveat on any surface displaying this metric:** the current and prior
month are incomplete and will revise upward as in-flight orders are delivered.

---

## 3. `orders_monthly` and `aov_monthly`

```sql
-- unit is the ORDER, never the line item: 9.94% of orders are multi-item
SELECT strftime(o.order_purchase_timestamp, '%Y-%m') AS period,
       count(DISTINCT o.order_id)                    AS orders,
       sum(i.price + i.freight_value)
         / count(DISTINCT o.order_id)                AS aov_brl
FROM orders o
JOIN order_items i USING (order_id)
WHERE o.order_status NOT IN ('canceled', 'unavailable')
GROUP BY 1;
```

`count(DISTINCT order_id)` is deliberate. A plain `count(*)` after the join to
`order_items` counts lines, inflating the denominator by 14.2% and deflating AOV
accordingly. This is the most common silent error in the dataset.

---

## 4. `repeat_purchase_rate`

```sql
-- customer_unique_id is the PERSON. customer_id is issued per order and will
-- return exactly 0% forever.
WITH per_customer AS (
    SELECT c.customer_unique_id, count(DISTINCT o.order_id) AS n_orders
    FROM orders o
    JOIN customers c USING (customer_id)
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1
)
SELECT 100.0 * count(*) FILTER (WHERE n_orders > 1) / count(*) AS repeat_rate_pct
FROM per_customer;
```

**This is a correctness rule, not a preference.** `customer_id` yields 0.00% by
construction. Any dashboard reporting a repeat rate of exactly zero is reporting a
bug. A CI check should assert the rate is strictly positive.

---

## 5. `delivery_days`

| Choice | Decision |
|---|---|
| Clock start | `order_purchase_timestamp` |
| Clock end | `order_delivered_customer_date` |
| Day count | calendar days |
| Scope | orders with a delivery timestamp |

```sql
SELECT strftime(order_purchase_timestamp, '%Y-%m') AS period,
       median(date_diff('day', order_purchase_timestamp,
                        order_delivered_customer_date)) AS delivery_days_p50
FROM orders
WHERE order_delivered_customer_date IS NOT NULL
GROUP BY 1;
```

Purchase-to-delivery calendar days is the customer's experience, which is the
thing worth managing. Carrier-handoff-to-delivery in business days measures
carrier performance and reads ~4 days shorter — a legitimate metric that must
carry its own name (`carrier_transit_days`).

**Report the median, not the mean.** Delivery times are right-skewed; the mean is
pulled by a tail of very late orders and moves for reasons unrelated to typical
experience.

---

## 6. Enforcement

1. **One definition per name.** If a variant is needed, it gets a new name. The
   failure mode this spec exists to prevent is two numbers sharing one label.
2. **Every metric surface states its anchor.** A revenue figure without a visible
   anchor is not interpretable.
3. **Revising metrics are marked as such.** §2 and any delivery-anchored series
   display an incomplete-period warning for the current and prior month.
4. **Assertions in CI:**
   - `repeat_purchase_rate > 0`
   - `orders_monthly == count(DISTINCT order_id)` (fan-out guard)
   - §1 and §2 never appear on the same axis of the same chart
5. **This spec is versioned.** A change to any definition here is a change to
   history; publish the restatement alongside it.

---

*Derived from the audit in [`REPORT.md`](REPORT.md). The audit's finding is that
choices 1 (anchor) and 2 (measure) carry essentially all of the disagreement; the
rest of this document is specified for completeness rather than because it is
load-bearing.*
