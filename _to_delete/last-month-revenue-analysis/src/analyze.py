"""
Analysis: definition spread, attribution of spread to individual choices,
and decision flips.

Primary metric  : definition spread = (max - min) / mean across admissible
                  definitions, per metric per month.
Decision metric : the share of month-over-month growth calls whose *sign*
                  depends only on which admissible definition was used.
"""
import os
import json
import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "..", "out")

# 2018-08 is the last month with full coverage under all four anchors
# (2018-09 collapses to 1-56 orders: the export boundary).
FOCAL_MONTH = "2018-08"


def measure_of(row):
    """Collapse source x freight x voucher into one 4-level 'measure' factor."""
    if row["source"] == "items":
        return "items+freight" if row["freight"] == "incl" else "items only"
    return "paid total" if row["voucher"] == "incl" else "paid ex-voucher"


def load():
    rev = pd.read_csv(f"{OUT}/revenue_by_definition.csv")
    months = pd.read_csv(f"{OUT}/months.csv")
    complete = set(months.loc[months["complete"], "ym"])
    rev["measure"] = rev.apply(measure_of, axis=1)
    rev = rev[rev["ym"].isin(complete)].copy()
    # A definition is usable for a month only if it produced a value there.
    return rev, sorted(complete)


def spread_table(rev, value="revenue"):
    g = rev.groupby("ym")[value]
    out = pd.DataFrame({
        "n_defs": g.count(), "min": g.min(), "max": g.max(),
        "mean": g.mean(), "median": g.median(),
    })
    out["spread_abs"] = out["max"] - out["min"]
    out["spread_pct"] = 100 * out["spread_abs"] / out["mean"]
    return out.reset_index()


def variance_decomposition(rev, value="revenue"):
    """
    Share of within-month variance in log(metric) attributable to each choice.

    Type-II style: for each factor, the reduction in residual sum of squares
    from adding it to a model containing the other two main effects. Reported
    as a share of total explained SS so the three numbers are comparable.
    """
    import itertools
    df = rev.copy()
    df["y"] = np.log(df[value].clip(lower=1e-9))
    factors = ["anchor", "measure", "status"]

    def rss(sub, cols):
        if not cols:
            return ((sub["y"] - sub["y"].mean()) ** 2).sum()
        pred = sub.groupby(cols)["y"].transform("mean")
        return ((sub["y"] - pred) ** 2).sum()

    rows = []
    for ym, sub in df.groupby("ym"):
        total = rss(sub, [])
        full = rss(sub, factors)
        contrib = {}
        for f in factors:
            others = [x for x in factors if x != f]
            contrib[f] = rss(sub, others) - full
        s = sum(contrib.values())
        row = {"ym": ym, "total_ss": total,
               "explained_by_main_effects": (total - full) / total if total else 0}
        for f in factors:
            row[f"share_{f}"] = contrib[f] / s if s else 0
        rows.append(row)
    return pd.DataFrame(rows)


def decision_flips(rev, value="revenue"):
    """
    For each consecutive month pair, compute MoM growth under every definition
    and record whether the sign of the growth call is unanimous.
    """
    piv = rev.pivot_table(index="ym", columns="def_id", values=value)
    piv = piv.sort_index()
    growth = piv.pct_change().iloc[1:]
    rows = []
    for ym, r in growth.iterrows():
        r = r.dropna()
        if len(r) < 2:
            continue
        pos, neg = (r > 0).sum(), (r < 0).sum()
        rows.append({
            "ym": ym,
            "n_defs": len(r),
            "n_positive": int(pos),
            "n_negative": int(neg),
            "flip": bool(pos > 0 and neg > 0),
            "min_growth_pct": 100 * r.min(),
            "max_growth_pct": 100 * r.max(),
            "median_growth_pct": 100 * r.median(),
        })
    return pd.DataFrame(rows)


def conditional_robustness(rev, value="revenue"):
    """
    The actionable question: if a team standardises ONE choice, how much of the
    disagreement goes away? Reports spread and flip rate with each dimension
    held fixed, one at a time.
    """
    rows = []
    full_fl = decision_flips(rev, value)
    rows.append({
        "held_fixed": "(nothing)", "level": "all 64 definitions",
        "n_defs": rev["def_id"].nunique(),
        "median_spread_pct": float(spread_table(rev, value)["spread_pct"].median()),
        "n_flips": int(full_fl["flip"].sum()), "n_pairs": int(len(full_fl)),
    })
    for dim in ("anchor", "measure", "status"):
        for lvl, sub in rev.groupby(dim):
            fl = decision_flips(sub, value)
            rows.append({
                "held_fixed": dim, "level": lvl,
                "n_defs": sub["def_id"].nunique(),
                "median_spread_pct": float(spread_table(sub, value)["spread_pct"].median()),
                "n_flips": int(fl["flip"].sum()), "n_pairs": int(len(fl)),
            })
    df = pd.DataFrame(rows)
    df["flip_pct"] = 100 * df["n_flips"] / df["n_pairs"]
    return df


def growth_variance_decomposition(rev, value="revenue"):
    """
    Same decomposition as variance_decomposition, but on month-over-month growth
    rates rather than levels.

    These can disagree, and the disagreement is the point: a choice that scales
    every month by a constant factor (freight) moves the level a lot and growth
    not at all, while a choice that shifts revenue between months (the anchor)
    does the opposite.
    """
    piv = rev.pivot_table(index="ym", columns="def_id", values=value).sort_index()
    growth = piv.pct_change().iloc[1:]
    meta = rev.drop_duplicates("def_id").set_index("def_id")[
        ["anchor", "measure", "status"]]
    long = growth.reset_index().melt(id_vars="ym", var_name="def_id",
                                     value_name="g").dropna()
    long = long.join(meta, on="def_id")
    long = long.rename(columns={"g": "y"})
    factors = ["anchor", "measure", "status"]

    def rss(sub, cols):
        if not cols:
            return ((sub["y"] - sub["y"].mean()) ** 2).sum()
        pred = sub.groupby(cols)["y"].transform("mean")
        return ((sub["y"] - pred) ** 2).sum()

    rows = []
    for ym, sub in long.groupby("ym"):
        full = rss(sub, factors)
        contrib = {f: rss(sub, [x for x in factors if x != f]) - full
                   for f in factors}
        s = sum(contrib.values())
        rows.append({"ym": ym, **{f"share_{f}": (contrib[f] / s if s else 0)
                                  for f in factors}})
    return pd.DataFrame(rows)


def focal(rev, month, value="revenue"):
    sub = rev[rev["ym"] == month].copy()
    sub = sub.sort_values(value)
    lo, hi = sub.iloc[0], sub.iloc[-1]
    return dict(
        month=month,
        n_defs=len(sub),
        min=float(sub[value].min()),
        max=float(sub[value].max()),
        mean=float(sub[value].mean()),
        median=float(sub[value].median()),
        spread_pct=float(100 * (sub[value].max() - sub[value].min()) / sub[value].mean()),
        ratio=float(sub[value].max() / sub[value].min()),
        lowest_def=lo["def_id"], highest_def=hi["def_id"],
        table=sub[["def_id", "anchor", "measure", "status", value, "n_orders"]],
    )


def main():
    rev, complete = load()

    sp = spread_table(rev)
    vd = variance_decomposition(rev)
    fl = decision_flips(rev)
    f_rev = focal(rev, FOCAL_MONTH)
    f_aov = focal(rev, FOCAL_MONTH, value="aov")
    sp_aov = spread_table(rev, value="aov")

    cr = conditional_robustness(rev)
    gvd = growth_variance_decomposition(rev)
    cr.to_csv(f"{OUT}/conditional_robustness.csv", index=False)
    gvd.to_csv(f"{OUT}/growth_variance_decomposition.csv", index=False)

    sp.to_csv(f"{OUT}/spread_revenue.csv", index=False)
    sp_aov.to_csv(f"{OUT}/spread_aov.csv", index=False)
    vd.to_csv(f"{OUT}/variance_decomposition.csv", index=False)
    fl.to_csv(f"{OUT}/decision_flips.csv", index=False)
    f_rev["table"].to_csv(f"{OUT}/focal_month_revenue.csv", index=False)

    # ---- delivery time -----------------------------------------------------
    dlv = pd.read_csv(f"{OUT}/delivery_by_definition.csv")
    dlv = dlv[dlv["ym"].isin(complete)]
    dl_focal = dlv[dlv["ym"] == FOCAL_MONTH]
    dl_summary = dlv.groupby("ym")["mean_days"].agg(["min", "max", "mean"])
    dl_summary["spread_pct"] = 100 * (dl_summary["max"] - dl_summary["min"]) / dl_summary["mean"]
    dl_summary.reset_index().to_csv(f"{OUT}/spread_delivery.csv", index=False)

    # ---- repeat rate -------------------------------------------------------
    rpt = pd.read_csv(f"{OUT}/repeat_by_definition.csv")

    summary = {
        "complete_months": complete,
        "n_complete_months": len(complete),
        "n_definitions": int(rev["def_id"].nunique()),
        "focal_month": FOCAL_MONTH,
        "focal_revenue": {k: v for k, v in f_rev.items() if k != "table"},
        "focal_aov": {k: v for k, v in f_aov.items() if k != "table"},
        "spread_pct_median_across_months": float(sp["spread_pct"].median()),
        "spread_pct_min": float(sp["spread_pct"].min()),
        "spread_pct_max": float(sp["spread_pct"].max()),
        "aov_spread_pct_median": float(sp_aov["spread_pct"].median()),
        "variance_shares_mean": {
            f: float(vd[f"share_{f}"].mean()) for f in ("anchor", "measure", "status")
        },
        "growth_variance_shares_mean": {
            f: float(gvd[f"share_{f}"].mean()) for f in ("anchor", "measure", "status")
        },
        "conditional_robustness": cr.to_dict("records"),
        "explained_by_main_effects_mean": float(vd["explained_by_main_effects"].mean()),
        "n_month_pairs": int(len(fl)),
        "n_flips": int(fl["flip"].sum()),
        "flip_pct": float(100 * fl["flip"].mean()),
        "flip_months": fl.loc[fl["flip"], "ym"].tolist(),
        "delivery_spread_pct_median": float(dl_summary["spread_pct"].median()),
        "delivery_focal_min_days": float(dl_focal["mean_days"].min()),
        "delivery_focal_max_days": float(dl_focal["mean_days"].max()),
        "repeat_rate": rpt[["def_id", "n_customers", "n_repeat",
                            "repeat_rate_pct"]].to_dict("records"),
    }
    with open(f"{OUT}/summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)

    # ---- console report ----------------------------------------------------
    print(f"Complete months            : {len(complete)} "
          f"({complete[0]} .. {complete[-1]})")
    print(f"Admissible definitions     : {summary['n_definitions']}")
    print()
    print(f"=== FOCAL MONTH {FOCAL_MONTH}: 'last month's revenue' ===")
    fr = summary["focal_revenue"]
    print(f"  min    R$ {fr['min']:>14,.2f}   [{fr['lowest_def']}]")
    print(f"  median R$ {fr['median']:>14,.2f}")
    print(f"  max    R$ {fr['max']:>14,.2f}   [{fr['highest_def']}]")
    print(f"  spread    {fr['spread_pct']:.1f}% of mean   "
          f"(max/min = {fr['ratio']:.2f}x)")
    print()
    print(f"Spread across {len(complete)} months: median {summary['spread_pct_median_across_months']:.1f}%, "
          f"range {summary['spread_pct_min']:.1f}%-{summary['spread_pct_max']:.1f}%")
    print(f"AOV spread median          : {summary['aov_spread_pct_median']:.1f}%")
    print()
    print("Variance attribution, LEVELS (share of explained within-month variance):")
    for f, v in summary["variance_shares_mean"].items():
        print(f"  {f:<8} {100*v:5.1f}%")
    print()
    print("Variance attribution, MoM GROWTH:")
    for f, v in summary["growth_variance_shares_mean"].items():
        print(f"  {f:<8} {100*v:5.1f}%")
    print()
    print("If you standardise ONE choice, what survives?")
    print(cr.to_string(index=False,
                       columns=["held_fixed", "level", "n_defs",
                                "median_spread_pct", "n_flips", "n_pairs"],
                       float_format=lambda x: f"{x:.1f}"))
    print()
    print(f"MoM growth-sign flips      : {summary['n_flips']} of "
          f"{summary['n_month_pairs']} month pairs "
          f"({summary['flip_pct']:.0f}%)")
    print(f"  flip months: {', '.join(summary['flip_months'])}")
    print()
    print(f"Delivery time {FOCAL_MONTH}     : "
          f"{summary['delivery_focal_min_days']:.1f} to "
          f"{summary['delivery_focal_max_days']:.1f} days "
          f"(median monthly spread {summary['delivery_spread_pct_median']:.0f}%)")
    print()
    print("Repeat-purchase rate:")
    for r in summary["repeat_rate"]:
        print(f"  {r['def_id']:<40} {r['repeat_rate_pct']:6.2f}%  "
              f"({r['n_repeat']:,} of {r['n_customers']:,})")


if __name__ == "__main__":
    main()
