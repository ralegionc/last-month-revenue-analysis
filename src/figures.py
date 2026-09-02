"""Figures for the revenue definition audit.

Palette: the dataviz reference categorical slots 1-4 (blue, orange, aqua,
yellow), validated for the light surface. Aqua and yellow sit below 3:1 contrast
on this surface, so the relief rule applies: every series carries a visible
direct label, and the underlying table ships as CSV alongside.
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "out")
FIG = os.path.join(HERE, "..", "figures")
os.makedirs(FIG, exist_ok=True)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e6e5e1"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
ANCHOR_COLOR = {"purchase": S1, "approved": S2, "carrier": S3, "delivered": S4}
ANCHOR_LABEL = {"purchase": "Purchase", "approved": "Approved",
                "carrier": "Shipped", "delivered": "Delivered"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10,
    "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": GRID,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True,
})

brl = FuncFormatter(lambda v, _: f"R${v/1e6:.1f}M" if abs(v) >= 1e6
                    else f"R${v/1e3:.0f}k")


def title(ax, t, sub=None):
    ax.set_title(t, loc="left", fontsize=13, fontweight="bold", color=INK,
                 pad=26 if sub else 10)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9.5,
                color=INK2, va="bottom")


def load():
    rev = pd.read_csv(f"{OUT}/revenue_by_definition.csv")
    months = pd.read_csv(f"{OUT}/months.csv")
    comp = set(months.loc[months["complete"], "ym"])
    rev = rev[rev["ym"].isin(comp)].copy()
    rev["measure"] = np.where(
        rev["source"] == "items",
        np.where(rev["freight"] == "incl", "items+freight", "items only"),
        np.where(rev["voucher"] == "incl", "paid total", "paid ex-voucher"))
    with open(f"{OUT}/summary.json") as fh:
        summary = json.load(fh)
    return rev, summary


# ---------------------------------------------------------------- figure 1
def fig_focal(rev, summary):
    m = summary["focal_month"]
    sub = rev[rev["ym"] == m].sort_values("revenue").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    y = np.arange(len(sub))
    colors = [ANCHOR_COLOR[a] for a in sub["anchor"]]
    ax.scatter(sub["revenue"], y, s=44, c=colors, zorder=3,
               edgecolors=SURFACE, linewidths=1.2)

    med = sub["revenue"].median()
    ax.axvline(med, color=MUTED, lw=1.4, ls=(0, (4, 3)), zorder=2)
    ax.text(med, len(sub) + 1.5, f" median  R${med/1e6:.2f}M",
            color=INK2, fontsize=9, va="bottom")

    lo, hi = sub["revenue"].iloc[0], sub["revenue"].iloc[-1]
    ax.annotate(f"R${lo/1e6:.2f}M", (lo, 0), xytext=(-8, 0),
                textcoords="offset points", ha="right", va="center",
                fontsize=9.5, color=INK, fontweight="bold")
    ax.annotate(f"R${hi/1e6:.2f}M", (hi, len(sub) - 1), xytext=(8, 0),
                textcoords="offset points", ha="left", va="center",
                fontsize=9.5, color=INK, fontweight="bold")

    for a, c in ANCHOR_COLOR.items():
        idx = sub.index[sub["anchor"] == a]
        ax.scatter([], [], c=c, s=44, label=ANCHOR_LABEL[a])
    ax.legend(title="Period anchor", frameon=False, loc="lower right",
              fontsize=9, title_fontsize=9, labelcolor=INK2)

    ax.set_yticks([])
    ax.set_ylim(-2, len(sub) + 4)
    ax.xaxis.set_major_formatter(brl)
    ax.set_xlabel("Revenue reported for the month")
    ax.grid(axis="y", visible=False)
    title(ax, f"“What was revenue last month?” — {m}",
          f"Each dot is one of {len(sub)} defensible definitions. "
          f"Spread {summary['focal_revenue']['spread_pct']:.0f}% of mean; "
          f"highest is {summary['focal_revenue']['ratio']:.2f}x the lowest.")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig1_focal_month_fan.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- figure 2
def fig_anchor_series(rev):
    sub = rev[(rev["measure"] == "items+freight") & (rev["status"] == "all")]
    piv = sub.pivot_table(index="ym", columns="anchor", values="revenue").sort_index()
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    x = np.arange(len(piv))
    anchors = ["purchase", "approved", "carrier", "delivered"]
    for a in anchors:
        ax.plot(x, piv[a].values, lw=2, color=ANCHOR_COLOR[a], zorder=3,
                solid_capstyle="round")

    # Declutter end labels: nudge apart any that would collide, then leader-line
    # each back to its true endpoint so the label still reads as anchored.
    ends = sorted(((piv[a].values[-1], a) for a in anchors), key=lambda t: t[0])
    span = piv.values.max() - piv.values.min()
    min_gap = 0.055 * span
    placed = []
    for val, a in ends:
        y = val if not placed else max(val, placed[-1][0] + min_gap)
        placed.append((y, a, val))
    for y, a, val in placed:
        ax.annotate(ANCHOR_LABEL[a], (x[-1], y), xytext=(9, 0),
                    textcoords="offset points", va="center",
                    fontsize=9.5, color=ANCHOR_COLOR[a], fontweight="bold")
        if abs(y - val) > 1e-9:
            ax.plot([x[-1], x[-1] + 0.55], [val, y], lw=0.9,
                    color=ANCHOR_COLOR[a], alpha=0.7, zorder=2)
    nov = list(piv.index).index("2017-11")
    ax.axvline(nov, color=MUTED, lw=1, ls=(0, (3, 3)), zorder=1)
    ax.text(nov, ax.get_ylim()[1] * 0.98, " Black Friday", fontsize=9,
            color=INK2, va="top")

    ax.set_xticks(x[::3])
    ax.set_xticklabels(piv.index[::3], rotation=0)
    ax.yaxis.set_major_formatter(brl)
    ax.set_xlim(-0.5, len(piv) + 3.2)
    ax.grid(axis="x", visible=False)
    title(ax, "The same revenue, assigned to different months",
          "Identical orders and identical money. Only the timestamp that "
          "decides which month they land in changes.")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig2_anchor_timing.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- figure 3
def fig_attribution(summary):
    lv = summary["variance_shares_mean"]
    gr = summary["growth_variance_shares_mean"]
    factors = ["anchor", "measure", "status"]
    names = ["Period anchor", "Revenue measure", "Status scope"]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    y = np.arange(len(factors))
    h = 0.32
    ax.barh(y + h/2 + 0.01, [100*lv[f] for f in factors], height=h,
            color=S1, zorder=3, label="Level of revenue")
    ax.barh(y - h/2 - 0.01, [100*gr[f] for f in factors], height=h,
            color=S2, zorder=3, label="Month-over-month growth")
    for i, f in enumerate(factors):
        ax.text(100*lv[f] + 1.5, i + h/2 + 0.01, f"{100*lv[f]:.0f}%",
                va="center", fontsize=9.5, color=INK2)
        ax.text(100*gr[f] + 1.5, i - h/2 - 0.01, f"{100*gr[f]:.0f}%",
                va="center", fontsize=9.5, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 118)
    ax.set_ylim(-0.6, len(factors) - 0.15)
    ax.set_xlabel("Share of variance across definitions (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=INK2,
              bbox_to_anchor=(1.0, 1.02))
    title(ax, "Different choices break different numbers",
          "Measure moves the level. The anchor corrupts growth — which is\n"
          "what the meeting is actually about.")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig3_attribution.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- figure 4
def fig_robustness():
    cr = pd.read_csv(f"{OUT}/conditional_robustness.csv")
    order, labels, vals = [], [], []
    base = cr[cr["held_fixed"] == "(nothing)"].iloc[0]
    labels.append("Nothing standardised")
    vals.append(base["flip_pct"])
    for dim, nice in [("anchor", "Standardise the anchor"),
                      ("measure", "Standardise the measure"),
                      ("status", "Standardise status scope")]:
        d = cr[cr["held_fixed"] == dim]
        labels.append(nice)
        vals.append(d["flip_pct"].mean())
    fig, ax = plt.subplots(figsize=(9.0, 4.0))
    y = np.arange(len(labels))[::-1]
    cols = [MUTED, S1, S2, S3]
    ax.barh(y, vals, height=0.55, color=cols, zorder=3)
    for yy, v in zip(y, vals):
        ax.text(v + 1, yy, f"{v:.0f}%", va="center", fontsize=10,
                color=INK, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_xlabel("Months where the growth call's sign depends on definition (%)")
    ax.grid(axis="y", visible=False)
    title(ax, "One choice does almost all the damage",
          "Average share of month-pairs with a contradictory growth sign, "
          "after fixing each dimension in turn.")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig4_robustness.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- figure 5
def fig_spread_by_month(summary):
    sp = pd.read_csv(f"{OUT}/spread_revenue.csv")
    fl = pd.read_csv(f"{OUT}/decision_flips.csv")
    flip_months = set(fl.loc[fl["flip"], "ym"])
    from matplotlib.patches import Patch
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    x = np.arange(len(sp))
    first = sp["ym"].iloc[0]  # no prior month, so no growth call exists
    colors = [MUTED if m == first else (S2 if m in flip_months else S1)
              for m in sp["ym"]]
    ax.bar(x, sp["spread_pct"], width=0.68, color=colors, zorder=3)
    med = sp["spread_pct"].median()
    ax.axhline(med, color=MUTED, lw=1.4, ls=(0, (4, 3)), zorder=4)
    ax.text(len(sp) - 0.4, med, f" median {med:.0f}%", color=INK2,
            fontsize=9, va="bottom", ha="right")
    ax.set_xticks(x[::2])
    ax.set_xticklabels(sp["ym"][::2], rotation=45, ha="right")
    ax.set_ylabel("Spread across definitions (% of mean)")
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0, sp["spread_pct"].max() * 1.32)
    ax.legend(handles=[Patch(color=S2, label="Growth call contradicted"),
                       Patch(color=S1, label="Growth call agreed"),
                       Patch(color=MUTED, label="No prior month")],
              frameon=False, fontsize=9, labelcolor=INK2, loc="upper right",
              ncol=3, columnspacing=1.2, handlelength=1.2)
    title(ax, "How far apart the defensible answers sit, month by month",
          "2017-01 is the extreme: in a fast-ramping month, delivery lag makes "
          "the anchor choice dominate everything.")
    fig.tight_layout()
    fig.savefig(f"{FIG}/fig5_spread_by_month.png", dpi=200)
    plt.close(fig)


def main():
    rev, summary = load()
    fig_focal(rev, summary)
    fig_anchor_series(rev)
    fig_attribution(summary)
    fig_robustness()
    fig_spread_by_month(summary)
    print("wrote 5 figures to", os.path.abspath(FIG))


if __name__ == "__main__":
    main()
