#!/bin/bash
set -e
cd /root/bitcount-report
source .env
export GMAIL_USER GMAIL_APP_PASSWORD
python3 send_report.py
