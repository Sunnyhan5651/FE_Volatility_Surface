"""전략당 그래프 1개 (선 2개: 당일 체결 / 익일 체결). 화면에 표시하고, save_dir 을 주면 PNG 로도 저장한다."""
from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pathlib import Path

from matplotlib import font_manager

_have = {f.name for f in font_manager.fontManager.ttflist}
for _name in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"):     # 설치된 한글 폰트를 하나 고른다
    if _name in _have:
        plt.rcParams["font.family"] = _name
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25})


def strategy_figure(name: str, dates, eq_same_day, eq_next_day):
    x = pd.to_datetime(pd.Series(dates), format="%Y%m%d")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x, 100 * np.array(eq_same_day[1:]), label=f"당일 체결  {100 * eq_same_day[-1]:+.2f}%", color="#D55E00", lw=1.4)
    ax.plot(x, 100 * np.array(eq_next_day[1:]), label=f"익일 체결  {100 * eq_next_day[-1]:+.2f}%", color="#0072B2", lw=1.4)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_title(name)
    ax.set_ylabel("누적 수익률 (%)")
    span = (x.iloc[-1] - x.iloc[0]).days
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6 if span > 730 else 2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    return fig


def show_all(results, dates, save_dir=None):
    """전략별 그림을 모두 만든 뒤 한 번에 표시한다. save_dir 을 주면 PNG 로도 저장한다."""
    by = {}
    for r in results:
        by.setdefault(r["strategy"], {})[r["fill"]] = r["equity"]
    for k, (name, eqs) in enumerate(by.items(), 1):
        fig = strategy_figure(name, dates, eqs["당일 체결"], eqs["익일 체결"])
        if save_dir:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            safe = name.replace(" + ", "_").replace(" ", "_").replace("(", "").replace(")", "")
            fig.savefig(Path(save_dir) / f"{k:02d}_{safe}.png", dpi=130)
    plt.show()
