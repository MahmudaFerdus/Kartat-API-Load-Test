#!/usr/bin/env bash
# ==============================================================================
# Server Resource Monitor for Load Testing (Run this on the Target Server)
# ==============================================================================
# Logs timestamp, CPU (%usr, %sys, %iowait, %idle), Memory (Used, Free, Buff/Cache),
# Swap, 1-minute Load Average, and TCP Connections every 1 second.
#
# Usage:
#   chmod +x server-monitor.sh
#   ./server-monitor.sh                # prints to stdout
#   ./server-monitor.sh > metrics.log  # logs to file for post-test analysis
# ==============================================================================
set -euo pipefail

echo "Timestamp,CPU_User%,CPU_System%,CPU_IOWait%,CPU_Idle%,Mem_Used_MB,Mem_Free_MB,Mem_Avail_MB,Swap_Used_MB,Load_1m,TCP_Established,TCP_TimeWait"

while true; do
  TS="$(date +'%Y-%m-%dT%H:%M:%S')"

  # CPU usage from top / vmstat
  if command -v vmstat >/dev/null 2>&1; then
    CPU_DATA="$(vmstat 1 2 | tail -n 1)"
    CPU_US="$(echo "${CPU_DATA}" | awk '{print $13}')"
    CPU_SY="$(echo "${CPU_DATA}" | awk '{print $14}')"
    CPU_WA="$(echo "${CPU_DATA}" | awk '{print $16}')"
    CPU_ID="$(echo "${CPU_DATA}" | awk '{print $15}')"
  else
    CPU_US="N/A"; CPU_SY="N/A"; CPU_WA="N/A"; CPU_ID="N/A"
  fi

  # Memory usage from free -m
  if command -v free >/dev/null 2>&1; then
    MEM_LINE="$(free -m | awk '/^Mem:/{print $3","$4","$7}')"
    SWAP_USED="$(free -m | awk '/^Swap:/{print $3}')"
  else
    MEM_LINE="N/A,N/A,N/A"
    SWAP_USED="N/A"
  fi

  # 1-minute Load Average
  if [[ -f /proc/loadavg ]]; then
    LOAD_1M="$(awk '{print $1}' /proc/loadavg)"
  elif command -v uptime >/dev/null 2>&1; then
    LOAD_1M="$(uptime | sed 's/.*load average[s]*: //I' | awk '{print $1}' | tr -d ',')"
  else
    LOAD_1M="N/A"
  fi

  # TCP Connections
  if command -v ss >/dev/null 2>&1; then
    TCP_EST="$(ss -tan state established | wc -l | tr -d ' ')"
    TCP_TW="$(ss -tan state time-wait | wc -l | tr -d ' ')"
  elif command -v netstat >/dev/null 2>&1; then
    TCP_EST="$(netstat -ant | grep -c ESTABLISHED || true)"
    TCP_TW="$(netstat -ant | grep -c TIME_WAIT || true)"
  else
    TCP_EST="N/A"; TCP_TW="N/A"
  fi

  echo "${TS},${CPU_US},${CPU_SY},${CPU_WA},${CPU_ID},${MEM_LINE},${SWAP_USED},${LOAD_1M},${TCP_EST},${TCP_TW}"
  sleep 1
done
