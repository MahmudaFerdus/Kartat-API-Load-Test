#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${JMETER_HOME:-}" && -x "${JMETER_HOME}/bin/jmeter" ]]; then
  JMETER="${JMETER_HOME}/bin/jmeter"
elif command -v jmeter >/dev/null 2>&1; then
  JMETER="$(command -v jmeter)"
elif [[ -x "${HOME}/apache-jmeter-5.6.3/bin/jmeter" ]]; then
  JMETER="${HOME}/apache-jmeter-5.6.3/bin/jmeter"
elif compgen -G "${HOME}/apache-jmeter*/bin/jmeter" >/dev/null 2>&1; then
  JMETER="$(ls -d ${HOME}/apache-jmeter*/bin/jmeter | head -n 1)"
elif [[ -x "/opt/homebrew/bin/jmeter" ]]; then
  JMETER="/opt/homebrew/bin/jmeter"
elif [[ -x "/usr/local/bin/jmeter" ]]; then
  JMETER="/usr/local/bin/jmeter"
else
  echo "Set JMETER_HOME to your Apache JMeter directory, or add jmeter to PATH." >&2
  echo "On macOS, you can install it via Homebrew: brew install jmeter" >&2
  exit 1
fi

if [[ ! -f secrets.properties ]]; then
  echo "secrets.properties is missing. Copy secrets.properties.example and set client_id, client_secret, and password." >&2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p results
n=0
while true; do
  if [[ "${n}" -eq 0 ]]; then
    out="results/${stamp}"
  else
    out="results/${stamp}-${n}"
  fi
  if mkdir "${out}" 2>/dev/null; then
    break
  fi
  n=$((n + 1))
  if [[ "${n}" -ge 100 ]]; then
    echo "Could not create a new results folder for ${stamp}." >&2
    exit 1
  fi
done

args=(
  -n
  -t kartat-gateway-purchase.jmx
  -q results-format.properties
  -q load-180-purchases-60-seconds.properties
)
if [[ -f .env ]]; then
  args+=(-q .env)
elif [[ -f ../.env ]]; then
  args+=(-q ../.env)
elif [[ -f secrets.properties ]]; then
  args+=(-q secrets.properties)
fi
args+=(
  -l "${out}/results.jtl"
  -j "${out}/jmeter.log"
  -e
  -o "${out}/dashboard"
)

echo "Results: ${out}"
set +e
"${JMETER}" "${args[@]}" "$@"
RC=$?
set -e

# Generate comprehensive summary report
if command -v python3 >/dev/null 2>&1; then
  python3 generate-summary.py "${out}" || true
elif command -v python >/dev/null 2>&1; then
  python generate-summary.py "${out}" || true
fi

exit "${RC}"
