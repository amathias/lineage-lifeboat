# Lineage Lifeboat Recovery Report

- Run: `judge-demo-001`
- Plan: `plan-40f5c54e81b0b5cd5dad`
- Status: `completed`
- Graph fingerprint: `72accff2049653af2a7134d41559d3bb0e8ad9a27edefe2ed986155b85dc524b`
- Context: `captured_datahub_fixture`
- Verified steps: `6/6`
- DataHub outcome: `not_configured`

## Dependency waves

1. `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.orders,PROD)`
2. `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.stg_orders,PROD)`
3. `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.customer_revenue,PROD)`
4. `urn:li:dataset:(urn:li:dataPlatform:featurestore,lifeboat.features.customer_value,PROD)`, `urn:li:dataset:(urn:li:dataPlatform:looker,lifeboat.dashboards.executive_revenue,PROD)`
5. `urn:li:dataset:(urn:li:dataPlatform:mlflow,lifeboat.models.churn_model,PROD)`

## Execution evidence

- `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.orders,PROD)` — **verified**, attempts `1`, action `restored_snapshot`
  - PASS `exists`: target exists
  - PASS `schema`: schema matches
  - PASS `row_count`: row count 3 >= 1
- `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.stg_orders,PROD)` — **verified**, attempts `1`, action `executed_sql_transform`
  - PASS `exists`: target exists
  - PASS `schema`: schema matches
  - PASS `checksum`: output checksum matches adapter evidence
- `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.customer_revenue,PROD)` — **verified**, attempts `1`, action `executed_sql_transform`
  - PASS `exists`: target exists
  - PASS `schema`: schema matches
  - PASS `business_rule`: all customer revenue values are nonnegative
- `urn:li:dataset:(urn:li:dataPlatform:featurestore,lifeboat.features.customer_value,PROD)` — **verified**, attempts `1`, action `executed_python_build`
  - PASS `exists`: target exists
  - PASS `freshness`: artifact age 0.000s <= 300.000s
- `urn:li:dataset:(urn:li:dataPlatform:looker,lifeboat.dashboards.executive_revenue,PROD)` — **verified**, attempts `1`, action `refreshed_report`
  - PASS `exists`: target exists
  - PASS `input_fingerprint`: report input fingerprint matches recovered revenue table
- `urn:li:dataset:(urn:li:dataPlatform:mlflow,lifeboat.models.churn_model,PROD)` — **verified**, attempts `1`, action `executed_python_build`
  - PASS `artifact_load`: artifact loaded as JSON object
  - PASS `metric_threshold`: accuracy 0.83 >= 0.70

## Safety and writeback

- Approval: `demo-incident-commander`
- DataHub: DATAHUB_TOKEN is absent; local recovery remains runnable
- Cloud actions: none; all execution targets are local and disposable.
