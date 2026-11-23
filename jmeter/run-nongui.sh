#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${JMETER_HOME:-}" && -x "${JMETER_HOME}/bin/jmeter" ]]; then
  JMETER="${JMETER_HOME}/bin/jmeter"
elif command -v jmeter >/dev/null 2>&1; then
  JMETER="$(command -v jmeter)"
else
  echo "Set JMETER_HOME to your Apache JMeter directory, or add jmeter to PATH." >&2
  exit 1
fi

if [[ ! -f secrets.properties ]]; then
  echo "secrets.properties is missing. Copy secrets.properties.example and set client_id, client_secret, and password." >&2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
out="results/${stamp}"
mkdir -p "${out}"

args=(
  -n
  -t kartat-gateway-purchase.jmx
  -q results-format.properties
  -q load-180-purchases-60-seconds.properties
)
if [[ -f secrets.properties ]]; then
  args+=(-q secrets.properties)
fi
args+=(
  -l "${out}/results.jtl"
  -j "${out}/jmeter.log"
  -e
  -o "${out}/dashboard"
)

echo "Results: ${out}"
exec "${JMETER}" "${args[@]}" "$@"
