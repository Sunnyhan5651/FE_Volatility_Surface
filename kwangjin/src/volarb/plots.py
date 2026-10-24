"""그림 생성. 그림 안에는 성과 수치(수익률·MDD·Sharpe 등)를 넣지 않는다 — 수치는 콘솔/표로만 출력한다.
(그림의 한글 깨짐을 막기 위해 라벨은 영문 사용)"""
from __future__ import annotations

from pathlib import Path

import sys

import matplotlib

# 스파이더/주피터에서 실행하거나 --show 를 주면 화면에 표시, 아니면 파일로만 저장 (--no-show 로 강제 해제)
SHOW = ("--no-show" not in sys.argv) and ("--show" in sys.argv or "spyder_kernels" in sys.modules)
if not SHOW:
    matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import drawdown_series

# Okabe-Ito (색각 이상에도 구분되는 팔레트)
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000", "#999999"]
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "legend.frameon": False, "axes.titlesize": 11})


def _dt(dates):
    return pd.to_datetime(pd.Series(dates), format="%Y%m%d")


def _fmt_dates(ax):
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))


def _save(fig, out: Path, name: str) -> str:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    if not getattr(fig, '_skip_tight', False):
        fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    if SHOW:
        plt.show()
    plt.close(fig)
    return str(path)


def _curve(ax, dates, eq, label, color, **kw):
    ax.plot(_dt(dates), 100 * np.array(eq[1:]), label=label, color=color, lw=1.4, **kw)


def indicators(rows, spot, out):
    fig, ax = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    sd = _dt([d for d, _ in spot])
    ax[0].plot(sd, [v for _, v in spot], color=COLORS[6], lw=1.2)
    ax[0].set_title("KOSPI200 spot")
    d = _dt([r["date"] for r in rows])
    ax[1].plot(d, [r["near_atm"] if r["near_atm"] is not None else np.nan for r in rows], color=COLORS[0], label="near-month ATM IV")
    ax[1].plot(d, [r["rv20"] if r["rv20"] is not None else np.nan for r in rows], color=COLORS[1], label="20d realized vol")
    ax[1].set_title("Implied vs realized volatility (vol pts)")
    ax[1].legend(loc="upper left")
    ax[2].plot(d, [r["skew"] if r["skew"] is not None else np.nan for r in rows], color=COLORS[0], label="IV(0.90) - IV(1.10)")
    ax[2].plot(d, [r["skew25"] if r["skew25"] is not None else np.nan for r in rows], color=COLORS[2], label="IV(25d put) - IV(25d call)")
    ax[2].set_title("Near-month skew (vol pts)")
    ax[2].legend(loc="upper left")
    ax[3].plot(d, [r["term_slope"] if r["term_slope"] is not None else np.nan for r in rows], color=COLORS[3])
    ax[3].axhline(0, color="k", lw=0.6)
    ax[3].set_title("Term slope: far ATM IV - near ATM IV (vol pts)")
    _fmt_dates(ax[3])
    return _save(fig, out, "01_indicators.png")


def baseline(curves, dates, out):
    names = [("skew", COLORS[0]), ("calendar", COLORS[2]), ("vrp", COLORS[1]), ("combined", COLORS[6])]
    fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for n, c in names:
        eq = curves[f"{n}|daily"]
        _curve(ax[0], dates, eq, n, c)
        ax[1].plot(_dt(dates), 100 * np.array(drawdown_series(eq)[1:]), color=c, lw=1.4, label=n)
    ax[0].set_title("Cumulative return, daily delta-hedged (% of entry forward, additive)")
    ax[0].axhline(0, color="k", lw=0.6)
    ax[0].legend(loc="best")
    ax[1].set_title("Drawdown from peak (%)")
    _fmt_dates(ax[1])
    p1 = _save(fig, out, "02_baseline_equity_drawdown.png")

    fig, ax = plt.subplots(1, 3, figsize=(14, 4), sharex=True)
    for a, (n, _) in zip(ax, names[:3]):
        _curve(a, dates, curves[f"{n}|static"], "static hedge", COLORS[7])
        _curve(a, dates, curves[f"{n}|daily"], "daily re-hedge", COLORS[0])
        a.set_title(n)
        a.axhline(0, color="k", lw=0.6)
        _fmt_dates(a)
    ax[0].legend()
    p2 = _save(fig, out, "03_baseline_hedging.png")
    return [p1, p2]


def execution(curves, cells, dates, out):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2), sharex=True)
    styles = {(0, 15): ("same-day fill, hold<=15", COLORS[1], "-"), (0, 5): ("same-day fill, hold<=5", COLORS[1], "--"),
              (1, 15): ("next-day fill, hold<=15", COLORS[0], "-"), (1, 5): ("next-day fill, hold<=5", COLORS[0], "--")}
    for a, s in zip(ax, ("skew", "calendar", "vrp")):
        for (lag, hold), (lab, col, ls) in styles.items():
            a.plot(_dt(dates), 100 * np.array(curves[f"{s}|lag{lag}|hold{hold}"][1:]), label=lab, color=col, ls=ls, lw=1.4)
        a.set_title(f"{s} (mean of 9 W x E cells)")
        a.axhline(0, color="k", lw=0.6)
        _fmt_dates(a)
    ax[0].legend(fontsize=8)
    p1 = _save(fig, out, "04_execution_assumptions.png")

    fig = plt.figure(figsize=(10, 4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.05], wspace=0.12)
    ax = [fig.add_subplot(gs[0]), fig.add_subplot(gs[1])]
    cax = fig.add_subplot(gs[2])
    sub = cells[(cells.strategy == "skew") & (cells.hold == 5)]
    vmax = float(np.nanmax(np.abs(sub.total_return_pct)))
    for a, lag in zip(ax, (0, 1)):
        g = sub[sub.lag == lag].pivot(index="W", columns="E", values="total_return_pct")
        im = a.imshow(g.values, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto", origin="lower")
        a.set_xticks(range(len(g.columns)), [str(c) for c in g.columns])
        a.set_yticks(range(len(g.index)), [str(i) for i in g.index])
        a.set_xlabel("entry threshold |z|")
        a.grid(False)
        a.set_title("skew, " + ("same-day fill" if lag == 0 else "next-day fill"))
    ax[1].set_yticklabels([])
    ax[0].set_ylabel("z-score window")
    fig.colorbar(im, cax=cax, label="total return (%)")
    fig._skip_tight = True
    p2 = _save(fig, out, "05_skew_heatmap_window_threshold.png")
    return [p1, p2]


def cost(table, out):
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for lab, col in (("BASE", COLORS[0]), ("D25S", COLORS[2])):
        t = table[table.name == lab].sort_values("cost_iv_pt")
        ax.plot(t.cost_iv_pt, t.total_return_pct, marker="o", label=lab, color=col)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("cost per leg per transaction (IV pts)")
    ax.set_ylabel("ensemble return (%)")
    ax.set_title("Skew: sensitivity to transaction cost (next-day fill, hold<=5)")
    ax.legend()
    return _save(fig, out, "06_cost_sensitivity.png")


def combos(table, out):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    labels = list(dict.fromkeys(table.name))
    x = np.arange(len(labels))
    for k, (lag, col, lab) in enumerate(((1, COLORS[0], "next-day fill"), (0, COLORS[1], "same-day fill"))):
        t = table[table.lag == lag].set_index("name").loc[labels]
        ax.bar(x + (k - 0.5) * 0.38, t.total_return_pct, 0.38, color=col, label=lab)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(x, labels)
    ax.set_ylabel("ensemble return (%)")
    ax.set_title("Skew variants: S=stop, D=DTE>=10 filter, M=median/MAD z (hold<=5)")
    ax.legend()
    return _save(fig, out, "07_skew_variant_combos.png")


def signals(curves, dates, out):
    settings = ("lag1, cost 0.5", "lag1, cost 0", "lag0, cost 0.5")
    titles = ("next-day fill, cost 0.5", "next-day fill, cost 0", "same-day fill, cost 0.5")
    names = ["BASE", "SMA3", "D25", "D25L", "D25S", "D25SL"]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.4), sharex=True, sharey=True)
    for a, s, t in zip(ax, settings, titles):
        for n, c in zip(names, COLORS):
            _curve(a, dates, curves[f"{n}|{s}"], n, c)
        a.axhline(0, color="k", lw=0.6)
        a.set_title(t)
        _fmt_dates(a)
    ax[0].legend(fontsize=8, ncol=2)
    return _save(fig, out, "08_signal_variants.png")


def stats(x, y, a, b, primary_row, out):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].scatter(x, y, s=14, alpha=0.6, color=COLORS[0])
    xs = np.linspace(np.nanmin(x), np.nanmax(x), 50)
    ax[0].plot(xs, a + b * xs, color=COLORS[1])
    ax[0].axhline(0, color="k", lw=0.6)
    ax[0].axvline(0, color="k", lw=0.6)
    ax[0].set_xlabel("skew z-score today")
    ax[0].set_ylabel("skew change over next 10 days (vol pts)")
    ax[0].set_title("Does a high skew z-score revert? (same-expiry pairs)")
    vals = [primary_row["dskew_z_lt_m1"], primary_row["dskew_mid"], primary_row["dskew_z_gt1"]]
    ax[1].bar(["z < -1", "|z| <= 1", "z > 1"], vals, color=[COLORS[2], COLORS[7], COLORS[1]])
    ax[1].axhline(0, color="k", lw=0.6)
    ax[1].set_ylabel("mean skew change over next 10 days (vol pts)")
    ax[1].set_title("Mean subsequent skew change by z bucket")
    return _save(fig, out, "09_skew_mean_reversion.png")
