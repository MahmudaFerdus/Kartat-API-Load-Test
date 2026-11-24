#!/usr/bin/env bash
# ==============================================================================
# Bottleneck & Capacity Test Runner for 2-Core / 4GB RAM Target Server
# ==============================================================================
# This script executes an open-loop concurrency ramp test (default 1 -> 60 users
# over 5 minutes) to identify:
#   1. Maximum Throughput (TPS saturation point)
#   2. Latency Knee (where queueing begins and response time explodes)
#   3. Failure Threshold (HTTP 502/504 / timeouts under peak load)
# ==============================================================================
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# JVM tuning for the load generator
export JVM_ARGS="${JVM_ARGS:--Xms1g -Xmx2g -XX:+UseG1GC -XX:+ParallelRefProcEnabled}"

if [[ -z "${JAVA_HOME:-}" && -d "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home" ]]; then
  export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
fi

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
  echo "Error: JMeter is not installed or not in PATH." >&2
  echo "" >&2
  echo "To install JMeter on macOS using Homebrew, run:" >&2
  echo "  brew install jmeter" >&2
  echo "" >&2
  echo "If already installed manually, set JMETER_HOME:" >&2
  echo "  export JMETER_HOME=/path/to/apache-jmeter-5.x" >&2
  exit 1
fi

ENV_FILE=""
if [[ -f .env ]]; then
  ENV_FILE=".env"
elif [[ -f ../.env ]]; then
  ENV_FILE="../.env"
elif [[ -f secrets.properties ]]; then
  ENV_FILE="secrets.properties"
else
  echo "Warning: No .env or secrets.properties file found." >&2
  echo "Copy .env.example to .env and configure credentials before running:" >&2
  echo "  cp .env.example .env" >&2
fi

stamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p results
n=0
while true; do
  if [[ "${n}" -eq 0 ]]; then
    out="results/bottleneck-${stamp}"
  else
    out="results/bottleneck-${stamp}-${n}"
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
)

if [[ -n "${ENV_FILE}" ]]; then
  args+=(-q "${ENV_FILE}")
fi

args+=(
  -l "${out}/results.jtl"
  -j "${out}/jmeter.log"
  -e
  -o "${out}/dashboard"
)

echo "=============================================================================="
echo " Starting Bottleneck Stress Test"
echo " Target Configuration: 2-Core CPU / 4GB RAM Server"
echo " Results Directory:   ${out}"
echo " Config File:         ${ENV_FILE:-None (using plan defaults)}"
echo "=============================================================================="
echo "Tip: Run ./server-monitor.sh on the target server during this test to capture"
echo "real-time CPU, RAM, and load average correlation."
echo "=============================================================================="

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
