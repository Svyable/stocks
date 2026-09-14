const state = { rows: [], meta: null };

const $ = (id) => document.getElementById(id);
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

function esc(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function labelTheme(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function signalLabel(value) {
  return ({ BUY_CANDIDATE: "BUY", WATCH: "WATCH", NO_ACTION: "NO ACTION", DEFENSIVE: "DEFENSIVE", FILTERED: "FILTERED" })[value] || value;
}

function regimeClass(regime) {
  if (regime === "RISK_ON" || regime === "UPTREND_COOLING") return "risk-on";
  if (regime === "DEFENSIVE") return "defensive";
  return "neutral";
}

function deriveMeta(rows) {
  const score = rows[0]?.market_score ?? 0;
  return {
    generated_at: null,
    market: {
      regime: score >= 20 ? "RISK_ON" : score >= 16 ? "UPTREND_COOLING" : score >= 10 ? "NEUTRAL" : "DEFENSIVE",
      score,
      close: null,
      ema8: null,
      ema21: null,
      ema50: null,
    },
  };
}

function renderHeader() {
  const meta = state.meta || deriveMeta(state.rows);
  const market = meta.market || {};
  const card = $("regime-card");
  card.className = `regime-card ${regimeClass(market.regime)}`;
  $("regime").textContent = (market.regime || "UNKNOWN").replaceAll("_", " ");
  $("market-score").textContent = `${market.score ?? "—"} / 20`;

  const emaValues = [market.close, market.ema8, market.ema21, market.ema50].filter((v) => Number.isFinite(v));
  const lit = market.regime === "RISK_ON" ? 4 : market.regime === "UPTREND_COOLING" ? 3 : market.regime === "NEUTRAL" ? 2 : 1;
  $("ema-strip").innerHTML = Array.from({ length: 4 }, (_, i) => `<span class="${i < lit ? "on" : ""}"></span>`).join("");
  if (emaValues.length === 4) {
    card.title = `SPY ${market.close.toFixed(2)} · EMA8 ${market.ema8.toFixed(2)} · EMA21 ${market.ema21.toFixed(2)} · EMA50 ${market.ema50.toFixed(2)}`;
  }

  if (meta.generated_at) {
    const date = new Date(meta.generated_at);
    $("freshness").textContent = Number.isNaN(date.valueOf()) ? `Scan ${meta.generated_at}` : `Scan ${date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;
  } else {
    $("freshness").textContent = "Latest committed scan";
  }
}

function themeStats(rows) {
  const groups = new Map();
  rows.forEach((row) => {
    if (!groups.has(row.theme)) groups.set(row.theme, []);
    groups.get(row.theme).push(row);
  });
  return [...groups.entries()].map(([theme, members]) => ({
    theme,
    score: members.reduce((sum, r) => sum + Number(r.theme_score || 0), 0) / members.length,
    leader: Math.max(...members.map((r) => Number(r.total_score || 0))),
    count: members.length,
  })).sort((a, b) => b.score - a.score || b.leader - a.leader);
}

function heat(score) {
  if (score >= 17) return "#26d980";
  if (score >= 14) return "#249d71";
  if (score >= 10) return "#2c7095";
  if (score >= 6) return "#80633e";
  return "#8e3540";
}

function renderSummary() {
  const rows = state.rows;
  const buys = rows.filter((r) => r.action === "BUY_CANDIDATE");
  const watches = rows.filter((r) => r.action === "WATCH");
  const top = rows[0];
  const themes = themeStats(rows);
  $("buy-count").textContent = buys.length;
  $("watch-count").textContent = watches.length;
  $("top-score").textContent = top ? Number(top.total_score).toFixed(1) : "—";
  $("top-score-name").textContent = top ? `${top.ticker} · ${signalLabel(top.action)}` : "—";
  $("top-theme").textContent = themes[0] ? labelTheme(themes[0].theme) : "—";
  $("top-theme-score").textContent = themes[0] ? `${themes[0].score.toFixed(1)} / 20 theme score` : "—";

  const banner = $("signal-banner");
  if (buys.length) {
    banner.hidden = false;
    banner.textContent = `${buys.length} confirmed buy candidate${buys.length === 1 ? "" : "s"}: ${buys.map((r) => r.ticker).join(", ")}. Confirm live market data before acting.`;
  } else {
    banner.hidden = true;
  }
}

function renderThemes() {
  const themes = themeStats(state.rows);
  $("themes").innerHTML = themes.map((item) => `
    <button class="theme" type="button" data-theme="${esc(item.theme)}" style="--heat:${heat(item.score)}" title="Filter rankings to ${esc(labelTheme(item.theme))}">
      <strong>${esc(labelTheme(item.theme))}</strong>
      <b>${item.score.toFixed(1)}</b>
      <span>${item.count} names · leader ${item.leader.toFixed(1)}</span>
    </button>
  `).join("");

  document.querySelectorAll(".theme").forEach((button) => button.addEventListener("click", () => {
    $("search").value = button.dataset.theme;
    renderTable();
    document.querySelector(".rankings-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  }));
}

function scoreStack(row) {
  const parts = [
    ["market", Number(row.market_score || 0), 20],
    ["theme-score", Number(row.theme_score || 0), 20],
    ["leader", Number(row.leader_score || 0), 25],
    ["setup", Number(row.setup_score || 0), 20],
    ["breakout", Number(row.breakout_score || 0), 15],
  ];
  const title = `Market ${parts[0][1].toFixed(1)}/20 · Theme ${parts[1][1].toFixed(1)}/20 · Leader ${parts[2][1].toFixed(1)}/25 · Setup ${parts[3][1].toFixed(1)}/20 · Breakout ${parts[4][1].toFixed(1)}/15`;
  return `<div class="score-stack" title="${esc(title)}">${parts.map(([name, value]) => `<i class="${name}" style="width:${Math.max(value, 0)}%"></i>`).join("")}</div>`;
}

function renderTable() {
  const query = $("search").value.trim().toLowerCase();
  const action = $("action-filter").value;
  const rows = state.rows.filter((row) => {
    const matchesAction = action === "ALL" || row.action === action;
    const haystack = `${row.ticker} ${row.theme} ${labelTheme(row.theme)}`.toLowerCase();
    return matchesAction && (!query || haystack.includes(query));
  });

  if (!rows.length) {
    $("rankings").innerHTML = `<tr><td colspan="10" class="empty">No names match this filter.</td></tr>`;
    return;
  }

  $("rankings").innerHTML = rows.map((row) => `
    <tr>
      <td class="rank">#${row.rank}</td>
      <td class="stock"><a href="https://finance.yahoo.com/quote/${encodeURIComponent(row.ticker)}" target="_blank" rel="noreferrer"><strong>${esc(row.ticker)} ↗</strong></a><small>${esc(labelTheme(row.theme))}</small></td>
      <td><span class="signal signal-${String(row.action).toLowerCase()}">${esc(signalLabel(row.action))}</span></td>
      <td class="num score"><strong>${Number(row.total_score).toFixed(1)}</strong></td>
      <td class="num">${money.format(row.price)}</td>
      <td class="num">${money.format(row.trigger)}</td>
      <td class="num">${money.format(row.stop)}</td>
      <td class="num">${money.format(row.target_2r)}</td>
      <td class="num" title="Current volume / 20-day average">${pct.format(row.volume_ratio)}×</td>
      <td>${scoreStack(row)}</td>
    </tr>
  `).join("");
}

function render() {
  renderHeader();
  renderSummary();
  renderThemes();
  renderTable();
}

async function load() {
  try {
    const [rankResponse, metaResponse] = await Promise.all([
      fetch("data/latest.json", { cache: "no-store" }),
      fetch("data/meta.json", { cache: "no-store" }).catch(() => null),
    ]);
    if (!rankResponse.ok) throw new Error(`ranking HTTP ${rankResponse.status}`);
    state.rows = await rankResponse.json();
    if (metaResponse?.ok) state.meta = await metaResponse.json();
    render();
  } catch (error) {
    console.error(error);
    $("rankings").innerHTML = `<tr><td colspan="10" class="empty">Could not load the latest scan. Check the repository Actions run.</td></tr>`;
    $("freshness").textContent = "Data unavailable";
  }
}

$("search").addEventListener("input", renderTable);
$("action-filter").addEventListener("change", renderTable);
load();
