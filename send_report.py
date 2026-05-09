#!/usr/bin/env python3
"""
Bitcount (BTC) daily market report mailer.
Fetches live data from CoinGecko + Fear & Greed API,
generates a structured report with rule-based analysis,
then emails it to the recipient.
No LLM API required.
"""

import smtplib
import os
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
TODAY = datetime.now(ET).strftime("%Y-%m-%d")

RECIPIENT    = "andrewric86@gmail.com"
GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_APP_PW = os.environ["GMAIL_APP_PASSWORD"]

SUBJECT = f"Bitcount daily market brief – {TODAY}"


# ── 1. Fetch live market data ─────────────────────────────────────────────────

def fetch_market_data() -> dict:
    cg = requests.get(
        "https://api.coingecko.com/api/v3/coins/bitcoin",
        params={"localization": "false", "tickers": "false",
                "community_data": "false", "developer_data": "false"},
        timeout=15,
    ).json()

    md = cg["market_data"]
    data = {
        "price":          md["current_price"]["usd"],
        "change_24h":     md["price_change_percentage_24h"],
        "change_7d":      md["price_change_percentage_7d"],
        "change_30d":     md["price_change_percentage_30d"],
        "volume_24h":     md["total_volume"]["usd"],
        "market_cap":     md["market_cap"]["usd"],
        "ath":            md["ath"]["usd"],
        "ath_change_pct": md["ath_change_percentage"]["usd"],
        "high_24h":       md["high_24h"]["usd"],
        "low_24h":        md["low_24h"]["usd"],
        "circulating":    md["circulating_supply"],
    }

    fg = requests.get(
        "https://api.alternative.me/fng/?limit=2", timeout=10
    ).json()["data"]
    data["fg_value"] = int(fg[0]["value"])
    data["fg_label"] = fg[0]["value_classification"]
    data["fg_prev"]  = int(fg[1]["value"])

    return data


# ── 2. Rule-based analysis ────────────────────────────────────────────────────

def analyse(d: dict) -> dict:
    p    = d["price"]
    c24  = d["change_24h"]
    c7   = d["change_7d"]
    c30  = d["change_30d"]
    fg   = d["fg_value"]
    ath  = d["ath"]
    vol  = d["volume_24h"]
    mc   = d["market_cap"]

    # Direction
    if c24 > 2 and c7 > 3:
        direction = "UP"
    elif c24 < -2 and c7 < -3:
        direction = "DOWN"
    else:
        direction = "SIDEWAYS"

    # Volume (volume-to-market-cap ratio typical range ~2-6%)
    vol_ratio = (vol / mc) * 100
    if vol_ratio > 6:
        volume = "HIGH"
    elif vol_ratio < 2.5:
        volume = "LOW"
    else:
        volume = "NORMAL"

    # Sentiment label
    if fg >= 75:
        sentiment = "EXTREME GREED"
        sentiment_note = "Market is overheated — risk of sharp pullback is elevated."
    elif fg >= 55:
        sentiment = "GREED"
        sentiment_note = "Bullish momentum present but watch for complacency."
    elif fg >= 45:
        sentiment = "NEUTRAL"
        sentiment_note = "No strong directional bias; wait for a clearer signal."
    elif fg >= 25:
        sentiment = "FEAR"
        sentiment_note = "Bearish sentiment dominates — historically a buying opportunity area."
    else:
        sentiment = "EXTREME FEAR"
        sentiment_note = "Maximum pessimism — often marks cycle lows for patient buyers."

    # Overall stance
    if fg >= 55 and c7 > 0 and c30 > 0:
        stance = "BULLISH"
    elif fg <= 40 and c7 < 0 and c30 < 0:
        stance = "BEARISH"
    else:
        stance = "NEUTRAL"

    # Key levels (derived from current price and 24h range)
    support1  = round(d["low_24h"] * 0.99 / 100) * 100
    support2  = round(p * 0.95 / 500) * 500
    resist1   = round(d["high_24h"] * 1.01 / 100) * 100
    resist2   = round(p * 1.05 / 500) * 500
    invalidation = round(p * 0.92 / 500) * 500

    # ATH proximity
    ath_pct = abs(d["ath_change_pct"])
    if ath_pct < 5:
        ath_note = f"only {ath_pct:.1f}% below ATH (${ath:,.0f}) — price discovery territory"
    elif ath_pct < 15:
        ath_note = f"{ath_pct:.1f}% below ATH (${ath:,.0f}) — upper range of historical cycle"
    else:
        ath_note = f"{ath_pct:.1f}% below ATH (${ath:,.0f}) — mid-cycle range"

    # Short / medium-term narrative
    if direction == "UP":
        short_term  = f"Positive momentum; buyers in control above ${support1:,.0f}"
        medium_term = f"Bullish structure intact if price holds above ${support2:,.0f}"
    elif direction == "DOWN":
        short_term  = f"Selling pressure active; watch ${support1:,.0f} as near-term floor"
        medium_term = f"Recovery needs reclaim of ${resist1:,.0f} to shift bias"
    else:
        short_term  = f"Coiling between ${support1:,.0f} and ${resist1:,.0f} — breakout imminent"
        medium_term = f"Trend continuation depends on which level breaks first"

    # Bull / bear / base scenarios
    if stance == "BULLISH":
        bull = f"Hold above ${resist1:,.0f} → continuation toward ${resist2:,.0f}+"
        bear = f"Rejection + close below ${support1:,.0f} → retest of ${support2:,.0f}"
        base = f"Consolidation near ${p:,.0f}, then upside continuation (higher probability)"
    elif stance == "BEARISH":
        bull = f"Reclaim of ${resist1:,.0f} and hold → relief rally to ${resist2:,.0f}"
        bear = f"Continued selling below ${support1:,.0f} → test of ${support2:,.0f}"
        base = f"Further downside pressure toward ${support2:,.0f} before stabilisation"
    else:
        bull = f"Break above ${resist1:,.0f} with volume → push toward ${resist2:,.0f}"
        bear = f"Break below ${support1:,.0f} → accelerated move to ${support2:,.0f}"
        base = f"Range-bound between ${support1:,.0f}–${resist1:,.0f} pending catalyst"

    # Confidence
    signals = sum([
        abs(c24) > 2,
        abs(c7) > 5,
        fg < 25 or fg > 75,
        vol_ratio > 5 or vol_ratio < 2,
    ])
    if signals >= 3:
        confidence = "HIGH"
    elif signals == 2:
        confidence = "MEDIUM-HIGH"
    elif signals == 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    conf_note = f"{signals}/4 confirming signals (24h move, 7d trend, sentiment extreme, volume)"

    # News drivers (derived from data)
    drivers = []
    if abs(c24) > 3:
        move = "rallied" if c24 > 0 else "sold off"
        drivers.append(f"<strong>Strong 24h move:</strong> BTC {move} {abs(c24):.1f}% in the last 24 hours — significant one-day volatility.")
    if ath_pct < 10:
        drivers.append(f"<strong>Near all-time high:</strong> Price is {ath_pct:.1f}% below ATH (${ath:,.0f}) — resistance and profit-taking risk elevated.")
    if fg <= 25:
        drivers.append(f"<strong>Extreme Fear ({fg}):</strong> Historically these levels coincide with capitulation bottoms — potential contrarian buy zone.")
    elif fg >= 75:
        drivers.append(f"<strong>Extreme Greed ({fg}):</strong> Crowd is very optimistic — corrections often follow these readings.")
    if c30 > 20:
        drivers.append(f"<strong>Strong monthly run:</strong> BTC is up {c30:.1f}% over 30 days — momentum strong but extended.")
    elif c30 < -15:
        drivers.append(f"<strong>Monthly drawdown:</strong> BTC is down {abs(c30):.1f}% over 30 days — accumulation zone for long-term holders.")
    if vol_ratio > 6:
        drivers.append(f"<strong>Elevated volume:</strong> 24h volume is {vol_ratio:.1f}% of market cap — unusual activity, potential breakout or breakdown.")
    # Always include ATH context
    drivers.append(f"<strong>ATH context:</strong> Current price is {ath_note}.")
    drivers = drivers[:5]  # cap at 5

    return {
        "direction": direction,
        "volume": volume,
        "vol_ratio": vol_ratio,
        "sentiment": sentiment,
        "sentiment_note": sentiment_note,
        "stance": stance,
        "support1": support1,
        "support2": support2,
        "resist1": resist1,
        "resist2": resist2,
        "invalidation": invalidation,
        "short_term": short_term,
        "medium_term": medium_term,
        "bull": bull,
        "bear": bear,
        "base": base,
        "confidence": confidence,
        "conf_note": conf_note,
        "drivers": drivers,
        "ath_note": ath_note,
    }


# ── 3. Build HTML report ──────────────────────────────────────────────────────

def build_html(d: dict, a: dict) -> str:
    drivers_html = "\n".join(f"  <li>{item}</li>" for item in a["drivers"])

    fg_arrow = "▲" if d["fg_value"] > d["fg_prev"] else ("▼" if d["fg_value"] < d["fg_prev"] else "—")

    return f"""<h2>Bitcount (BTC) Daily Market Brief – {TODAY}</h2>

<h3>Summary</h3>
<p>
  Bitcoin is trading at <strong>${d['price']:,.0f}</strong>
  ({'+' if d['change_24h'] >= 0 else ''}{d['change_24h']:.2f}% in 24h,
  {'+' if d['change_7d'] >= 0 else ''}{d['change_7d']:.1f}% over 7 days).
  The overall trend is <strong>{a['direction']}</strong> with <strong>{a['volume']}</strong> volume
  and a <strong>{a['stance']}</strong> market bias.
  The Fear &amp; Greed Index sits at <strong>{d['fg_value']} ({d['fg_label']})</strong> {fg_arrow} from {d['fg_prev']} yesterday.
</p>

<h3>News Drivers</h3>
<ul>
{drivers_html}
</ul>

<h3>Trend Analysis</h3>
<ul>
  <li><strong>Direction:</strong> {a['direction']}</li>
  <li><strong>Volume:</strong> {a['volume']} ({a['vol_ratio']:.1f}% volume-to-market-cap ratio)</li>
  <li><strong>Short-term (1–3d):</strong> {a['short_term']}</li>
  <li><strong>Medium-term (1–2w):</strong> {a['medium_term']}</li>
  <li><strong>24h range:</strong> ${d['low_24h']:,.0f} – ${d['high_24h']:,.0f}</li>
  <li><strong>30d change:</strong> {'+' if d['change_30d'] >= 0 else ''}{d['change_30d']:.1f}%</li>
</ul>

<h3>Sentiment</h3>
<ul>
  <li><strong>Overall:</strong> {a['stance']}</li>
  <li><strong>Fear &amp; Greed Index:</strong> {d['fg_value']} ({d['fg_label']}) {fg_arrow} vs {d['fg_prev']} yesterday</li>
  <li><strong>Context:</strong> {a['sentiment_note']}</li>
</ul>

<h3>Next Move Scenarios</h3>
<ul>
  <li><strong>Bull case:</strong> {a['bull']}</li>
  <li><strong>Bear case:</strong> {a['bear']}</li>
  <li><strong>Base case:</strong> {a['base']}</li>
</ul>

<h3>Key Levels</h3>
<ul>
  <li><strong>Support:</strong> ${a['support1']:,.0f} / ${a['support2']:,.0f}</li>
  <li><strong>Resistance:</strong> ${a['resist1']:,.0f} / ${a['resist2']:,.0f}</li>
  <li><strong>Invalidation:</strong> ${a['invalidation']:,.0f}</li>
</ul>

<h3>Confidence</h3>
<p><strong>{a['confidence']}</strong> — {a['conf_note']}.</p>

<hr>
<p><em>Generated by bitcount-market-scout · {TODAY} 07:00 ET</em></p>"""


# ── 4. Send email ─────────────────────────────────────────────────────────────

def send(html_body: str):
    import re
    plain = re.sub(r"<[^>]+>", "", html_body).strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = SUBJECT
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PW)
        server.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())

    print(f"Sent: {SUBJECT}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching market data...")
    data = fetch_market_data()
    print(f"  BTC: ${data['price']:,.0f}  |  24h: {data['change_24h']:+.2f}%  |  F&G: {data['fg_value']} ({data['fg_label']})")

    print("Analysing...")
    analysis = analyse(data)

    print("Building report...")
    html = build_html(data, analysis)

    print("Sending email...")
    send(html)
