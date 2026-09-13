import numpy as np
import pandas as pd

from stocks_ranker.scoring import market_state, score_stock


def frame(start=100.0, drift=0.4, days=90, breakout=False, volume_spike=False):
    idx = pd.date_range("2026-01-01", periods=days, freq="B")
    close = start + np.arange(days) * drift
    if breakout:
        close[-1] = close[-2] + 4.0
    high = close + 1.0
    low = close - 1.0
    volume = np.full(days, 1_000_000.0)
    if volume_spike:
        volume[-1] = 2_000_000.0
    return pd.DataFrame(
        {"Open": close - 0.2, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def test_market_state_detects_risk_on_uptrend():
    state = market_state(frame())
    assert state.regime == "RISK_ON"
    assert state.score == 20.0
    assert state.close > state.ema8 > state.ema21 > state.ema50


def test_confirmed_breakout_can_be_buy_candidate():
    stock = frame(drift=0.5, breakout=True, volume_spike=True)
    spy = frame(drift=0.15)
    state = market_state(spy)
    result = score_stock(
        ticker="TEST",
        theme="test_theme",
        frame=stock,
        benchmark_frame=spy,
        market=state,
        theme_score=20.0,
        min_price=5.0,
        min_avg_dollar_volume_20d=1_000_000,
        account_risk_pct=1.0,
        max_position_pct=25.0,
    )
    assert result["action"] == "BUY_CANDIDATE"
    assert result["total_score"] >= 75
    assert result["trigger"] > 0
    assert result["stop"] < result["trigger"]
    assert result["target_2r"] > result["trigger"]
    assert 0 < result["max_position_pct_at_configured_risk"] <= 25


def test_illiquid_stock_is_filtered():
    stock = frame()
    spy = frame(drift=0.15)
    result = score_stock(
        ticker="TEST",
        theme="test_theme",
        frame=stock,
        benchmark_frame=spy,
        market=market_state(spy),
        theme_score=20.0,
        min_price=5.0,
        min_avg_dollar_volume_20d=10_000_000_000,
        account_risk_pct=1.0,
        max_position_pct=25.0,
    )
    assert result["action"] == "FILTERED"
