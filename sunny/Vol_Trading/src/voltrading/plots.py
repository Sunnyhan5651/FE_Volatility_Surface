"""시각화: IV vs HV 시계열, VRP 분포, 전략별 누적 손익."""
from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib import font_manager

# 한글 폰트 설정
_have = {f.name for f in font_manager.fontManager.ttflist}
for _fn in ("AppleGothic", "Malgun Gothic", "NanumGothic", "Noto Sans CJK KR"):
    if _fn in _have:
        plt.rcParams["font.family"] = _fn
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.25,
    "figure.dpi":        150,
})

BLUE  = "#0072B2"
RED   = "#D55E00"
GREEN = "#009E73"
GRAY  = "#888888"


def _xaxis(ax, dates):
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    return x


# ── 1. IV vs HV 시계열 ────────────────────────────────────
def plot_iv_hv(rows: List[dict], out_dir: Path):
    dates  = [r["date"] for r in rows]
    iv     = [r["atm_iv"] for r in rows]
    hv     = [r["rv20"]   for r in rows]
    vrp    = [r["vrp"]    for r in rows]

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")

    ax = axes[0]
    ax.plot(x, iv,  color=BLUE,  lw=1.5, label="ATM IV (근월물, %)")
    ax.plot(x, hv,  color=RED,   lw=1.5, label="20일 실현변동성 HV (%)", alpha=0.85)
    ax.set_ylabel("변동성 (%)")
    ax.legend(frameon=False)
    ax.set_title("KOSPI200 옵션 — ATM IV vs 실현변동성(HV)", fontsize=13, fontweight="bold")

    ax2 = axes[1]
    vrp_arr = np.array([v if v is not None else np.nan for v in vrp])
    ax2.fill_between(x, vrp_arr, 0,
                     where=(vrp_arr > 0), color=RED,   alpha=0.35, label="VRP > 0 (IV > HV, short vol 우위)")
    ax2.fill_between(x, vrp_arr, 0,
                     where=(vrp_arr < 0), color=BLUE,  alpha=0.35, label="VRP < 0 (IV < HV, long vol 우위)")
    ax2.axhline(0, color="k", lw=0.8)
    ax2.set_ylabel("VRP = IV − HV (%p)")
    ax2.set_xlabel("날짜")
    ax2.legend(frameon=False)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    fig.tight_layout()
    path = out_dir / "01_IV_vs_HV.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path.name}")


# ── 2. VRP 분포 히스토그램 ────────────────────────────────
def plot_vrp_dist(rows: List[dict], out_dir: Path):
    vrp = [r["vrp"] for r in rows if r["vrp"] is not None]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(vrp, bins=50, color=BLUE, alpha=0.7, edgecolor="white")
    ax.axvline(0,            color="k",   lw=1.2, linestyle="--", label="VRP = 0")
    ax.axvline(np.mean(vrp), color=RED,   lw=1.5, linestyle="-",  label=f"평균 VRP = {np.mean(vrp):.1f}%p")
    ax.set_xlabel("VRP = ATM IV − 20일 HV (%p)")
    ax.set_ylabel("빈도")
    ax.set_title("VRP 분포 — IV > HV 구조적 프리미엄 확인", fontsize=12, fontweight="bold")
    ax.legend(frameon=False)
    pct_pos = 100 * sum(v > 0 for v in vrp) / len(vrp)
    ax.text(0.98, 0.93, f"VRP > 0 비율: {pct_pos:.1f}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10, color=RED,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=RED, alpha=0.8))
    fig.tight_layout()
    path = out_dir / "02_VRP_distribution.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path.name}")


# ── 3. 기간구조 시계열 ────────────────────────────────────
def plot_term_structure(rows: List[dict], out_dir: Path):
    dates = [r["date"]       for r in rows]
    ts    = [r["term_slope"] for r in rows]
    fig, ax = plt.subplots(figsize=(12, 4))
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")
    ts_arr = np.array([v if v is not None else np.nan for v in ts])
    ax.fill_between(x, ts_arr, 0,
                    where=(ts_arr > 0), color=GREEN, alpha=0.4, label="우상향 (단기 IV < 장기 IV)")
    ax.fill_between(x, ts_arr, 0,
                    where=(ts_arr < 0), color=RED,   alpha=0.4, label="역전 (단기 IV > 장기 IV, 위기)")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("기간구조 기울기 (원월 − 근월 ATM IV, %p)")
    ax.set_xlabel("날짜")
    ax.set_title("변동성 기간구조 — 역전 구간은 위기 국면", fontsize=12, fontweight="bold")
    ax.legend(frameon=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.tight_layout()
    path = out_dir / "03_term_structure.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path.name}")


# ── 4. 전략별 누적 손익 ───────────────────────────────────
def plot_strategy_equity(results: list, dates: list, out_dir: Path):
    """results: [{name, equity_same, equity_next}, ...]"""
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")
    for i, res in enumerate(results):
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(x, 100 * np.array(res["equity_same"][1:]), color=RED,  lw=1.8, label="당일 종가 체결")
        ax.plot(x, 100 * np.array(res["equity_next"][1:]), color=BLUE, lw=1.8, label="익일 종가 체결", alpha=0.85)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title(res["name"], fontsize=13, fontweight="bold")
        ax.set_ylabel("누적 수익률 (%p)")
        ax.set_xlabel("날짜")
        ax.legend(frameon=False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        # 성과 요약 박스
        m = res["metrics_same"]
        txt = (f"Sharpe {m['sharpe']:.2f}  |  MDD {m['mdd_pct']:.1f}%p  |"
               f"  승률 {m['win_rate_pct']:.0f}%  |  거래 {m['effective_trades']}건")
        ax.text(0.01, 0.97, txt, transform=ax.transAxes,
                fontsize=9, va="top", color="#333333",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=GRAY, alpha=0.8))
        fig.tight_layout()
        idx = str(i + 4).zfill(2)
        path = out_dir / f"{idx}_{res['tag']}.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        print(f"  저장: {path.name}")


# ── 5. 전략 비교 요약 ─────────────────────────────────────
def plot_summary(results: list, dates: list, out_dir: Path):
    fig, ax = plt.subplots(figsize=(12, 5))
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")
    colors = [RED, BLUE, GREEN]
    for res, col in zip(results, colors):
        eq = np.array(res["equity_same"][1:])
        ax.plot(x, 100 * eq, color=col, lw=2, label=res["name"])
    ax.axhline(0, color="k", lw=0.8, linestyle="--")
    ax.set_title("IV 기반 변동성 트레이딩 전략 비교", fontsize=13, fontweight="bold")
    ax.set_ylabel("누적 수익률 (%p)")
    ax.set_xlabel("날짜")
    ax.legend(frameon=False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.tight_layout()
    path = out_dir / "07_strategy_comparison.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  저장: {path.name}")
