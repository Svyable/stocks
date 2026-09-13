from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MarketState:
    score: float
    regime: str
    close: float
    ema8: float
    ema21: float
    ema50: float


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = frame["Close"].shift(1)
    tr = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - prev_close).abs(),
            (frame["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def period_return(series: pd.Series, days: int) -> float:
    if len(series) <= days or series.iloc[-days - 1] == 0:
        return float("nan")
    return float(series.iloc[-1] / series.iloc[-days - 1] - 1)


def market_state(frame: pd.DataFrame) -> MarketState:
    close = frame["Close"]
    e8 = float(ema(close, 8).iloc[-1])
    e21 = float(ema(close, 21).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    c = float(close.iloc[-1])
    if c > e8 > e21 > e50:
        return MarketState(20.0, "RISK_ON", c, e8, e21, e50)
    if c > e21 > e50:
        return MarketState(16.0, "UPTREND_COOLING", c, e8, e21, e50)
    if c > e50:
        return MarketState(10.0, "NEUTRAL", c, e8, e21, e50)
    return MarketState(0.0, "DEFENSIVE", c, e8, e21, e50)


def _pct_rank(values: pd.Series) -> pd.Series:
    if values.notna().sum() <= 1:
        return pd.Series(0.5, index=values.index)
    return values.rank(pct=True, method="average").fillna(0.0)


def score_themes(
    themes: dict[str, dict],
    history: dict[str, pd.DataFrame],
    benchmark: str,
) -> dict[str, float]:
    spy = history[benchmark]["Close"]
    rows: list[dict] = []
    for name, spec in themes.items():
        etf = spec["etf"].upper()
        if etf not in history:
            continue
        etf_close = history[etf]["Close"]
        member_flags_21: list[float] = []
        member_flags_50: list[float] = []
        for ticker in spec["tickers"]:
            frame = history.get(ticker.upper())
            if frame is None or len(frame) < 55:
                continue
            c = float(frame["Close"].iloc[-1])
            member_flags_21.append(float(c > ema(frame["Close"], 21).iloc[-1]))
            member_flags_50.append(float(c > ema(frame["Close"], 50).iloc[-1]))
        rows.append(
            {
                "theme": name,
                "excess20": period_return(etf_close, 20) - period_return(spy, 20),
                "excess60": period_return(etf_close, 60) - period_return(spy, 60),
                "breadth21": np.mean(member_flags_21) if member_flags_21 else 0.0,
                "breadth50": np.mean(member_flags_50) if member_flags_50 else 0.0,
            }
        )
    if not rows:
        return {name: 0.0 for name in themes}
    metrics = pd.DataFrame(rows).set_index("theme")
    composite = (
        0.35 * _pct_rank(metrics["excess20"])
        + 0.30 * _pct_rank(metrics["excess60"])
        + 0.20 * _pct_rank(metrics["breadth21"])
        + 0.15 * _pct_rank(metrics["breadth50"])
    )
    return {name: round(float(score * 20), 2) for name, score in composite.items()}


def _clip_score(value: float, low: float, high: float, points: float) -> float:
    if np.isnan(value):
        return 0.0
    if high == low:
        return 0.0
    return float(np.clip((value - low) / (high - low), 0, 1) * points)


def score_stock(
    ticker: str,
    theme: str,
    frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    market: MarketState,
    theme_score: float,
    min_price: float,
    min_avg_dollar_volume_20d: float,
    account_risk_pct: float,
    max_position_pct: float,
) -> dict:
    if len(frame) < 65:
        raise ValueError(f"{ticker}: insufficient history")

    close = frame["Close"]
    c = float(close.iloc[-1])
    e8 = float(ema(close, 8).iloc[-1])
    e21 = float(ema(close, 21).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    atr14 = float(atr(frame, 14).iloc[-1])
    avg_vol20 = float(frame["Volume"].tail(20).mean())
    avg_vol60 = float(frame["Volume"].tail(60).mean())
    vol_ratio = float(frame["Volume"].iloc[-1] / avg_vol20) if avg_vol20 else 0.0
    dollar_vol20 = avg_vol20 * c

    spy_close = benchmark_frame["Close"]
    excess20 = period_return(close, 20) - period_return(spy_close, 20)
    excess60 = period_return(close, 60) - period_return(spy_close, 60)
    high_252 = float(close.tail(252).max())
    high_proximity = c / high_252 if high_252 else 0.0
    volume_trend = avg_vol20 / avg_vol60 if avg_vol60 else 0.0

    leader_score = (
        _clip_score(excess20, -0.10, 0.20, 8)
        + _clip_score(excess60, -0.15, 0.35, 8)
        + _clip_score(high_proximity, 0.75, 1.0, 5)
        + _clip_score(volume_trend, 0.80, 1.50, 4)
    )

    prior20_high = float(frame["High"].iloc[-21:-1].max())
    gap_to_breakout = prior20_high / c - 1 if c else float("nan")
    range10 = float((frame["High"].tail(10).max() - frame["Low"].tail(10).min()) / c)
    atr_pct = atr14 / c if c else float("nan")
    setup_score = (
        _clip_score(0.08 - max(gap_to_breakout, 0.0), 0.0, 0.08, 7)
        + _clip_score(0.18 - range10, 0.0, 0.15, 6)
        + _clip_score(0.08 - atr_pct, 0.0, 0.06, 4)
        + (3.0 if c >= e8 >= e21 else 1.0 if c >= e21 else 0.0)
    )

    broke_out = c > prior20_high
    breakout_score = 8.0 if broke_out else 4.0 if gap_to_breakout <= 0.02 else 0.0
    breakout_score += 7.0 if vol_ratio >= 1.5 else 4.0 if vol_ratio >= 1.2 else 1.0 if vol_ratio >= 1.0 else 0.0

    total = float(market.score + theme_score + leader_score + setup_score + breakout_score)
    liquid = c >= min_price and dollar_vol20 >= min_avg_dollar_volume_20d
    trend_ok = c > e21 > e50
    confirmed = broke_out and vol_ratio >= 1.2

    if not liquid:
        action = "FILTERED"
    elif market.score < 10 or c < e50:
        action = "DEFENSIVE"
    elif total >= 75 and market.score >= 16 and trend_ok and confirmed:
        action = "BUY_CANDIDATE"
    elif total >= 65 and trend_ok:
        action = "WATCH"
    else:
        action = "NO_ACTION"

    trigger = prior20_high * 1.001
    entry = c if confirmed else trigger
    raw_stop = max(e21, entry - 2 * atr14)
    stop = min(entry * 0.995, raw_stop)
    risk_per_share = max(entry - stop, entry * 0.005)
    risk_pct = risk_per_share / entry
    target_2r = entry + 2 * risk_per_share
    # account_risk_pct is expressed as a percent (1.0 == 1%); risk_pct is decimal.
    position_pct = min(max_position_pct, account_risk_pct / risk_pct)

    return {
        "ticker": ticker,
        "theme": theme,
        "action": action,
        "total_score": round(total, 2),
        "market_score": round(market.score, 2),
        "theme_score": round(theme_score, 2),
        "leader_score": round(leader_score, 2),
        "setup_score": round(setup_score, 2),
        "breakout_score": round(breakout_score, 2),
        "price": round(c, 2),
        "ema8": round(e8, 2),
        "ema21": round(e21, 2),
        "ema50": round(e50, 2),
        "relative_20d_pct": round(excess20 * 100, 2),
        "relative_60d_pct": round(excess60 * 100, 2),
        "volume_ratio": round(vol_ratio, 2),
        "gap_to_breakout_pct": round(gap_to_breakout * 100, 2),
        "avg_dollar_volume_20d": round(dollar_vol20, 0),
        "trigger": round(trigger, 2),
        "stop": round(stop, 2),
        "target_2r": round(target_2r, 2),
        "stop_distance_pct": round(risk_pct * 100, 2),
        "max_position_pct_at_configured_risk": round(position_pct, 2),
    }


def rank_universe(config: dict, history: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, MarketState]:
    benchmark = config.get("benchmark", "SPY").upper()
    if benchmark not in history:
        raise RuntimeError(f"Missing benchmark history for {benchmark}")
    market = market_state(history[benchmark])
    theme_scores = score_themes(config["themes"], history, benchmark)
    filters = config.get("filters", {})
    risk = config.get("risk", {})

    # A ticker can belong to more than one theme. Attribute it to whichever theme
    # is strongest today so the final stack contains each ticker only once.
    ticker_theme: dict[str, str] = {}
    for theme, spec in config["themes"].items():
        for raw_ticker in spec["tickers"]:
            ticker = raw_ticker.upper()
            current = ticker_theme.get(ticker)
            if current is None or theme_scores.get(theme, 0.0) > theme_scores.get(current, 0.0):
                ticker_theme[ticker] = theme

    rows: list[dict] = []
    for ticker, theme in ticker_theme.items():
        if ticker not in history:
            continue
        try:
            rows.append(
                score_stock(
                    ticker=ticker,
                    theme=theme,
                    frame=history[ticker],
                    benchmark_frame=history[benchmark],
                    market=market,
                    theme_score=theme_scores.get(theme, 0.0),
                    min_price=float(filters.get("min_price", 5.0)),
                    min_avg_dollar_volume_20d=float(filters.get("min_avg_dollar_volume_20d", 20_000_000)),
                    account_risk_pct=float(risk.get("account_risk_per_trade_pct", 1.0)),
                    max_position_pct=float(risk.get("max_position_pct", 25.0)),
                )
            )
        except ValueError:
            continue

    ranked = pd.DataFrame(rows)
    if ranked.empty:
        return ranked, market
    priority = {"BUY_CANDIDATE": 0, "WATCH": 1, "NO_ACTION": 2, "DEFENSIVE": 3, "FILTERED": 4}
    ranked["_priority"] = ranked["action"].map(priority).fillna(9)
    ranked = ranked.sort_values(["_priority", "total_score"], ascending=[True, False]).drop(columns="_priority")
    ranked.insert(0, "rank", np.arange(1, len(ranked) + 1))
    return ranked.reset_index(drop=True), market
