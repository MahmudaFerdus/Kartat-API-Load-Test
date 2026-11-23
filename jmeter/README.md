# Kartat gateway purchase load test

One JMeter plan, `kartat-gateway-purchase.jmx`, runs in the GUI and headless. It calls only these GATEWAY.CD.DEV APIs:

1. `POST /oauth/token`
2. `POST /api/v1/stock/purchase/validate`
3. `POST /api/v1/stock/purchase/execute`

`base_url` defaults to `https://dev-apigw.cardselling.cash`. Each thread logs in once, keeps the `access_token`, and reuses the single reseller row in `data/reseller.csv`. Every attempt picks the next product/bundle row, calls validate, and calls execute only when validate returns `"status": true`.

The token and purchase bodies are multipart form fields, matching the Postman requests. Postman also lists `Content-Type: application/json` on the token call; the body mode is form-data, so this plan sends `multipart/form-data` and `Accept: application/json`.

## Before you run

Install Apache JMeter 5.6 (or newer) and set `JMETER_HOME`, or put `jmeter` on `PATH`.

```bash
cp secrets.properties.example secrets.properties
```

Fill `client_id`, `client_secret`, and `password` in `secrets.properties`. That file is gitignored. The same file is picked up when you start from the GUI and when you run headless. Do not commit it, and do not enable response-body logging: the token request contains the password and client secret.

JMeter writes every `-J` value into `jmeter.log`. Keep `client_secret` and `password` in `secrets.properties`. The setup thread loads that file and does not write the values into the log.

The reseller username is `jewel+101@newroztech.com` in `data/reseller.csv`.

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

A later `-q` or `-J` overrides the default 180/60 file. Results go to `results/<timestamp>/results.jtl` and `results/<timestamp>/dashboard/index.html`. The jtl stores status and URL, not request or response bodies.

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

`data/products.csv` is the round-robin list. Both ids on a row appear in the Kartat gateway collection or the GATEWAY.CD.DEV environment. Add further rows the same way; do not invent ids.

| operator_id | product | bundle_id | bundle | Where it appears |
| --- | --- | --- | --- | --- |
| 101 | Amazon Gift Card | 1001 | Amazon - $10 US | Bundle list and purchase examples |
| 101 | Amazon Gift Card | 1015 | Amazon - 30$ | Bundle list for operator 101 |
| 101 | Amazon Gift Card | 1016 | Amazon - 25$ | Bundle list for operator 101 |
| 101 | Amazon Gift Card | 1017 | Amazon - 20$ | Bundle list for operator 101 |
| 101 | Amazon Gift Card | 1003 | GATEWAY.CD.DEV bundleId | Environment `operatorId` and `bundleId` (the collection list does not name this bundle) |
| 106 | Newroz | 1025 | purchase execute example | Execute example that pairs these two ids |

Operator 116 (Korek) is in the operator list, and the operator-info request uses 116. No bundle id is recorded for it. Bundle id 1082 does not appear in the collection or the environment, so there is no 116/1082 row.

These operators are in the collection and have no bundle id there, so they are not rows yet: 102 Apple Giftcard, 103 FTTH, 104 TKTATIK, 105 Fastlink, 107 Playstation, 108 Spider Man, 109 Xbox Live Gold, 110 Play station Network Card Global, 111 Hulu Plus Gift Card (US), 112 CALL OF DUTY (COD), 113 PUBG (PC), 114 Amazon Gift Card US, 115 Test, 117 Apple (MintRoute).

`msisdn` uses `9647706055187`, the first number in the enabled validate/execute `msisdn` description (`asiacellMsisdn` is not defined in the environment). `sip` is `0662981885` and `dealer_number` is `ABC123`, the enabled form values. Change them per row in the CSV (`msisdn`) or with `-Jsip` and `-Jdealer_number`.
