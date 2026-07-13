#!/usr/bin/env bash
# Live integration tests against the Binance USDⓈ-M demo (fake money).
#
# WHY LOCAL: GitHub-hosted CI runners are geo-blocked by Binance (HTTP 451), so
# these must run from an allowed IP. Schedule this script on a machine in an
# allowed region.
#
#   cron (daily 09:00):
#     0 9 * * * cd /ABS/PATH/opentrading && ./scripts/run_demo_integration.sh >> /tmp/opentrading-demo-it.log 2>&1
#
#   macOS launchd: wrap this in a LaunchAgent plist with StartCalendarInterval.
#
# Requires: docker running, and BINANCE_DEMO_API_KEY/SECRET in .env (the api
# service loads .env). Exits non-zero if any test fails.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose run --rm --no-deps \
  -e RUN_DEMO_INTEGRATION=1 \
  api sh -c "pip install -q -r requirements/dev.txt && python -m pytest services/tests/tests_demo_integration.py -v"
