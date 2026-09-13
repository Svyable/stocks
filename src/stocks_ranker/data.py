from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import yfinance as yf


REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def download_history(tickers: Iterable[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Download adjusted daily OHLCV data and normalize it into one frame per ticker."""
    symbols = sorted({t.upper() for t in tickers if t})
    if not symbols:
        return {}

    raw = yf.download(
        tickers=" ".join(symbols),
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if raw.empty:
        raise RuntimeError("No market data returned by yfinance")

    frames: dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(raw.columns.get_level_values(0))
        level1 = set(raw.columns.get_level_values(1))
        for ticker in symbols:
            if ticker in level0:
                frame = raw[ticker].copy()
            elif ticker in level1:
                frame = raw.xs(ticker, axis=1, level=1).copy()
            else:
                continue
            frame = _normalize(frame)
            if not frame.empty:
                frames[ticker] = frame
    elif len(symbols) == 1:
        frame = _normalize(raw.copy())
        if not frame.empty:
            frames[symbols[0]] = frame

    return frames


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.rename(columns={str(c).title(): str(c).title() for c in frame.columns})
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    frame = frame[REQUIRED_COLUMNS].dropna(subset=["Close"]).copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame
