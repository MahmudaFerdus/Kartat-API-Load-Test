# Kartat gateway purchase load test

One JMeter plan, `kartat-gateway-purchase.jmx`, runs in the GUI and headless. It calls only these GATEWAY.CD.DEV APIs:

1. `POST /oauth/token`
2. `POST /api/v1/stock/purchase/validate`
3. `POST /api/v1/stock/purchase/execute`

`base_url` defaults to `https://dev-apigw.cardselling.cash`. Each thread logs in once, keeps the `access_token`, and reuses the single reseller row in `data/reseller.csv`. Every attempt picks the next product/bundle row, calls validate, and calls execute only when validate returns `"status": true`.

The token and purchase bodies are multipart form fields, matching the Postman requests. Postman also lists `Content-Type: application/json` on the token call; the body mode is form-data, so this plan sends `multipart/form-data` and `Accept: application/json`.

## Before you run

Install Apache JMeter 5.6 (or newer) and set `JMETER_HOME`, or put `jmeter` on `PATH`.

Copy `.env.example` to `.env` (either in the project root or in `jmeter/`):

```bash
cp .env.example .env
```

Configure `CLIENT_ID`, `CLIENT_SECRET`, and `PASSWORD` in `.env`. You can also configure all load and purchase parameters (`NUM_THREADS`, `RAMP_TIME`, `DURATION`, `BASE_URL`, etc.) directly in `.env`.

> [!NOTE]
> `.env` is gitignored. The test plan automatically checks for `.env` (in current and parent directory) and falls back to `secrets.properties` if present.

## Finding Bottlenecks (2-Core CPU / 4GB RAM Server)

To discover the maximum throughput, latency breakpoint, and resource exhaustion point on a **2-Core CPU / 4GB RAM** target server:

```bash
./run-bottleneck-test.sh
```

Or on Windows:

```bat
run-bottleneck-test.cmd
```

### How the Bottleneck Test Works:
1. **Concurrency Ramp:** Smoothly ramps active users from 1 to 60 over 5 minutes (300 seconds), adding 1 new concurrent user every 5 seconds.
2. **Saturation Hold:** Sustains peak load for an additional 2 minutes (120 seconds).
3. **Automated Summary Report:** Instantly prints an executive summary table to the terminal upon completion and saves a formatted `summary.md` inside the results folder.
4. **Interactive HTML Dashboard:** Generates complete charts and telemetry in `results/bottleneck-YYYYMMDD-HHMMSS/dashboard/`.

### What to Monitor on the Target Server:
Run the lightweight monitor script directly on the target server during the test:
```bash
chmod +x server-monitor.sh
./server-monitor.sh > server-metrics.csv
```
This logs CPU (%usr, %sys, %wa, %id), Memory, Swap, Load Average, and TCP connection counts every second.

### Interpreting the Bottleneck:
Open `dashboard/index.html` in your browser:
- **Throughput Plateau (Max Capacity):** Check **Transactions Per Second (TPS)** vs **Active Threads Over Time**. Note the thread count where TPS stops growing and flatlines. On a 2-core machine, this typically happens between 15–40 concurrent users.
- **Queueing Latency (Knee of the Curve):** In **Response Times Over Time**, identify where latency jumps exponentially (e.g. from 200ms to 2,000ms+). That point is your safe operational ceiling.
- **Errors & Timeouts:** In **Response Codes Over Time**, identify when HTTP 502/504 errors or connection timeouts begin appearing.
- **Correlating Server Metrics:** If CPU Idle hits `0%` with high User%, the bottleneck is compute (application logic / hashing / serialization). If CPU IOWait (`%wa`) spikes or Swap usage climbs above 0MB, the 4GB RAM limit was reached and the database/OS began disk thrashing.

## GUI

From this folder:

```bat
run-gui.cmd
```

```bash
./run-gui.sh
```

The launcher loads the 180 purchases / 60 seconds profile and opens the plan. Press Start.

Another profile or a single override:

```bat
run-gui.cmd -q load-900-purchases-300-seconds.properties
run-gui.cmd -Jnum_threads=10 -JtotalPurchases=20 -Jduration=30 -JthreadGroupDuration=45
```

```bash
./run-gui.sh -q load-open-loop.properties
```

You can also open `kartat-gateway-purchase.jmx` from JMeter's File menu. The setup thread still reads `secrets.properties` next to the plan. Thread count, ramp, duration, and purchase count then use the defaults in the plan (fixed shape, 180 purchases, 60 seconds, 30 threads, 5 second ramp) unless you started JMeter with `-q` or `-J`.

Summary Report is on the plan. View Results Tree is off; turn it on only for a short local debug, and do not save that output.

## Headless

```bat
run-nongui.cmd
run-nongui.cmd -q load-900-purchases-300-seconds.properties
run-nongui.cmd -q load-open-loop.properties -Jnum_threads=20 -Jduration=120 -JthreadGroupDuration=120
```

```bash
./run-nongui.sh
./run-nongui.sh -q load-900-purchases-300-seconds.properties
./run-nongui.sh -q load-open-loop.properties -Jnum_threads=20 -Jduration=120 -JthreadGroupDuration=120
```

A later `-q` or `-J` overrides the default 180/60 file. Each run writes a new folder `results/yyyyMMdd-HHmmss` (`results\yyyyMMdd-HHmmss` on Windows) containing `results.jtl` and `dashboard/index.html`. If that folder already exists, the name gains `-1`, `-2`, and so on. The launcher does not reuse `results\run`. The jtl stores status and URL, not request or response bodies.

## Shapes and properties

| Property | Fixed default | What it does |
| --- | --- | --- |
| `loadShape` | `fixed` | `fixed` schedules an exact attempt count. `open` repeats until the duration ends. |
| `totalPurchases` | `180` | Attempts to start. On `open`, `0` means no cap. |
| `duration` | `60` | Seconds the attempts are spread across, or how long `open` runs. |
| `threadGroupDuration` | `90` | Scheduler cap. Fixed profiles use duration plus `drainSeconds`. |
| `drainSeconds` | `30` | Extra time so a slow last call can finish. |
| `num_threads` | `30` | Workers. Keep this at least `(totalPurchases / duration) * seconds per purchase`. |
| `ramp_time` | `5` | Seconds to start all threads. |
| `enablePurchaseThrottle` | `false` | On `open`, `true` spaces starts at `targetPurchaseTps`. |
| `targetPurchaseTps` | `3` | Used only when the throttle is on. |

Profiles:

- `load-180-purchases-60-seconds.properties` — fixed, 180 attempts, 60 seconds
- `load-900-purchases-300-seconds.properties` — fixed, 900 attempts, 300 seconds
- `load-open-loop.properties` — open, 10 threads, 300 seconds, no purchase cap

## Catalog rows

`data/products.csv` is the round-robin list. Each purchase attempt takes the next row for both validate and execute. `product_id` is sent as `operator_id`. `bundle_id` is sent as `bundle_id`.

| product_id | bundle_id | name |
| --- | --- | --- |
| 116 | 1082 | Bundle |
| 116 | 1083 | Bundle |
| 125 | 1089 | Bundle |
| 125 | 1088 | Bundle |
| 116 | 1074 | Bundle |
| 125 | 1084 | Bundle |

The sheet has no `msisdn` column, so every row uses `9647706055187` (the `asiacellMsisdn` default). `sip` is `0662981885` and `dealer_number` is `ABC123`. Override them with `-JasiacellMsisdn`, `-Jsip`, and `-Jdealer_number`.
