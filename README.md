# Last Month's Revenue Is Not One Number

**An audit of how far a single metric can legitimately move before anyone has done
anything wrong, and which one standardisation fixes the most.**

Ask four analysts for last month's revenue and you get four numbers. The usual
explanation is that someone made a mistake. Usually nobody did. Each of them
picked a defensible answer to the same three questions, and the questions have no
canonical answers.

Which timestamp assigns an order to a month? Does revenue include freight? Do
cancelled orders count?

This project enumerates 64 defensible combinations of those choices, computes all
of them over the same 99,441 orders, and measures what the disagreement does to
the decisions the number is used for.

**Across 64 definitions, August 2018 supports answers from R$838,577 to
R$1,347,361.** That is a 47% spread and 1.61 times from lowest to highest, from
identical rows. More consequentially, **8 of 19 month-over-month growth
comparisons contain a contradiction**: one defensible definition says the business
grew, another says it shrank, over the same period.

**One change fixes almost all of it.** Standardise the period anchor and
contradicted month-pairs fall from 42% to 5%. Standardise the freight policy, the
argument teams actually have, and it falls from 42% to 41%.

```
$ make

  dataset          Olist Brazilian e-commerce, 99,441 orders, Jan 2017 - Aug 2018
  definitions      64 admissible  (4 anchors x 2 measures x 2 freight x 2 status)
  months           20 complete

  focal month 2018-08
    lowest      R$  838,577    purchase | items | excl freight | delivered only
    highest     R$1,347,360    delivery | items | incl freight | delivered only
    spread             47.2%   ratio 1.61x
    AOV spread         20.3%   ratio 1.23x

  across all 20 months
    median spread      27.5%   min 18.2%   max 109.4%

  variance decomposition        level     growth
    period anchor                38.2%     96.3%
    revenue measure              60.2%      1.9%
    status scope                  1.5%      1.8%

  month-pairs with a contradiction    8 / 19   (42.1%)
    holding anchor fixed              0-2 / 19
    holding measure fixed             7-8 / 19
```

---

## Why this is interesting

**The spread is not the finding.** That a metric varies under different
definitions is unsurprising and, on its own, not actionable. The finding is that
the variation flips the sign of growth in 42% of month-pairs, which turns a
definitional question into a decision-quality problem.

**The variance decomposition inverts between level and growth.** The revenue
measure drives 60% of variance in the level and 2% in growth. The period anchor
drives 38% of the level and **96%** of growth. Teams argue about freight because
it visibly moves the headline number. It is almost the only choice that does not
matter for the comparison anyone is actually making.

**The mechanism is legible.** Freight is a roughly constant 14% of gross every
month, so including it scales the level and leaves the growth rate alone. The
anchor is different in kind: it *moves revenue between months*, which is precisely
what corrupts a period-over-period comparison.

**November 2017 is the clean illustration.** Black Friday orders are purchased in
November and delivered in December. A delivery-anchored November looks flat while
a purchase-anchored November spikes. The month you most want to explain is the
month where the choice matters most.

**The inadmissible definitions were excluded up front and documented.** The claim
is not that 64 numbers exist, but that 64 *defensible* numbers exist. Anything a
competent analyst would reject was removed before counting.

---

## The recommendation

Standardise the period anchor, to **purchase timestamp**, for operating reviews.

**It is the only anchor populated for every order.** Approval is missing on 160
orders, carrier handoff on 1,783, delivery on 2,965. Any other anchor silently
drops rows, and which rows it drops correlates with the thing being measured.

**It never revises.** A delivery-anchored month keeps filling in for weeks after
month-end, so last month's revenue reported on the 1st is a different number from
the same month reported on the 30th. Purchase-anchored months are final when the
month ends.

**It matches the decision.** An operating review is usually asking about demand,
and demand happens at purchase.

Keep a delivery-anchored series in parallel for finance, since control transfers
on delivery and that is the accounting-correct basis. The point is not that one
anchor is true. It is that a comparison must use one anchor, declared, and the
same one on both sides.

[`METRIC_SPEC.md`](METRIC_SPEC.md) writes this out the way a semantic layer would
enforce it, naming both the decision and the alternatives it rejects.

---

## The definition grid

64 combinations across four dimensions.

| Dimension | Options |
|---|---|
| Period anchor | purchase, approval, carrier handoff, delivery |
| Measure | line items, payments |
| Freight | included, excluded |
| Status scope | all orders, delivered only |

Each is computed over all 20 complete months, giving a full grid rather than a
sample of it, which is what makes the variance decomposition exact rather than
estimated.

## Architecture

```
   Olist Brazilian e-commerce, 99,441 orders, Jan 2017 - Aug 2018
        |
        v
   src/definitions.py    the 64-cell grid; admissibility rules and exclusions
        |
        v
   src/engine.py         computes every definition over every month
        |                one pass, no per-definition re-scan
        v
   src/analyze.py        +-- revenue_by_definition, spread_revenue
        |                +-- growth_variance_decomposition   anchor vs measure vs status
        |                +-- decision_flips                  the 8 contradicted pairs
        |                +-- conditional_robustness          hold one dimension fixed
        |                +-- repeat_by_definition, delivery_by_definition
        v
   src/figures.py        figures/
   src/build_html.py     revenue_definition_audit.html   move the definition,
                                                          watch the number move
```

## Reading order

| Document | For |
|---|---|
| [`MEMO.md`](MEMO.md) | One page, recommendation first. Start here |
| [`REPORT.md`](REPORT.md) | Method, results, limitations |
| [`METRIC_SPEC.md`](METRIC_SPEC.md) | The specification to standardise on |
| `revenue_definition_audit.html` | Interactive. Change a choice, watch the number |

## Running it

```bash
pip install -r requirements.txt
make
```

`make` runs the engine, the analysis, the figures and the HTML build. `pytest`
runs the test suite.

## Outputs

| File | Contents |
|---|---|
| `out/summary.json` | Every headline number in this README |
| `out/revenue_by_definition.csv` | The full 64 by 20 grid |
| `out/spread_revenue.csv`, `out/spread_aov.csv` | Spread per month, both metrics |
| `out/growth_variance_decomposition.csv` | Anchor vs measure vs status, per month |
| `out/decision_flips.csv` | The 8 contradicted month-pairs, with the pair of definitions |
| `out/conditional_robustness.csv` | Contradictions remaining when one dimension is held fixed |
| `out/focal_month_revenue.csv` | August 2018 under all 64 |
| `out/repeat_by_definition.csv`, `out/delivery_by_definition.csv` | Companion metrics under the same grid |

## Limitations

One dataset, one business model. Olist is a Brazilian marketplace, and the
freight share that makes the measure dimension so influential on the level is a
property of marketplace logistics. A subscription business would show a different
decomposition, and the anchor result may or may not generalise.

The 64 definitions are admissible by the author's judgement. That judgement is
documented and can be disputed, and disputing it is the correct way to attack this
analysis.

Twenty months is enough to establish the pattern and not enough to characterise
seasonality. The 109.4% maximum spread is a single month and should not be read as
typical.

## Roadmap

- Replicate on a subscription or SaaS dataset, where deferred revenue introduces a
  fifth dimension and the anchor question changes shape
- Extend the flip analysis to quarter-over-quarter and year-over-year, where
  anchor effects should partially wash out
- Ship the grid as a dbt package so the audit can run against a live warehouse
  rather than a static extract

## Data

Olist Brazilian E-Commerce Public Dataset, 99,441 orders spanning January 2017 to
August 2018.

## License

MIT. See [LICENSE](LICENSE).
