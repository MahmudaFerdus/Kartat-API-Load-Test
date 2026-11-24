# Kartat API Load Test

JMeter plan for the Kartat gateway purchase flow: `POST /oauth/token`, `POST /api/v1/stock/purchase/validate`, and `POST /api/v1/stock/purchase/execute`.

## Quick Start (.env)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Fill in `CLIENT_ID`, `CLIENT_SECRET`, and `PASSWORD`.
3. Run the **2-Core / 4GB RAM Bottleneck Test**:
   ```bash
   cd jmeter
   ./run-bottleneck-test.sh
   ```
   Or on Windows:
   ```cmd
   cd jmeter
   run-bottleneck-test.cmd
   ```

See [jmeter/README.md](jmeter/README.md) for full documentation, GUI runs, open-loop profiles, and server monitoring guide.

## Catalog rows

`jmeter/data/products.csv` is the round-robin list. Each purchase attempt takes the next row for both validate and execute. `product_id` is sent as `operator_id`. `bundle_id` is sent as `bundle_id`. There is no `msisdn` column.

| product_id | bundle_id | name |
| --- | --- | --- |
| 116 | 1082 | Bundle |
| 116 | 1083 | Bundle |
| 125 | 1089 | Bundle |
| 125 | 1088 | Bundle |
| 131 | 1068 | Bundle |
| 131 | 1067 | Bundle |
| 105 | 1072 | Bundle |
| 124 | 1052 | Bundle |
