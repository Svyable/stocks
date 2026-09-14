from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from .data import download_history
from .scoring import rank_universe


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _symbols(config: dict) -> set[str]:
    symbols = {config.get("benchmark", "SPY").upper()}
    for spec in config["themes"].values():
        symbols.add(spec["etf"].upper())
        symbols.update(t.upper() for t in spec["tickers"])
    return symbols


def _write_report(ranked: pd.DataFrame, market, out_dir: Path, top: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(out_dir / "latest.csv", index=False)
    (out_dir / "latest.json").write_text(
        json.dumps(ranked.to_dict(orient="records"), indent=2), encoding="utf-8"
    )

    generated_at = datetime.now(timezone.utc)
    metadata = {
        "generated_at": generated_at.isoformat(),
        "market": {
            "regime": market.regime,
            "score": market.score,
            "close": market.close,
            "ema8": market.ema8,
            "ema21": market.ema21,
            "ema50": market.ema50,
        },
        "ranked_count": int(len(ranked)),
        "buy_candidate_count": int((ranked["action"] == "BUY_CANDIDATE").sum()) if "action" in ranked else 0,
        "watch_count": int((ranked["action"] == "WATCH").sum()) if "action" in ranked else 0,
    }
    (out_dir / "meta.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    as_of = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    if ranked.empty:
        table = "No qualifying symbols returned."
    else:
        columns = [
            "rank",
            "ticker",
            "theme",
            "action",
            "total_score",
            "price",
            "trigger",
            "stop",
            "target_2r",
            "volume_ratio",
        ]
        table = ranked.head(top)[columns].to_markdown(index=False)

    report = f"""# Latest stack ranking

Generated: {as_of}

Market regime: **{market.regime}** — market score **{market.score:.0f}/20**.
SPY: close {market.close:.2f} | EMA8 {market.ema8:.2f} | EMA21 {market.ema21:.2f} | EMA50 {market.ema50:.2f}

## Ranked candidates

{table}

## Signal meaning

- `BUY_CANDIDATE`: market + theme + leader + setup all score well and the stock has a confirmed 20-day breakout with volume.
- `WATCH`: strong enough to stalk, but the breakout/volume confirmation is not complete.
- `DEFENSIVE`: market or stock trend gate failed; do not treat the score as a long entry.
- `FILTERED`: failed price/liquidity minimums.

This is a rules-based research screen, not individualized investment advice. Verify prices, liquidity, earnings dates, news, and your own risk limits before trading.
"""
    (out_dir / "latest.md").write_text(report, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank momentum/breakout stocks from strongest themes")
    parser.add_argument("--config", default="config/universe.yaml")
    parser.add_argument("--period", default="1y")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--top", type=int, default=30)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = _load_config(Path(args.config))
    history = download_history(_symbols(config), period=args.period)
    ranked, market = rank_universe(config, history)
    _write_report(ranked, market, Path(args.output_dir), args.top)

    print(f"Market: {market.regime} ({market.score:.0f}/20)")
    if ranked.empty:
        print("No ranked symbols returned")
    else:
        print(ranked.head(args.top).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
