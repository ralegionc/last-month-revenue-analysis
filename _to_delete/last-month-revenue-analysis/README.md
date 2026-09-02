# Last Month Revenue Analysis

**How much does "last month's revenue" actually vary across defensible
definitions — and which single standardisation fixes the most?**

Across 64 defensible definitions of monthly revenue on the same 99,441 orders,
August 2018 supports answers from **R$838,577 to R$1,347,361** — a 47% spread and
1.61x from low to high. **Eight of nineteen** month-over-month growth calls
contain a contradiction: one defensible definition says the business grew,
another says it shrank.

The actionable finding: **the period anchor carries 96% of the variance in growth
rates.** Standardising it alone drops contradicted month-pairs from 42% to 5%.
Standardising the freight policy — the argument teams actually have — drops it to
41%.

| | |
|---|---|
| **Start here** | [`MEMO.md`](MEMO.md) — one page, recommendation first |
| **Full analysis** | [`REPORT.md`](REPORT.md) — method, results, limitations |
| **The deliverable** | [`METRIC_SPEC.md`](METRIC_SPEC.md) — definitions to standardise on |
| **Interactive** | `revenue_definition_audit.html` — move the definition, watch the number |

---

## Run it

```bash
pip install -r requirements.txt
make data      # fetch Olist CSVs from Olist's own GitHub org (~160MB)
make all       # profile -> engine -> analyze -> figures -> html
make test      # 17 quality gates
```

Everything is CPU-only and runs in about a minute after the download. DuckDB does
the heavy lifting; no warehouse required.

## How it works

```
src/definitions.py   the admissible definition space + the admissibility rule
                     + 7 rejected definitions with reasons
src/engine.py        one order-level base table, then every definition evaluated
                     as a parameterisation of ONE query
src/analyze.py       spread, variance attribution (levels and growth), decision
                     flips, conditional robustness
src/figures.py       5 static figures
src/build_html.py    the self-contained interactive report
tests/test_audit.py  17 gates pinning integrity, admissibility, and every
                     headline number quoted in the prose
```

**Definitions are parameters, never hand-written queries.** Writing 64 variants by
hand is how definition drift gets into an audit of definition drift.

**The admissibility rule comes first and is enforced in tests.** A definition is
admissible only if you can state a business context in which a competent analyst
would prefer it. Without that rule the headline spread is trivially inflatable by
adding absurd variants — so the rejected ones are documented too.

**The prose depends on the pipeline, not the other way round.** Every number in
the memo and report is generated into `out/summary.json` and pinned by a test. If
the pipeline changes and a headline moves, the tests fail and the prose is wrong.

## Data

[Olist Brazilian E-Commerce Public Dataset](https://github.com/olist/work-at-olist-data),
taken from Olist's own GitHub organisation rather than a third-party mirror.
99,441 orders, September 2016 – October 2018. Boundary months are excluded as
partial exports; the analysis window is the 20 complete months from 2017-01 to
2018-08.

The dataset is a good subject because its ambiguity is genuine: five timestamps
per order, freight at 14.2% of gross, 603 "unavailable" orders that have payment
records but no line items at all, and a `customer_id` column that is issued per
order and silently returns a 0% repeat rate forever.

## Results at a glance

| Finding | Value |
|---|---|
| Spread, August 2018 | 47.2% of mean (R$508,784) |
| Median spread, 20 months | 27.5% |
| Contradicted growth calls | 8 of 19 (42%) |
| Anchor's share of growth variance | 96.3% |
| Measure's share of level variance | 60.2% |
| Contradictions after fixing the anchor | 5% |
| Repeat rate: `customer_id` vs `customer_unique_id` | 0.00% vs 3.12% |
| Delivery time, August 2018 | 3.6 to 7.7 days |

## Limitations

One dataset, one vertical. A marketplace with physical delivery has a long gap
between purchase and delivery, which is what gives the anchor its leverage — a
digital-goods business would likely show a smaller anchor effect and a larger
measure effect. The method transfers; the magnitudes should not be quoted for
another business. Full discussion in [`REPORT.md` §9](REPORT.md).
