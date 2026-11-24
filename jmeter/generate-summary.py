#!/usr/bin/env python3
"""
Generate a comprehensive Performance & Bottleneck Summary Report from JMeter results.
Supports reading from dashboard/statistics.json or directly from results.jtl.
Outputs formatted Markdown report to <results_dir>/summary.md and prints a clean summary table to stdout.
"""

import sys
import os
import json
import csv
from datetime import datetime

def format_ms(val):
    if val is None or val == "":
        return "N/A"
    try:
        return f"{float(val):,.1f} ms"
    except (ValueError, TypeError):
        return str(val)

def format_num(val):
    if val is None:
        return "0"
    try:
        return f"{int(val):,}"
    except (ValueError, TypeError):
        return str(val)

def format_rate(val):
    if val is None:
        return "0.0/s"
    try:
        return f"{float(val):,.2f}/s"
    except (ValueError, TypeError):
        return str(val)

def parse_from_statistics_json(stat_file):
    with open(stat_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def parse_from_jtl(jtl_file):
    samples = {}
    total_start = None
    total_end = None

    with open(jtl_file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get('label') or 'Unknown'
            try:
                elapsed = float(row.get('elapsed', 0))
                success = row.get('success', 'true').strip().lower() == 'true'
                ts = float(row.get('timeStamp', 0))
            except (ValueError, TypeError):
                continue

            if total_start is None or ts < total_start:
                total_start = ts
            end_ts = ts + elapsed
            if total_end is None or end_ts > total_end:
                total_end = end_ts

            for key in (label, 'Total'):
                if key not in samples:
                    samples[key] = {
                        'latencies': [],
                        'errors': 0,
                        'total': 0
                    }
                samples[key]['latencies'].append(elapsed)
                samples[key]['total'] += 1
                if not success:
                    samples[key]['errors'] += 1

    duration_sec = max(1.0, (total_end - total_start) / 1000.0) if (total_start and total_end) else 1.0

    stats = {}
    for key, item in samples.items():
        lats = sorted(item['latencies'])
        count = len(lats)
        errors = item['errors']
        err_pct = (errors / count * 100.0) if count > 0 else 0.0

        def pct(p):
            if not lats:
                return 0.0
            k = (len(lats) - 1) * (p / 100.0)
            f = int(k)
            c = min(f + 1, len(lats) - 1)
            return lats[f] + (k - f) * (lats[c] - lats[f])

        stats[key] = {
            'transaction': key,
            'sampleCount': count,
            'errorCount': errors,
            'errorPct': err_pct,
            'meanResTime': sum(lats) / count if count else 0.0,
            'medianResTime': pct(50),
            'pct1ResTime': pct(90),
            'pct2ResTime': pct(95),
            'pct3ResTime': pct(99),
            'minResTime': lats[0] if lats else 0.0,
            'maxResTime': lats[-1] if lats else 0.0,
            'throughput': count / duration_sec
        }
    return stats

def analyze_bottlenecks(stats):
    findings = []
    total = stats.get('Total', {})
    err_pct = total.get('errorPct', 0.0)
    avg_resp = total.get('meanResTime', 0.0)
    p95_resp = total.get('pct2ResTime', 0.0)
    throughput = total.get('throughput', 0.0)

    # 1. Error rate analysis
    if err_pct == 0.0:
        findings.append("✅ **Zero Errors:** 100% of purchase transactions succeeded without HTTP or business logic failures.")
    elif err_pct < 1.0:
        findings.append(f"⚠️ **Low Error Rate ({err_pct:.2f}%):** A small fraction of requests failed. Review `jmeter.log` to check if errors were connection timeouts or gateway rejections.")
    else:
        findings.append(f"❌ **High Error Rate ({err_pct:.2f}%):** Significant failures detected. The gateway or backend connection pool likely saturated under this load.")

    # 2. Latency analysis
    if p95_resp < 500:
        findings.append(f"✅ **Fast Response Time (P95: {p95_resp:,.1f}ms):** Latency remained comfortably under 500ms, indicating healthy processing headroom.")
    elif p95_resp < 2000:
        findings.append(f"⚠️ **Moderate Latency (P95: {p95_resp:,.1f}ms):** Response times increased up to 2 seconds under peak concurrency. Server queueing began at higher loads.")
    else:
        findings.append(f"❌ **Severe Latency Degredation (P95: {p95_resp:,.1f}ms):** High queueing delays (> 2s) observed. The target server's 2 CPU cores were likely at 100% saturation.")

    # 3. Endpoint breakdown (Validate vs Execute)
    val_stat = None
    exec_stat = None
    for k, v in stats.items():
        k_lower = k.lower()
        if 'validate' in k_lower and val_stat is None:
            val_stat = v
        elif 'execute' in k_lower and exec_stat is None:
            exec_stat = v

    if val_stat and exec_stat:
        v_avg = val_stat.get('meanResTime', 0.0)
        e_avg = exec_stat.get('meanResTime', 0.0)
        if e_avg > 0 and v_avg > 0:
            ratio = e_avg / v_avg
            if ratio > 2.0:
                findings.append(f"🔍 **Primary Endpoint Bottleneck:** `purchase execute` ({e_avg:,.1f}ms avg) is **{ratio:.1f}x slower** than `purchase validate` ({v_avg:,.1f}ms avg). Stock allocation / DB transaction locking in the execute phase is the primary performance limiter.")
            elif ratio < 0.5:
                findings.append(f"🔍 **Primary Endpoint Bottleneck:** `purchase validate` ({v_avg:,.1f}ms avg) took longer than execute ({e_avg:,.1f}ms avg). External catalog/reseller validation queries may need indexing or caching.")
            else:
                findings.append(f"ℹ️ **Balanced Endpoints:** Validate ({v_avg:,.1f}ms) and Execute ({e_avg:,.1f}ms) have comparable latencies.")

    # 4. Capacity assessment for 2-Core / 4GB RAM
    findings.append(f"📊 **Throughput Observed:** Sustained **{throughput:,.2f} TPS** (Transactions/sec). For a 2-Core VM, if throughput flatlined while latency increased, this marks the operational saturation ceiling.")

    return findings

def generate_report(results_dir):
    stats_json = os.path.join(results_dir, 'dashboard', 'statistics.json')
    jtl_file = os.path.join(results_dir, 'results.jtl')

    if os.path.isfile(stats_json):
        stats = parse_from_statistics_json(stats_json)
        source = "dashboard/statistics.json"
    elif os.path.isfile(jtl_file):
        stats = parse_from_jtl(jtl_file)
        source = "results.jtl (raw)"
    else:
        print(f"Error: Neither {stats_json} nor {jtl_file} found in {results_dir}", file=sys.stderr)
        return False

    total = stats.get('Total', {})
    findings = analyze_bottlenecks(stats)
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build Markdown Content
    md = []
    md.append(f"# Load Test Performance & Bottleneck Summary")
    md.append(f"")
    md.append(f"- **Generated:** {ts_now}")
    md.append(f"- **Results Directory:** `{os.path.abspath(results_dir)}`")
    md.append(f"- **Metrics Source:** `{source}`")
    md.append(f"")
    md.append(f"## Key Executive Metrics")
    md.append(f"")
    md.append(f"| Metric | Result |")
    md.append(f"| :--- | :--- |")
    md.append(f"| **Total Purchase Requests** | **{format_num(total.get('sampleCount', 0))}** |")
    md.append(f"| **Success Rate** | **{100.0 - float(total.get('errorPct', 0.0)):.2f}%** |")
    md.append(f"| **Error Rate** | **{float(total.get('errorPct', 0.0)):.2f}%** ({format_num(total.get('errorCount', 0))} errors) |")
    md.append(f"| **Throughput (TPS)** | **{format_rate(total.get('throughput', 0.0))}** |")
    md.append(f"| **Average Response Time** | **{format_ms(total.get('meanResTime', 0.0))}** |")
    md.append(f"| **Median (P50) Latency** | **{format_ms(total.get('medianResTime', 0.0))}** |")
    md.append(f"| **90th Percentile (P90)** | **{format_ms(total.get('pct1ResTime', 0.0))}** |")
    md.append(f"| **95th Percentile (P95)** | **{format_ms(total.get('pct2ResTime', 0.0))}** |")
    md.append(f"| **99th Percentile (P99)** | **{format_ms(total.get('pct3ResTime', 0.0))}** |")
    md.append(f"| **Min / Max Latency** | {format_ms(total.get('minResTime', 0.0))} / {format_ms(total.get('maxResTime', 0.0))} |")
    md.append(f"")
    md.append(f"## Bottleneck & Capacity Analysis")
    md.append(f"")
    for f in findings:
        md.append(f"- {f}")
    md.append(f"")
    md.append(f"## Transaction & Endpoint Breakdown")
    md.append(f"")
    md.append(f"| Transaction / Sampler | Samples | Error % | Avg Latency | P50 (Med) | P90 | P95 | P99 | Throughput |")
    md.append(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    # Order keys: Total first, then others
    keys = sorted(stats.keys(), key=lambda x: (0 if x == 'Total' else 1, x))
    for k in keys:
        s = stats[k]
        md.append(f"| `{k}` | {format_num(s.get('sampleCount', 0))} | {float(s.get('errorPct', 0.0)):.2f}% | {format_ms(s.get('meanResTime', 0.0))} | {format_ms(s.get('medianResTime', 0.0))} | {format_ms(s.get('pct1ResTime', 0.0))} | {format_ms(s.get('pct2ResTime', 0.0))} | {format_ms(s.get('pct3ResTime', 0.0))} | {format_rate(s.get('throughput', 0.0))} |")

    md.append(f"")
    md.append(f"> [!TIP]")
    md.append(f"> For detailed visual charts (Active Threads over Time, Response Times vs Threads, Latency Percentiles), open `dashboard/index.html`.")

    summary_file = os.path.join(results_dir, "summary.md")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # Console Output (Pretty ASCII)
    print("\n" + "=" * 80)
    print("                    LOAD TEST PERFORMANCE SUMMARY REPORT")
    print("=" * 80)
    print(f" Results Folder: {os.path.abspath(results_dir)}")
    print(f" Total Samples:  {format_num(total.get('sampleCount', 0))} requests")
    print(f" Error Rate:     {float(total.get('errorPct', 0.0)):.2f}% ({format_num(total.get('errorCount', 0))} errors)")
    print(f" Throughput:     {format_rate(total.get('throughput', 0.0))}")
    print(f" Latency (Avg):  {format_ms(total.get('meanResTime', 0.0))}")
    print(f" Latency (P90):  {format_ms(total.get('pct1ResTime', 0.0))}")
    print(f" Latency (P95):  {format_ms(total.get('pct2ResTime', 0.0))}")
    print(f" Latency (P99):  {format_ms(total.get('pct3ResTime', 0.0))}")
    print("-" * 80)
    print(f" {'Transaction':<32} {'Count':<8} {'Err%':<8} {'Avg (ms)':<11} {'P95 (ms)':<11} {'TPS':<8}")
    print("-" * 80)
    for k in keys:
        s = stats[k]
        display_name = k if len(k) <= 30 else (k[:27] + "...")
        print(f" {display_name:<32} {format_num(s.get('sampleCount', 0)):<8} {float(s.get('errorPct', 0.0)):<8.1f} {float(s.get('meanResTime', 0.0)):<11.1f} {float(s.get('pct2ResTime', 0.0)):<11.1f} {float(s.get('throughput', 0.0)):<8.2f}")
    print("=" * 80)
    print(" Bottleneck Analysis:")
    for f in findings:
        clean_f = f.replace("**", "").replace("`", "")
        print(f"  • {clean_f}")
    print("=" * 80)
    print(f" Full Summary Report Saved: {summary_file}")
    print(f" Interactive HTML Dashboard: {os.path.join(results_dir, 'dashboard', 'index.html')}")
    print("=" * 80 + "\n")
    return True

if __name__ == '__main__':
    target_dir = sys.argv[1] if len(sys.argv) > 1 else None
    if not target_dir:
        # Default to latest results folder if not provided
        results_root = os.path.join(os.path.dirname(__file__), "results")
        if os.path.isdir(results_root):
            subdirs = [os.path.join(results_root, d) for d in os.listdir(results_root) if os.path.isdir(os.path.join(results_root, d))]
            if subdirs:
                target_dir = max(subdirs, key=os.path.getmtime)
    if not target_dir or not os.path.isdir(target_dir):
        print("Usage: python3 generate-summary.py <path_to_results_folder>", file=sys.stderr)
        sys.exit(1)

    generate_report(target_dir)
