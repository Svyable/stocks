import json
from types import SimpleNamespace

import pandas as pd

from stocks_ranker.cli import _write_report


def test_report_keeps_rankings_json_and_emits_dashboard_metadata(tmp_path):
    ranked = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "TEST",
                "theme": "example",
                "action": "WATCH",
                "total_score": 68.0,
                "price": 100.0,
                "trigger": 102.0,
                "stop": 96.0,
                "target_2r": 114.0,
                "volume_ratio": 1.1,
            }
        ]
    )
    market = SimpleNamespace(
        regime="NEUTRAL",
        score=10.0,
        close=500.0,
        ema8=499.0,
        ema21=498.0,
        ema50=490.0,
    )

    _write_report(ranked, market, tmp_path, top=10)

    ranking = json.loads((tmp_path / "latest.json").read_text())
    meta = json.loads((tmp_path / "meta.json").read_text())

    assert isinstance(ranking, list)
    assert ranking[0]["ticker"] == "TEST"
    assert meta["market"]["regime"] == "NEUTRAL"
    assert meta["market"]["score"] == 10.0
    assert meta["ranked_count"] == 1
    assert meta["buy_candidate_count"] == 0
    assert meta["watch_count"] == 1
    assert meta["generated_at"].endswith("+00:00")
