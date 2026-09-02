# Memo: "Last month's revenue" is not one number, and the fix is one line of policy

**To:** whoever owns the revenue metric
**Date:** 14 August 2026
**Dataset:** Olist Brazilian e-commerce, 99,441 orders, Jan 2017 – Aug 2018

---

## Recommendation

**Standardise the period anchor first, and standardise it to purchase timestamp for
operating reviews.** Do that one thing and the share of month-over-month growth
calls that reverse on definition choice falls from **42% to 5%**.

Standardising anything else first — the freight policy, the cancellation rule —
buys you almost nothing on growth. Those are the arguments teams actually have,
and they are the wrong arguments.

## What we found

Across 64 defensible definitions of monthly revenue, the same data supports
answers from **R$838,577 to R$1,347,361** for August 2018. That is a gap of
**R$508,784 — 47% of the mean, and 1.61x from lowest to highest.** Every one of
those definitions is one a competent analyst could defend; the inadmissible ones
were excluded up front and are documented.

Typical months are tighter but not tight: **median spread 27.5%** across 20
months, never below 18%.

The consequential finding is not the spread, it's what the spread does to
decisions. **Eight of nineteen month-over-month comparisons (42%) contain a
contradiction** — one defensible definition says the business grew, another says
it shrank, over the same period, from the same rows.

## Why the anchor is the lever

Two dimensions dominate, and they break different numbers:

| Choice | Share of variance in the *level* | Share of variance in *growth* |
|---|---|---|
| Period anchor (which timestamp assigns an order to a month) | 38% | **96%** |
| Revenue measure (freight in/out, items vs. payments) | **60%** | 2% |
| Status scope (cancellations) | 2% | 2% |

Freight is a roughly constant ~14% of gross every month, so including or
excluding it moves the level a lot and the growth rate essentially not at all.
The anchor is different in kind: it **moves revenue between months**, which is
precisely what corrupts a comparison. November 2017 is the clean illustration —
Black Friday orders are purchased in November and delivered in December, so a
delivery-anchored November looks flat while a purchase-anchored November spikes.
The month you most want to explain is the month where the choice matters most.

Holding the anchor fixed and letting everything else vary: 0–2 contradictions out
of 19. Holding the measure fixed instead: 7–8 out of 19, i.e. no improvement.

## What to standardise it to

**Purchase timestamp**, for three reasons:

1. It is the only anchor populated for **every** order. Approval is missing on
   160 orders, carrier handoff on 1,783, delivery on 2,965.
2. It never revises. A delivery-anchored month keeps filling in for weeks after
   month-end, so "last month's revenue" reported on the 1st is a different number
   than the same month reported on the 30th. Purchase-anchored months are final
   when the month ends.
3. It matches the decision the operating review is usually making, which is about
   demand.

**Keep a delivery-anchored series in parallel for finance** — control transfers on
delivery, so that is the accounting-correct basis. The point is not that one
anchor is right. It is that the two must be *named differently and never compared
to each other*, which is exactly what happens today when both are called
"revenue."

## Two traps worth fixing at the same time

- **Repeat-purchase rate is currently unmeasurable by accident.** Built on
  `customer_id` it is **0.00%**; built on `customer_unique_id` it is **3.12%**.
  `customer_id` is issued per order, so the natural-looking query returns a number
  that is not merely different but structurally always zero. Nobody notices,
  because zero looks like a finding.
- **Delivery time is 3.6 days or 7.7 days**, a 2.1x range, depending on whether
  the clock starts at carrier handoff or purchase and whether you count business
  or calendar days. No definition here is wrong; they are answers to different
  questions being reported under one label.

## What would have to be true for this to be wrong

The spread is measured over definitions we judged admissible. If you think the
delivery anchor should never have been in scope, the median spread drops to
20.5% and contradicted months fall from 8 to 4 of 19 — smaller, still material,
and the anchor still dominates the remainder, so the recommendation is unchanged. The finding that would
overturn this is evidence that one anchor is already universally used in
practice, in which case there is nothing to standardise and the real exposure is
the measure dimension instead.

## Cost of doing nothing

Every one of the eight contradicted months is a meeting where two teams arrive
with different numbers and spend it reconciling instead of deciding. The
definition is one line in a semantic layer. The reconciliation is recurring,
unbudgeted, and invisible in every plan.

---

*Full analysis in [`REPORT.md`](REPORT.md). Recommended definition in
[`METRIC_SPEC.md`](METRIC_SPEC.md). Everything reproduces with `make all`;
17 tests pin the claims above.*
