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

def ensure_dashboard(results_dir, jtl_file, stats_json):
    if os.path.isfile(stats_json):
        return
    if not os.path.isfile(jtl_file) or os.path.getsize(jtl_file) == 0:
        return
    # Fix potential truncated last line from SIGINT / Ctrl+C
    try:
        with open(jtl_file, 'rb+') as f:
            lines = f.readlines()
            if lines and not lines[-1].endswith(b'\n'):
                f.seek(0)
                f.writelines(lines[:-1])
                f.truncate()
    except Exception:
        pass

    # Try generating dashboard using jmeter CLI if available
    dashboard_dir = os.path.join(results_dir, 'dashboard')
    import shutil, subprocess
    jmeter_bin = shutil.which('jmeter') or os.environ.get('JMETER')
    if not jmeter_bin:
        for candidate in [
            os.path.expanduser('~/apache-jmeter-5.6.3/bin/jmeter'),
            '/opt/homebrew/bin/jmeter',
            '/usr/local/bin/jmeter'
        ]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                jmeter_bin = candidate
                break
    if jmeter_bin:
        if os.path.isdir(dashboard_dir):
            shutil.rmtree(dashboard_dir, ignore_errors=True)
        try:
            subprocess.run([jmeter_bin, '-g', jtl_file, '-o', dashboard_dir],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

def generate_report(results_dir):
    stats_json = os.path.join(results_dir, 'dashboard', 'statistics.json')
    jtl_file = os.path.join(results_dir, 'results.jtl')

    ensure_dashboard(results_dir, jtl_file, stats_json)

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

    # Generate standalone styled HTML Report
    html_file = os.path.join(results_dir, "summary.html")
    err_pct_num = float(total.get('errorPct', 0.0))
    err_color = "var(--danger)" if err_pct_num > 5.0 else ("var(--warning)" if err_pct_num > 0 else "var(--success)")
    tps_val = float(total.get('throughput', 0.0))

    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html lang=\"en\">")
    html.append("<head>")
    html.append("  <meta charset=\"UTF-8\">")
    html.append("  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
    html.append("  <title>Load Test Summary Report</title>")
    html.append("  <style>")
    html.append("    :root {")
    html.append("      --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8;")
    html.append("      --border: #334155; --accent: #38bdf8; --success: #22c55e;")
    html.append("      --warning: #f59e0b; --danger: #ef4444;")
    html.append("    }")
    html.append("    * { box-sizing: border-box; margin: 0; padding: 0; }")
    html.append("    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); padding: 2rem 1rem; line-height: 1.5; }")
    html.append("    .container { max-width: 1100px; margin: 0 auto; }")
    html.append("    header { margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }")
    html.append("    h1 { font-size: 1.8rem; font-weight: 700; color: #fff; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem; }")
    html.append("    .meta { color: var(--muted); font-size: 0.9rem; }")
    html.append("    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }")
    html.append("    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }")
    html.append("    .card-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 0.35rem; }")
    html.append("    .card-value { font-size: 1.8rem; font-weight: 700; color: #fff; }")
    html.append("    .card-sub { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }")
    html.append("    .section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }")
    html.append("    h2 { font-size: 1.2rem; font-weight: 600; margin-bottom: 1rem; color: #fff; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }")
    html.append("    ul.findings { list-style: none; display: flex; flex-direction: column; gap: 0.75rem; }")
    html.append("    ul.findings li { background: rgba(255,255,255,0.03); padding: 0.75rem 1rem; border-radius: 8px; border-left: 4px solid var(--accent); font-size: 0.95rem; }")
    html.append("    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; text-align: left; }")
    html.append("    th { background: rgba(255,255,255,0.05); color: var(--muted); font-weight: 600; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }")
    html.append("    td { padding: 0.75rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); }")
    html.append("    tr:hover { background: rgba(255,255,255,0.02); }")
    html.append("    tr.total-row { font-weight: 700; background: rgba(56, 189, 248, 0.08); }")
    html.append("    tr.total-row td { border-bottom: 2px solid var(--accent); }")
    html.append("    .num { text-align: right; font-variant-numeric: tabular-nums; }")
    html.append("    .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }")
    html.append("    .badge-err { background: rgba(239,68,68,0.2); color: #f87171; }")
    html.append("    .badge-ok { background: rgba(34,197,94,0.2); color: #4ade80; }")
    html.append("    .footer { text-align: center; color: var(--muted); font-size: 0.85rem; margin-top: 2rem; }")
    html.append("    .btn { display: inline-block; background: var(--accent); color: #0f172a; font-weight: 600; padding: 0.6rem 1.25rem; border-radius: 8px; text-decoration: none; margin-top: 0.5rem; transition: opacity 0.2s; }")
    html.append("    .btn:hover { opacity: 0.9; }")
    html.append("  </style>")
    html.append("</head>")
    html.append("<body>")
    html.append("  <div class=\"container\">")
    html.append("    <header>")
    html.append("      <h1>🚀 Load Test Performance Summary</h1>")
    html.append(f"      <div class=\"meta\">Generated on {ts_now} &bull; Directory: <code>{os.path.basename(os.path.abspath(results_dir))}</code></div>")
    html.append("    </header>")
    html.append("    <div class=\"grid\">")
    html.append("      <div class=\"card\">")
    html.append("        <div class=\"card-label\">Throughput (TPS)</div>")
    html.append(f"        <div class=\"card-value\" style=\"color: var(--accent);\">{format_rate(tps_val)}</div>")
    html.append("        <div class=\"card-sub\">Target: 6.00/s</div>")
    html.append("      </div>")
    html.append("      <div class=\"card\">")
    html.append("        <div class=\"card-label\">Error Rate</div>")
    html.append(f"        <div class=\"card-value\" style=\"color: {err_color};\">{err_pct_num:.2f}%</div>")
    html.append(f"        <div class=\"card-sub\">{format_num(total.get('errorCount', 0))} errors / {format_num(total.get('sampleCount', 0))} total</div>")
    html.append("      </div>")
    html.append("      <div class=\"card\">")
    html.append("        <div class=\"card-label\">Average Latency</div>")
    html.append(f"        <div class=\"card-value\">{format_ms(total.get('meanResTime', 0.0))}</div>")
    html.append(f"        <div class=\"card-sub\">Median (P50): {format_ms(total.get('medianResTime', 0.0))}</div>")
    html.append("      </div>")
    html.append("      <div class=\"card\">")
    html.append("        <div class=\"card-label\">95th Percentile (P95)</div>")
    html.append(f"        <div class=\"card-value\">{format_ms(total.get('pct2ResTime', 0.0))}</div>")
    html.append(f"        <div class=\"card-sub\">P99: {format_ms(total.get('pct3ResTime', 0.0))}</div>")
    html.append("      </div>")
    html.append("    </div>")

    html.append("    <div class=\"section\">")
    html.append("      <h2>Bottleneck & Capacity Analysis</h2>")
    html.append("      <ul class=\"findings\">")
    for f in findings:
        clean_finding = f.replace("**", "").replace("`", "")
        html.append(f"        <li>{clean_finding}</li>")
    html.append("      </ul>")
    html.append("    </div>")

    html.append("    <div class=\"section\">")
    html.append("      <h2>Transaction & Endpoint Breakdown</h2>")
    html.append("      <table>")
    html.append("        <thead>")
    html.append("          <tr>")
    html.append("            <th>Transaction / Sampler</th>")
    html.append("            <th class=\"num\">Samples</th>")
    html.append("            <th class=\"num\">Error %</th>")
    html.append("            <th class=\"num\">Avg Latency</th>")
    html.append("            <th class=\"num\">P50 (Med)</th>")
    html.append("            <th class=\"num\">P95</th>")
    html.append("            <th class=\"num\">Throughput</th>")
    html.append("          </tr>")
    html.append("        </thead>")
    html.append("        <tbody>")

    for k in keys:
        s = stats[k]
        is_tot = (k == 'Total')
        row_cls = " class=\"total-row\"" if is_tot else ""
        s_err = float(s.get('errorPct', 0.0))
        badge_cls = "badge-err" if s_err > 0.0 else "badge-ok"
        html.append(f"          <tr{row_cls}>")
        html.append(f"            <td><code>{k}</code></td>")
        html.append(f"            <td class=\"num\">{format_num(s.get('sampleCount', 0))}</td>")
        html.append(f"            <td class=\"num\"><span class=\"badge {badge_cls}\">{s_err:.1f}%</span></td>")
        html.append(f"            <td class=\"num\">{format_ms(s.get('meanResTime', 0.0))}</td>")
        html.append(f"            <td class=\"num\">{format_ms(s.get('medianResTime', 0.0))}</td>")
        html.append(f"            <td class=\"num\">{format_ms(s.get('pct2ResTime', 0.0))}</td>")
        html.append(f"            <td class=\"num\">{format_rate(s.get('throughput', 0.0))}</td>")
        html.append(f"          </tr>")

    html.append("        </tbody>")
    html.append("      </table>")
    html.append("    </div>")

    dashboard_rel = os.path.join("dashboard", "index.html")
    if os.path.isfile(os.path.join(results_dir, dashboard_rel)):
        html.append("    <div class=\"footer\">")
        html.append(f"      <p>Looking for interactive percentile graphs, thread over time, and response time charts?</p>")
        html.append(f"      <a class=\"btn\" href=\"{dashboard_rel}\" target=\"_blank\">View Full JMeter Dashboard &rarr;</a>")
        html.append("    </div>")

    html.append("  </div>")
    html.append("</body>")
    html.append("</html>")

    with open(html_file, "w", encoding="utf-8") as f:
        f.write("\n".join(html) + "\n")

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
    print(f" Summary Markdown Saved:   {summary_file}")
    print(f" Standalone HTML Report:   {html_file}")
    print(f" Interactive Dashboard:    {os.path.join(results_dir, 'dashboard', 'index.html')}")
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
