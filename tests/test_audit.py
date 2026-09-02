"""
Quality gates for the revenue definition audit.

These are not decorative. An audit of definition drift is exactly the kind of
project that can quietly acquire its own definition drift -- a fan-out join, a
silently dropped status, a spread number inflated by an inadmissible variant.
Each test below pins one of those.

Run: python -m pytest tests/ -q
"""
import os
import sys
import json
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import definitions as D  # noqa: E402
import engine as E  # noqa: E402
import analyze as A  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "out")


@pytest.fixture(scope="module")
def con():
    c = E.connect()
    E.build_base(c)
    return c


@pytest.fixture(scope="module")
def rev():
    return pd.read_csv(f"{OUT}/revenue_by_definition.csv")


@pytest.fixture(scope="module")
def summary():
    with open(f"{OUT}/summary.json") as fh:
        return json.load(fh)


# --------------------------------------------------------------- integrity
def test_base_is_one_row_per_order(con):
    n, d = con.execute("SELECT count(*), count(DISTINCT order_id) FROM base").fetchone()
    assert n == d == 99441


def test_no_orphan_revenue(con):
    """Every order_id in items/payments must exist in orders, or LEFT JOINs
    silently discard money."""
    r = con.execute("""
        SELECT (SELECT count(*) FROM (SELECT DISTINCT order_id FROM items_raw
                EXCEPT SELECT order_id FROM orders_raw)),
               (SELECT count(*) FROM (SELECT DISTINCT order_id FROM payments_raw
                EXCEPT SELECT order_id FROM orders_raw))
    """).fetchone()
    assert r == (0, 0)


def test_aggregation_does_not_fan_out(con):
    """The classic bug this whole project is about: joining orders to a
    multi-row child table without aggregating first multiplies revenue."""
    correct = con.execute("SELECT round(sum(items_price), 2) FROM base").fetchone()[0]
    raw = con.execute("SELECT round(sum(price), 2) FROM items_raw").fetchone()[0]
    assert abs(correct - raw) < 0.01


def test_payments_and_items_reconcile_in_aggregate(con):
    """They should agree to well under 1% -- if this drifts, one of the two
    revenue sources has been mis-parsed."""
    p, i = con.execute("""
        SELECT sum(pay_total), sum(items_price + items_freight)
        FROM base WHERE has_items AND has_payments
    """).fetchone()
    assert abs(p - i) / i < 0.001


# ------------------------------------------------------------ admissibility
def test_every_definition_has_a_documented_rationale():
    for dim in (D.ANCHORS, D.STATUS, D.FREIGHT, D.VOUCHERS, D.SOURCES):
        for k, v in dim.items():
            assert v.get("rationale"), f"{k} has no stated rationale"


def test_rejected_definitions_are_documented_with_reasons():
    assert len(D.REJECTED) >= 5
    for name, reason in D.REJECTED:
        assert len(reason) > 40, f"{name} rejected without a real reason"


def test_definition_space_is_the_expected_factorial():
    defs = D.enumerate_definitions()
    assert len(defs) == 64
    assert len({d["def_id"] for d in defs}) == 64
    # freight applies only to items; vouchers only to payments
    for d in defs:
        if d["source"] == "items":
            assert d["voucher"] == "n/a"
        else:
            assert d["freight"] == "n/a"


# ----------------------------------------------------------------- outputs
def test_no_definition_produces_impossible_revenue(rev):
    assert rev["revenue"].notna().all()
    assert (rev["revenue"] >= 0).all()
    assert (rev["n_orders"] > 0).all()


def test_freight_toggle_is_exactly_the_freight_component(con):
    incl = con.execute("""SELECT sum(items_price + items_freight) FROM base
                          WHERE ts_purchase IS NOT NULL""").fetchone()[0]
    excl = con.execute("""SELECT sum(items_price) FROM base
                          WHERE ts_purchase IS NOT NULL""").fetchone()[0]
    frt = con.execute("""SELECT sum(items_freight) FROM base
                         WHERE ts_purchase IS NOT NULL""").fetchone()[0]
    assert abs((incl - excl) - frt) < 0.01


def test_status_filters_are_nested(con):
    """all >= ex_canceled >= ex_canceled_unavail >= delivered_only, always."""
    vals = []
    for key in ("all", "ex_canceled", "ex_canceled_unavail", "delivered_only"):
        w = D.STATUS[key]["where"]
        vals.append(con.execute(
            f"SELECT count(*) FROM base WHERE {w}").fetchone()[0])
    assert vals == sorted(vals, reverse=True)


def test_boundary_months_are_excluded(summary):
    """Olist's first and last months are partial exports. Including them would
    manufacture spread that is an artefact of the export, not of definitions."""
    months = summary["complete_months"]
    for partial in ("2016-09", "2016-10", "2016-12", "2018-09", "2018-10"):
        assert partial not in months
    assert months[0] == "2017-01" and months[-1] == "2018-08"


# ------------------------------------------------------ analysis primitives
def test_spread_pct_on_a_known_case():
    df = pd.DataFrame({"ym": ["m"] * 3, "revenue": [80.0, 100.0, 120.0]})
    out = A.spread_table(df)
    assert out["spread_abs"].iloc[0] == 40
    assert out["spread_pct"].iloc[0] == pytest.approx(40.0)


def test_decision_flip_detection_on_a_known_case():
    """Two definitions that disagree on the sign of growth must be flagged;
    two that agree must not."""
    df = pd.DataFrame({
        "ym": ["2020-01", "2020-02"] * 2,
        "def_id": ["a", "a", "b", "b"],
        "revenue": [100.0, 110.0, 100.0, 90.0],
    })
    fl = A.decision_flips(df)
    assert bool(fl["flip"].iloc[0]) is True

    df2 = df.copy()
    df2.loc[3, "revenue"] = 105.0
    assert bool(A.decision_flips(df2)["flip"].iloc[0]) is False


def test_variance_shares_sum_to_one(summary):
    for key in ("variance_shares_mean", "growth_variance_shares_mean"):
        assert sum(summary[key].values()) == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------- headline stability
def test_headline_numbers_are_stable(summary):
    """Pins the claims made in the memo. If the pipeline changes and these
    move, the memo is wrong and must be rewritten -- not the other way round."""
    f = summary["focal_revenue"]
    assert f["month"] == "2018-08"
    assert 45 < f["spread_pct"] < 50
    assert 1.55 < f["ratio"] < 1.70
    assert 25 < summary["spread_pct_median_across_months"] < 30
    assert summary["n_flips"] == 8 and summary["n_month_pairs"] == 19
    assert summary["growth_variance_shares_mean"]["anchor"] > 0.90
    assert summary["variance_shares_mean"]["measure"] > 0.50


def test_standardising_the_anchor_beats_the_alternatives(summary):
    """The memo's central recommendation. If this ever fails, the
    recommendation is no longer supported."""
    cr = pd.DataFrame(summary["conditional_robustness"])
    by_dim = cr[cr["held_fixed"] != "(nothing)"].groupby("held_fixed")["flip_pct"].mean()
    assert by_dim["anchor"] < 10
    assert by_dim["measure"] > 30
    assert by_dim["status"] > 30


def test_customer_id_is_a_trap(summary):
    """customer_id is per-order in Olist, so a repeat-rate built on it is
    identically zero. This is the documented worked example of a definition
    that is not merely different but silently degenerate."""
    r = {x["def_id"]: x["repeat_rate_pct"] for x in summary["repeat_rate"]}
    assert r["customer_id|all"] == 0.0
    assert r["customer_unique_id|all"] > 3.0
