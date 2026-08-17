#!/usr/bin/env bash
# Ten Themes — full weekly pipeline.
#
# Runs every deterministic stage in order. The three research passes
# (analyst coverage, EDGAR filings, events/IPOs) are NOT automated here —
# see docs/AGENT.md. This script assumes those JSON files already exist
# in data/ and copies them into the working directory.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${ROOT}/pipeline"

echo "==> staging research inputs from data/"
cp "${ROOT}"/data/*.json "${WORK}/" 2>/dev/null || true

cd "${WORK}"

echo "==> [1/8] prices.py"       && python3 prices.py
echo "==> [2/8] enrich.py"       && python3 enrich.py
echo "==> [3/8] tech.py"         && python3 tech.py
echo "==> [4/8] score.py"        && python3 score.py
echo "==> [5/8] options.py"      && python3 options.py
echo "==> [6/8] score2.py"       && python3 score2.py
echo "==> [7/12] build_site2.py"  && python3 build_site2.py
echo "==> [8/12] macro.py"        && python3 macro.py
echo "==> [9/12] sectors.py"      && python3 sectors.py
echo "==> [10/12] factors.py"     && python3 factors.py
echo "==> [11/12] build_map.py"   && python3 build_map.py

if [[ -f link.txt ]]; then
  echo "==> [12/12] build_email2.py" && python3 build_email2.py
else
  echo "==> [12/12] SKIPPED build_email2.py — write the published dashboard URL to pipeline/link.txt first"
fi

mkdir -p "${ROOT}/output" "${ROOT}/public"
[[ -f site2.html  ]] && cp site2.html  "${ROOT}/output/dashboard.html" && cp site2.html "${ROOT}/public/index.html"
[[ -f map.html    ]] && cp map.html    "${ROOT}/output/map_room.html" && cp map.html "${ROOT}/public/map.html"
[[ -f email2.html ]] && cp email2.html "${ROOT}/output/email.html" && cp email2.html "${ROOT}/public/email.html"

echo
echo "Done. Refreshed JSON is in pipeline/; rendered output in output/ and public/ (Vercel)."
echo "Remember to rewrite STRATEGY (build_site2.py) and INTRO (build_email2.py) before publishing."
echo "Redeploy the desk with: npx vercel --prod"
echo "Or run the cloud job: DATABASE_URL=... python3 job.py"
