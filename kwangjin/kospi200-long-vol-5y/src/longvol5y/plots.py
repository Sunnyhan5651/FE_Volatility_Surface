"""전략마다 그래프 1장: 누적수익률 선 하나."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def _korean_font(plt):
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    for fam in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans CJK JP"):
        if fam in names:
            plt.rcParams["font.family"] = fam
            break
    plt.rcParams["axes.unicode_minus"] = False


def figure(result, dates):
    import matplotlib.pyplot as plt
    _korean_font(plt)
    x = [datetime.strptime(d, "%Y%m%d") for d in dates]
    m = result.metrics
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(x, m["curve"], color="#2a6fdb", lw=1.6, label=f"계속 보유  {m['누적수익률']:+.2f}%")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_title(result.name)
    ax.set_ylabel("누적수익률 (%)")
    ax.legend(frameon=False, loc="best")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def show_all(results, dates, save_dir=None):
    """화면에 전략별 그래프를 띄운다. save_dir 을 주면 PNG 로도 저장한다."""
    import matplotlib.pyplot as plt
    for k, r in enumerate(results, 1):
        fig = figure(r, dates)
        if save_dir:
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            safe = r.name.replace(" + ", "_").replace("/", "-").replace(" ", "_")
            fig.savefig(Path(save_dir) / f"{k:02d}_{safe}.png", dpi=130)
    plt.show()
