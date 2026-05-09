import "dotenv/config";
import nodemailer from "nodemailer";

const TODAY = new Date().toLocaleDateString("en-CA", {
  timeZone: "America/New_York",
});

const RECIPIENT = "andrewric86@gmail.com";

// ── 1. Fetch live market data ─────────────────────────────────────────────────

async function fetchMarketData() {
  const [cgRes, fgRes] = await Promise.all([
    fetch(
      "https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false"
    ),
    fetch("https://api.alternative.me/fng/?limit=2"),
  ]);

  const cg = await cgRes.json();
  const fg = (await fgRes.json()).data;
  const md = cg.market_data;

  return {
    price:        md.current_price.usd,
    change24h:    md.price_change_percentage_24h,
    change7d:     md.price_change_percentage_7d,
    change30d:    md.price_change_percentage_30d,
    volume24h:    md.total_volume.usd,
    marketCap:    md.market_cap.usd,
    ath:          md.ath.usd,
    athChangePct: md.ath_change_percentage.usd,
    high24h:      md.high_24h.usd,
    low24h:       md.low_24h.usd,
    fgValue:      parseInt(fg[0].value),
    fgLabel:      fg[0].value_classification,
    fgPrev:       parseInt(fg[1].value),
  };
}

// ── 2. Rule-based analysis ────────────────────────────────────────────────────

function analyse(d) {
  const { price, change24h, change7d, change30d, volume24h, marketCap, ath, athChangePct, high24h, low24h, fgValue, fgPrev } = d;

  // Direction
  const direction =
    change24h > 2 && change7d > 3 ? "UP" :
    change24h < -2 && change7d < -3 ? "DOWN" : "SIDEWAYS";

  // Volume
  const volRatio = (volume24h / marketCap) * 100;
  const volume = volRatio > 6 ? "HIGH" : volRatio < 2.5 ? "LOW" : "NORMAL";

  // Sentiment
  const sentiment =
    fgValue >= 75 ? { label: "EXTREME GREED", note: "Market is overheated — risk of sharp pullback is elevated." } :
    fgValue >= 55 ? { label: "GREED",         note: "Bullish momentum present but watch for complacency." } :
    fgValue >= 45 ? { label: "NEUTRAL",        note: "No strong directional bias — wait for a clearer signal." } :
    fgValue >= 25 ? { label: "FEAR",           note: "Bearish sentiment dominates — historically a buying opportunity area." } :
                    { label: "EXTREME FEAR",   note: "Maximum pessimism — often marks cycle lows for patient buyers." };

  // Stance
  const stance =
    fgValue >= 55 && change7d > 0 && change30d > 0 ? "BULLISH" :
    fgValue <= 40 && change7d < 0 && change30d < 0 ? "BEARISH" : "NEUTRAL";

  // Key levels
  const support1     = Math.round(low24h  * 0.99 / 100)  * 100;
  const support2     = Math.round(price   * 0.95 / 500)   * 500;
  const resist1      = Math.round(high24h * 1.01 / 100)   * 100;
  const resist2      = Math.round(price   * 1.05 / 500)   * 500;
  const invalidation = Math.round(price   * 0.92 / 500)   * 500;

  // ATH note
  const athPct = Math.abs(athChangePct);
  const athNote =
    athPct < 5  ? `only ${athPct.toFixed(1)}% below ATH ($${fmt(ath)}) — price discovery territory` :
    athPct < 15 ? `${athPct.toFixed(1)}% below ATH ($${fmt(ath)}) — upper range of historical cycle` :
                  `${athPct.toFixed(1)}% below ATH ($${fmt(ath)}) — mid-cycle range`;

  // Narratives
  const shortTerm =
    direction === "UP"   ? `Positive momentum; buyers in control above $${fmt(support1)}` :
    direction === "DOWN" ? `Selling pressure active; watch $${fmt(support1)} as near-term floor` :
                           `Coiling between $${fmt(support1)} and $${fmt(resist1)} — breakout imminent`;

  const mediumTerm =
    direction === "UP"   ? `Bullish structure intact if price holds above $${fmt(support2)}` :
    direction === "DOWN" ? `Recovery needs reclaim of $${fmt(resist1)} to shift bias` :
                           `Trend continuation depends on which level breaks first`;

  // Scenarios
  const bull =
    stance === "BULLISH" ? `Hold above $${fmt(resist1)} → continuation toward $${fmt(resist2)}+` :
    stance === "BEARISH" ? `Reclaim of $${fmt(resist1)} and hold → relief rally to $${fmt(resist2)}` :
                           `Break above $${fmt(resist1)} with volume → push toward $${fmt(resist2)}`;

  const bear =
    stance === "BULLISH" ? `Rejection + close below $${fmt(support1)} → retest of $${fmt(support2)}` :
    stance === "BEARISH" ? `Continued selling below $${fmt(support1)} → test of $${fmt(support2)}` :
                           `Break below $${fmt(support1)} → accelerated move to $${fmt(support2)}`;

  const base =
    stance === "BULLISH" ? `Consolidation near $${fmt(price)}, then upside continuation (higher probability)` :
    stance === "BEARISH" ? `Further downside toward $${fmt(support2)} before stabilisation` :
                           `Range-bound between $${fmt(support1)}–$${fmt(resist1)} pending catalyst`;

  // Confidence
  const signals = [
    Math.abs(change24h) > 2,
    Math.abs(change7d)  > 5,
    fgValue < 25 || fgValue > 75,
    volRatio > 5 || volRatio < 2,
  ].filter(Boolean).length;

  const confidence =
    signals >= 3 ? "HIGH" :
    signals === 2 ? "MEDIUM-HIGH" :
    signals === 1 ? "MEDIUM" : "LOW";

  // News drivers
  const drivers = [];
  if (Math.abs(change24h) > 3) {
    const move = change24h > 0 ? "rallied" : "sold off";
    drivers.push(`<strong>Strong 24h move:</strong> BTC ${move} ${Math.abs(change24h).toFixed(1)}% — significant one-day volatility.`);
  }
  if (athPct < 10) drivers.push(`<strong>Near all-time high:</strong> Price is ${athPct.toFixed(1)}% below ATH ($${fmt(ath)}) — resistance and profit-taking risk elevated.`);
  if (fgValue <= 25) drivers.push(`<strong>Extreme Fear (${fgValue}):</strong> Historically these levels coincide with capitulation bottoms — potential contrarian buy zone.`);
  else if (fgValue >= 75) drivers.push(`<strong>Extreme Greed (${fgValue}):</strong> Crowd is very optimistic — corrections often follow these readings.`);
  if (change30d > 20)  drivers.push(`<strong>Strong monthly run:</strong> BTC is up ${change30d.toFixed(1)}% over 30 days — momentum strong but extended.`);
  else if (change30d < -15) drivers.push(`<strong>Monthly drawdown:</strong> BTC is down ${Math.abs(change30d).toFixed(1)}% over 30 days — accumulation zone for long-term holders.`);
  if (volRatio > 6) drivers.push(`<strong>Elevated volume:</strong> 24h volume is ${volRatio.toFixed(1)}% of market cap — unusual activity, potential breakout or breakdown.`);
  drivers.push(`<strong>ATH context:</strong> Current price is ${athNote}.`);

  return {
    direction, volume, volRatio, stance,
    sentiment, shortTerm, mediumTerm,
    bull, bear, base,
    confidence, signals,
    support1, support2, resist1, resist2, invalidation,
    drivers: drivers.slice(0, 5),
  };
}

// ── 3. Build HTML ─────────────────────────────────────────────────────────────

function buildHtml(d, a) {
  const sign = n => n >= 0 ? "+" : "";
  const fgArrow = d.fgValue > d.fgPrev ? "▲" : d.fgValue < d.fgPrev ? "▼" : "—";

  return `<h2>Bitcount (BTC) Daily Market Brief – ${TODAY}</h2>

<h3>Summary</h3>
<p>
  Bitcoin is trading at <strong>$${fmt(d.price)}</strong>
  (${sign(d.change24h)}${d.change24h.toFixed(2)}% in 24h,
  ${sign(d.change7d)}${d.change7d.toFixed(1)}% over 7 days).
  Trend is <strong>${a.direction}</strong> with <strong>${a.volume}</strong> volume
  and a <strong>${a.stance}</strong> market bias.
  Fear &amp; Greed: <strong>${d.fgValue} (${d.fgLabel})</strong> ${fgArrow} from ${d.fgPrev} yesterday.
</p>

<h3>News Drivers</h3>
<ul>
  ${a.drivers.map(item => `<li>${item}</li>`).join("\n  ")}
</ul>

<h3>Trend Analysis</h3>
<ul>
  <li><strong>Direction:</strong> ${a.direction}</li>
  <li><strong>Volume:</strong> ${a.volume} (${a.volRatio.toFixed(1)}% volume-to-market-cap)</li>
  <li><strong>Short-term (1–3d):</strong> ${a.shortTerm}</li>
  <li><strong>Medium-term (1–2w):</strong> ${a.mediumTerm}</li>
  <li><strong>24h range:</strong> $${fmt(d.low24h)} – $${fmt(d.high24h)}</li>
  <li><strong>30d change:</strong> ${sign(d.change30d)}${d.change30d.toFixed(1)}%</li>
</ul>

<h3>Sentiment</h3>
<ul>
  <li><strong>Overall:</strong> ${a.stance}</li>
  <li><strong>Fear &amp; Greed:</strong> ${d.fgValue} (${d.fgLabel}) ${fgArrow} vs ${d.fgPrev} yesterday</li>
  <li><strong>Context:</strong> ${a.sentiment.note}</li>
</ul>

<h3>Next Move Scenarios</h3>
<ul>
  <li><strong>Bull case:</strong> ${a.bull}</li>
  <li><strong>Bear case:</strong> ${a.bear}</li>
  <li><strong>Base case:</strong> ${a.base}</li>
</ul>

<h3>Key Levels</h3>
<ul>
  <li><strong>Support:</strong> $${fmt(a.support1)} / $${fmt(a.support2)}</li>
  <li><strong>Resistance:</strong> $${fmt(a.resist1)} / $${fmt(a.resist2)}</li>
  <li><strong>Invalidation:</strong> $${fmt(a.invalidation)}</li>
</ul>

<h3>Confidence</h3>
<p><strong>${a.confidence}</strong> — ${a.signals}/4 confirming signals (24h move, 7d trend, sentiment extreme, volume).</p>

<hr>
<p><em>Generated by bitcount-market-scout · ${TODAY} 07:00 ET</em></p>`;
}

// ── 4. Send email ─────────────────────────────────────────────────────────────

async function sendEmail(html) {
  const transporter = nodemailer.createTransport({
    service: "gmail",
    auth: {
      user: process.env.GMAIL_USER,
      pass: process.env.GMAIL_APP_PASSWORD,
    },
  });

  await transporter.sendMail({
    from: process.env.GMAIL_USER,
    to: RECIPIENT,
    subject: `Bitcount daily market brief – ${TODAY}`,
    text: html.replace(/<[^>]+>/g, "").replace(/\n{3,}/g, "\n\n").trim(),
    html,
  });

  console.log(`Sent: Bitcount daily market brief – ${TODAY}`);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(n) {
  return n.toLocaleString("en-US");
}

// ── Main ──────────────────────────────────────────────────────────────────────

const data = await fetchMarketData();
console.log(`BTC: $${fmt(data.price)}  |  24h: ${data.change24h >= 0 ? "+" : ""}${data.change24h.toFixed(2)}%  |  F&G: ${data.fgValue} (${data.fgLabel})`);

const analysis = analyse(data);
const html = buildHtml(data, analysis);
await sendEmail(html);
