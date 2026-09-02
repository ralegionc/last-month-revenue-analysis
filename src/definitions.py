"""
The admissible definition space for "last month's revenue".

ADMISSIBILITY RULE
------------------
A definition is admissible if and only if you can state a concrete business
context in which a competent analyst would *prefer* it over the alternatives.
"Someone might do this by accident" is not sufficient. Definitions that fail
this test are listed in REJECTED with the reason, and are excluded from every
spread statistic in this study.

This rule exists because the headline number of a definition-sensitivity study
is trivially inflatable: throw in absurd variants and the spread grows without
bound. Policing admissibility honestly is what makes the number mean anything.
"""

# ----------------------------------------------------------------------------
# Dimension 1: period anchor -- which event assigns an order to a month
# ----------------------------------------------------------------------------
ANCHORS = {
    "purchase": dict(
        col="ts_purchase",
        label="Purchase timestamp",
        rationale="Bookings view. When the customer committed. Standard for "
                  "demand/marketing analysis and the only anchor available for "
                  "every order.",
    ),
    "approved": dict(
        col="ts_approved",
        label="Payment approval",
        rationale="Cash/finance view. When payment cleared and the order became "
                  "real to the business. Standard for payment-ops reporting.",
    ),
    "carrier": dict(
        col="ts_carrier",
        label="Carrier handoff",
        rationale="Fulfilment view. When goods left the seller. Used where "
                  "revenue is recognised at shipment (FOB shipping point).",
    ),
    "delivered": dict(
        col="ts_delivered",
        label="Delivery to customer",
        rationale="Accounting view. Control of the good transfers on delivery, so "
                  "this is the anchor closest to revenue recognition under "
                  "IFRS 15 / ASC 606 for a goods marketplace.",
    ),
}

# ----------------------------------------------------------------------------
# Dimension 2: revenue source
# ----------------------------------------------------------------------------
SOURCES = {
    "items": dict(
        label="Order line items",
        rationale="Merchandise view. Sums the priced lines actually sold. This is "
                  "what a category or seller P&L rolls up from.",
    ),
    "payments": dict(
        label="Payment records",
        rationale="Cash view. Sums what customers actually paid, including orders "
                  "that never produced line items. Reconciles to the payment "
                  "processor.",
    ),
}

# ----------------------------------------------------------------------------
# Dimension 3: freight (items source only -- payments are not separable)
# ----------------------------------------------------------------------------
FREIGHT = {
    "incl": dict(label="Freight included",
                 rationale="Gross merchandise value. Shipping is revenue to the "
                           "marketplace and is what the customer was charged."),
    "excl": dict(label="Freight excluded",
                 rationale="Product revenue. Shipping is a pass-through cost, so "
                           "excluding it is standard for margin and mix analysis."),
}

# ----------------------------------------------------------------------------
# Dimension 4: voucher treatment (payments source only)
# ----------------------------------------------------------------------------
VOUCHERS = {
    "incl": dict(label="Vouchers counted",
                 rationale="Total consideration received for the order, regardless "
                           "of tender type."),
    "excl": dict(label="Vouchers excluded",
                 rationale="Vouchers are contra-revenue -- a discount previously "
                           "granted, not new cash. Excluding them avoids "
                           "double-counting against the promotion that issued them."),
}

# ----------------------------------------------------------------------------
# Dimension 5: order status scope
# ----------------------------------------------------------------------------
STATUS = {
    "all": dict(
        label="All statuses",
        where="TRUE",
        rationale="Gross bookings. Nothing is retroactively removed, so a month's "
                  "number never changes after the fact.",
    ),
    "ex_canceled": dict(
        label="Exclude cancelled",
        where="status <> 'canceled'",
        rationale="Cancelled orders will not be fulfilled, so counting them "
                  "overstates the business.",
    ),
    "ex_canceled_unavail": dict(
        label="Exclude cancelled + unavailable",
        where="status NOT IN ('canceled','unavailable')",
        rationale="Both terminal non-fulfilment states. The conventional "
                  "'net bookings' scope.",
    ),
    "delivered_only": dict(
        label="Delivered only",
        where="status = 'delivered'",
        rationale="Conservative recognised revenue: count only what demonstrably "
                  "reached the customer.",
    ),
}

# ----------------------------------------------------------------------------
# Rejected -- documented so the admissibility rule is auditable
# ----------------------------------------------------------------------------
REJECTED = [
    ("Anchor on order_estimated_delivery_date",
     "It is a forecast, not an event. Anchoring realised revenue to a prediction "
     "means the month a sale lands in can change without anything happening."),
    ("Anchor on shipping_limit_date",
     "A seller SLA deadline, not a transaction event. It exists even for orders "
     "that were never shipped."),
    ("Anchor on review_creation_date",
     "Reviews are optional and arrive arbitrarily late; most revenue would be "
     "unassignable and the rest biased toward customers who review."),
    ("Revenue = sum(payment_value * payment_installments)",
     "Double counts. payment_value is already the full amount; installments only "
     "describe the schedule."),
    ("Revenue = sum over payment rows without deduplicating order_id",
     "Not a definition, just a fan-out join bug. Admissible definitions must be "
     "defensible on purpose."),
    ("Freight toggle applied to the payments source",
     "payment_value is not decomposable into product and freight components, so "
     "the toggle is undefined there rather than merely unusual."),
    ("Count each order line as an order for AOV",
     "A unit-of-analysis error, not a revenue definition. 9.9% of orders are "
     "multi-item, so this silently redefines the denominator."),
]


def enumerate_definitions():
    """Full factorial over the admissible space, respecting source interactions."""
    defs = []
    for a in ANCHORS:
        for s in STATUS:
            for f in FREIGHT:
                defs.append(dict(anchor=a, source="items", freight=f,
                                 voucher="n/a", status=s))
            for v in VOUCHERS:
                defs.append(dict(anchor=a, source="payments", freight="n/a",
                                 voucher=v, status=s))
    for i, d in enumerate(defs):
        d["def_id"] = (f"{d['anchor']}|{d['source']}|"
                       f"{d['freight'] if d['source']=='items' else d['voucher']}|"
                       f"{d['status']}")
        d["idx"] = i
    return defs


if __name__ == "__main__":
    ds = enumerate_definitions()
    print(f"{len(ds)} admissible definitions of monthly revenue")
    print(f"{len(REJECTED)} rejected definitions documented")
