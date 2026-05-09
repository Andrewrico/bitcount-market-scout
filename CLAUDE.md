# bitcount-report

Daily BTC market report mailer. Fetches live data, generates a structured analysis report, and emails it automatically every morning.

## What it does
- Pulls live BTC price, 24h/7d/30d change, volume, high/low, ATH from CoinGecko (no API key needed)
- Pulls Fear & Greed Index from alternative.me (no API key needed)
- Runs rule-based analysis to determine trend direction, sentiment, key levels, scenarios, and confidence
- Builds an HTML email report and sends it via Gmail SMTP

## Files
- `send_report.py` — main script: fetches data, analyses, builds HTML, sends email
- `run.sh` — cron wrapper that loads `.env` and runs the script
- `.env` — credentials (gitignored, never commit this)

## Credentials (in .env)
```
GMAIL_USER=andrewric86@gmail.com
GMAIL_APP_PASSWORD=<16-char Gmail App Password>
```
Generate app password at: myaccount.google.com/security → App passwords

## Schedule
Runs daily at 7:00 AM America/New_York via server cron:
```
0 7 * * * TZ=America/New_York /root/bitcount-report/run.sh >> /var/log/bitcount-report.log 2>&1
```
Check logs: `cat /var/log/bitcount-report.log`

## Run manually
```bash
source .env && export GMAIL_USER GMAIL_APP_PASSWORD && python3 send_report.py
```

## Dependencies
- `requests` (system package, pre-installed)
- No LLM API required — fully rule-based analysis

## Report email
- To: andrewric86@gmail.com
- Subject: `Bitcount daily market brief – YYYY-MM-DD`
- Format: HTML with headings and bullets, mobile-friendly

## GitHub
https://github.com/Andrewrico/bitcount-market-scout
