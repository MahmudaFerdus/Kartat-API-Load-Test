# Kartat API Load Test

JMeter plan for the Kartat gateway purchase flow: `POST /oauth/token`, `POST /api/v1/stock/purchase/validate`, and `POST /api/v1/stock/purchase/execute`.

See [jmeter/README.md](jmeter/README.md) for GUI and headless runs.

## Catalog rows

`jmeter/data/products.csv` is the round-robin list. Each purchase attempt takes the next row for both validate and execute. `product_id` is sent as `operator_id`. `bundle_id` is sent as `bundle_id`. There is no `msisdn` column.

| product_id | bundle_id | name |
| --- | --- | --- |
| 116 | 1082 | Bundle |
| 116 | 1083 | Bundle |
| 125 | 1089 | Bundle |
| 125 | 1088 | Bundle |
| 116 | 1074 | Bundle |
| 125 | 1084 | Bundle |
