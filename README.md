# Svyable Stocks

A rules-based momentum scanner that turns a top-down market process into a **stack-ranked list of stocks to buy, watch, or avoid**.

The ranking model follows the six-part process in the reference image:

1. **Analyze the market** — SPY 8/21/50 EMA regime.
2. **Find the strongest themes** — theme ETF relative strength plus member breadth.
3. **Pick the leaders** — stock relative strength, proximity to highs, volume trend, and price trend.
4. **Wait for the setup** — consolidation tightness, ATR compression, EMA posture, and proximity to a 20-day breakout.
5. **Execute on the breakout** — price above the prior 20-day high with volume confirmation.
6. **Manage risk** — trigger, logical stop, 2R target, stop distance, and position-size ceiling at the configured account risk.

## Live dashboard

The repository includes a zero-build static dashboard in `site/` designed for GitHub Pages. It shows the current market regime, buy/watch counts, theme strength, the full ranked stack, score-component bars, and trigger/stop/2R levels.

Once GitHub Pages is configured to use **GitHub Actions** as its publishing source, the scan workflow deploys the dashboard after each successful main-branch, scheduled, or manual scan. The expected project URL is:

`https://svyable.github.io/stocks/`

## Output

Each run writes:

- `output/latest.csv` — full stack ranking.
- `output/latest.json` — machine-readable ranking.
- `output/latest.md` — human-readable top list and market regime.
- `output/meta.json` — scan timestamp and market-regime metadata used by the dashboard.

The most important `action` values are:

- `BUY_CANDIDATE` — score >= 75, favorable market regime, positive stock trend, confirmed breakout, and volume >= 1.2x the 20-day average.
- `WATCH` — strong enough to stalk, but entry confirmation is incomplete.
- `DEFENSIVE` — market or stock trend gate failed.
- `FILTERED` — price/liquidity requirements failed.

A high score by itself is **not** a buy. The final gate requires the right environment and confirmation.

## Starter universe

`config/universe.yaml` contains a starter set across semiconductors, AI/software, nuclear, aerospace/space, robotics, financials/fintech, energy, biotech, cyber security, and internet/consumer themes. Edit that file to add/remove names or change theme ETFs.

The default liquidity filter is $20M of 20-day average dollar volume and a $5 minimum share price.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
stock-rank
```

Useful options:

```bash
stock-rank --config config/universe.yaml --period 1y --top 40 --output-dir output
```

## Scoring

The score is out of 100:

| Component | Points | What it measures |
|---|---:|---|
| Market | 20 | SPY trend using 8/21/50 EMAs |
| Theme | 20 | ETF relative strength + breadth |
| Leader | 25 | 20/60-day relative strength, highs, volume |
| Setup | 20 | Tightness, ATR, EMA posture, breakout proximity |
| Breakout | 15 | 20-day breakout + volume confirmation |

The ranker also emits a trigger, stop, 2R target, and a maximum position percentage based on `risk.account_risk_per_trade_pct` and `risk.max_position_pct` in the YAML config.

## Automation

GitHub Actions runs tests on pushes/PRs and runs the scanner on weekdays at 21:30 UTC. Main-branch, scheduled, and manual scans commit refreshed `output/latest.*` plus `output/meta.json` files back to `main`, then deploy the static dashboard to GitHub Pages.

The scheduled time is deliberately after the U.S. cash-market close; daylight-saving changes can shift how long after the close the job runs.

## Important caveat

This repository is a systematic **research and screening** tool, not individualized investment advice. Market data can be delayed or incomplete. Verify live price/volume, earnings dates, corporate actions, news, liquidity, and your own risk limits before trading.
