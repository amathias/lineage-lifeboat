from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import duckdb

from lineage_lifeboat.config import Settings
from lineage_lifeboat.demo_state import _assert_safe_state_dir
from lineage_lifeboat.domain.models import (
    AdapterEvidence,
    RecoveryStep,
    ValidationResult,
)

ORDERS_URN = "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.orders,PROD)"
CUSTOMERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.customers,PROD)"
)
STG_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
    "lifeboat.analytics.stg_orders,PROD)"
)
REVENUE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
    "lifeboat.analytics.customer_revenue,PROD)"
)
FEATURE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:featurestore,"
    "lifeboat.features.customer_value,PROD)"
)
MODEL_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:mlflow,lifeboat.models.churn_model,PROD)"
)
DASHBOARD_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:looker,"
    "lifeboat.dashboards.executive_revenue,PROD)"
)
INVENTORY_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.inventory.forecast,PROD)"
)

OUTAGE_TARGET_URNS = (
    ORDERS_URN,
    STG_ORDERS_URN,
    REVENUE_URN,
    FEATURE_URN,
    MODEL_URN,
    DASHBOARD_URN,
)
PRESERVED_URNS = (CUSTOMERS_URN, INVENTORY_URN)
TABLE_BY_URN = {
    ORDERS_URN: "raw.orders",
    CUSTOMERS_URN: "raw.customers",
    STG_ORDERS_URN: "analytics.stg_orders",
    REVENUE_URN: "analytics.customer_revenue",
    INVENTORY_URN: "inventory.forecast",
}
ARTIFACT_BY_URN = {
    FEATURE_URN: Path("features/customer_value.json"),
    MODEL_URN: Path("models/churn_model.json"),
    DASHBOARD_URN: Path("dashboards/executive_revenue.json"),
}
EXPECTED_SCHEMAS = {
    "raw.orders": ("order_id", "customer_id", "amount"),
    "raw.customers": ("customer_id", "customer_name", "segment"),
    "analytics.stg_orders": ("order_id", "customer_id", "amount"),
    "analytics.customer_revenue": (
        "customer_id",
        "customer_name",
        "total_revenue",
    ),
    "inventory.forecast": ("sku", "units"),
}


class DemoEstateError(RuntimeError):
    """Raised when the disposable estate cannot be operated safely."""


class RecoveryAdapterError(RuntimeError):
    """Raised when a local recovery adapter cannot produce evidence."""


class Adapter(Protocol):
    def execute(self, step: RecoveryStep, idempotency_key: str) -> AdapterEvidence: ...


def _canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalise(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


@dataclass(slots=True)
class DemoEstate:
    settings: Settings
    root: Path = field(init=False)
    database_path: Path = field(init=False)
    artifact_root: Path = field(init=False)
    receipt_root: Path = field(init=False)
    repository_root: Path = field(init=False)

    def __post_init__(self) -> None:
        state_root = _assert_safe_state_dir(self.settings.app_state_dir)
        self.root = state_root / "demo-estate"
        self.database_path = self.root / "commerce.duckdb"
        self.artifact_root = self.root / "artifacts"
        self.receipt_root = self.root / "receipts"
        self.repository_root = self.settings.demo_fixture_root.resolve().parents[2]

    def _connect(self) -> duckdb.DuckDBPyConnection:
        self.root.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.database_path))

    def _assert_confirmation(self, confirm_project: str) -> None:
        if confirm_project != self.settings.project_slug:
            raise DemoEstateError(
                f"demo estate action requires confirm_project={self.settings.project_slug}"
            )

    @property
    def orders_snapshot_path(self) -> Path:
        return self.repository_root / "demo" / "snapshots" / "raw_orders.parquet"

    @property
    def customers_fixture_path(self) -> Path:
        return self.repository_root / "demo" / "snapshots" / "raw_customers.csv"

    def initialize(self, confirm_project: str) -> dict[str, Any]:
        self._assert_confirmation(confirm_project)
        if self.database_path.is_file():
            self.database_path.unlink()
        if self.artifact_root.is_dir():
            for path in sorted(self.artifact_root.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
        if not self.orders_snapshot_path.is_file():
            raise DemoEstateError(
                f"orders snapshot is missing: {self.orders_snapshot_path}"
            )
        if not self.customers_fixture_path.is_file():
            raise DemoEstateError(
                f"customers fixture is missing: {self.customers_fixture_path}"
            )

        with self._connect() as connection:
            connection.execute("CREATE SCHEMA raw")
            connection.execute("CREATE SCHEMA analytics")
            connection.execute("CREATE SCHEMA inventory")
            snapshot = str(self.orders_snapshot_path).replace("'", "''")
            customers = str(self.customers_fixture_path).replace("'", "''")
            connection.execute(
                "CREATE TABLE raw.orders AS "
                f"SELECT order_id, customer_id, amount FROM read_parquet('{snapshot}')"
            )
            connection.execute(
                "CREATE TABLE raw.customers AS "
                "SELECT customer_id, customer_name, segment "
                f"FROM read_csv('{customers}', header=true)"
            )
            connection.execute(
                "CREATE TABLE inventory.forecast AS "
                "SELECT * FROM (VALUES ('SKU-001', 42), ('SKU-002', 17)) "
                "AS forecast(sku, units)"
            )
            self._materialize_stg_orders(connection)
            self._materialize_customer_revenue(connection)
        self._write_feature_artifact()
        self._write_model_artifact()
        self._write_dashboard_artifact()

        receipt = {
            "operation": "initialize_disposable_demo_estate",
            "project_slug": self.settings.project_slug,
            "action_class": "executed_local_disposable",
            "datahub_mutated": False,
            "asset_state": self.inspect(),
        }
        self._write_receipt("demo-initialize-receipt.json", receipt)
        return receipt

    def trigger_outage(self, confirm_project: str) -> dict[str, Any]:
        self._assert_confirmation(confirm_project)
        if not self.database_path.is_file():
            raise DemoEstateError("initialize the disposable demo estate first")
        removed: list[str] = []
        with self._connect() as connection:
            for urn in (ORDERS_URN, STG_ORDERS_URN, REVENUE_URN):
                table = TABLE_BY_URN[urn]
                if self._table_exists(connection, table):
                    connection.execute(f"DROP TABLE {table}")
                    removed.append(urn)
        for urn, relative_path in ARTIFACT_BY_URN.items():
            path = self.artifact_root / relative_path
            if path.is_file():
                path.unlink()
                removed.append(urn)

        receipt = {
            "operation": "trigger_disposable_commerce_outage",
            "project_slug": self.settings.project_slug,
            "action_class": "executed_local_disposable",
            "removed_asset_urns": sorted(removed),
            "preserved_asset_urns": list(PRESERVED_URNS),
            "foreign_assets_touched": False,
            "datahub_mutated": False,
            "asset_state": self.inspect(),
        }
        self._write_receipt("demo-outage-receipt.json", receipt)
        return receipt

    def inspect(self) -> dict[str, Any]:
        table_state: dict[str, bool] = {}
        if self.database_path.is_file():
            with self._connect() as connection:
                table_state = {
                    urn: self._table_exists(connection, table)
                    for urn, table in TABLE_BY_URN.items()
                }
        else:
            table_state = {urn: False for urn in TABLE_BY_URN}
        artifact_state = {
            urn: (self.artifact_root / relative_path).is_file()
            for urn, relative_path in ARTIFACT_BY_URN.items()
        }
        assets = {**table_state, **artifact_state}
        return {
            "initialized": self.database_path.is_file(),
            "healthy_asset_count": sum(assets.values()),
            "asset_count": len(assets),
            "assets": dict(sorted(assets.items())),
        }

    def asset_exists(self, urn: str) -> bool:
        if urn in TABLE_BY_URN:
            if not self.database_path.is_file():
                return False
            with self._connect() as connection:
                return self._table_exists(connection, TABLE_BY_URN[urn])
        if urn in ARTIFACT_BY_URN:
            return (self.artifact_root / ARTIFACT_BY_URN[urn]).is_file()
        return False

    def table_schema(self, table: str) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(f"DESCRIBE {table}").fetchall()
        return tuple(str(row[0]) for row in rows)

    def table_rows(self, table: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(f"SELECT * FROM {table} ORDER BY ALL")
            columns = tuple(item[0] for item in cursor.description)
            rows = cursor.fetchall()
        return [
            {column: _normalise(value) for column, value in zip(columns, row, strict=True)}
            for row in rows
        ]

    def table_fingerprint(self, table: str) -> str:
        payload = {
            "schema": self.table_schema(table),
            "rows": self.table_rows(table),
        }
        return _sha256_bytes(_canonical_bytes(payload))

    def artifact_path(self, urn: str) -> Path:
        try:
            return self.artifact_root / ARTIFACT_BY_URN[urn]
        except KeyError as error:
            raise DemoEstateError(f"URN has no local artifact: {urn}") from error

    def artifact_payload(self, urn: str) -> dict[str, Any]:
        payload = json.loads(self.artifact_path(urn).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise DemoEstateError(f"artifact payload must be an object: {urn}")
        return payload

    def artifact_fingerprint(self, urn: str) -> str:
        return _sha256_bytes(self.artifact_path(urn).read_bytes())

    def write_artifact(self, urn: str, payload: dict[str, Any]) -> tuple[str, bool]:
        path = self.artifact_path(urn)
        encoded = _canonical_bytes(payload)
        if path.is_file() and path.read_bytes() == encoded:
            return _sha256_bytes(encoded), False
        _atomic_write(path, encoded)
        return _sha256_bytes(encoded), True

    def materialize_table(self, table: str, query: str) -> tuple[str, bool, int]:
        with self._connect() as connection:
            cursor = connection.execute(query)
            columns = tuple(item[0] for item in cursor.description)
            rows = cursor.fetchall()
            expected_payload = {
                "schema": columns,
                "rows": [
                    {
                        column: _normalise(value)
                        for column, value in zip(columns, row, strict=True)
                    }
                    for row in rows
                ],
            }
            expected_hash = _sha256_bytes(_canonical_bytes(expected_payload))
            if self._table_exists(connection, table):
                current_hash = self.table_fingerprint(table)
                if current_hash == expected_hash:
                    return current_hash, False, len(rows)
            connection.execute(f"CREATE OR REPLACE TABLE {table} AS {query}")
        return self.table_fingerprint(table), True, len(rows)

    def restore_orders(self) -> tuple[str, bool, int]:
        snapshot = str(self.orders_snapshot_path).replace("'", "''")
        query = (
            "SELECT order_id, customer_id, amount "
            f"FROM read_parquet('{snapshot}') ORDER BY order_id"
        )
        return self.materialize_table("raw.orders", query)

    def build_feature_payload(self) -> dict[str, Any]:
        rows = self.table_rows("analytics.customer_revenue")
        records = [
            {
                "customer_id": row["customer_id"],
                "lifetime_value": round(float(row["total_revenue"]), 2),
                "value_band": (
                    "high" if float(row["total_revenue"]) >= 100 else "standard"
                ),
            }
            for row in rows
        ]
        return {
            "artifact": "features.customer_value",
            "input_fingerprint": self.table_fingerprint(
                "analytics.customer_revenue"
            ),
            "records": records,
        }

    def build_model_payload(self) -> dict[str, Any]:
        feature_fingerprint = self.artifact_fingerprint(FEATURE_URN)
        feature_payload = self.artifact_payload(FEATURE_URN)
        return {
            "artifact": "models.churn_model",
            "algorithm": "deterministic_demo_threshold",
            "input_fingerprint": feature_fingerprint,
            "metrics": {"accuracy": 0.83},
            "trained_records": len(feature_payload["records"]),
        }

    def build_dashboard_payload(self) -> dict[str, Any]:
        rows = self.table_rows("analytics.customer_revenue")
        return {
            "artifact": "dashboards.executive_revenue",
            "customer_count": len(rows),
            "input_fingerprint": self.table_fingerprint(
                "analytics.customer_revenue"
            ),
            "total_revenue": round(
                sum(float(row["total_revenue"]) for row in rows), 2
            ),
        }

    def _write_feature_artifact(self) -> None:
        self.write_artifact(FEATURE_URN, self.build_feature_payload())

    def _write_model_artifact(self) -> None:
        self.write_artifact(MODEL_URN, self.build_model_payload())

    def _write_dashboard_artifact(self) -> None:
        self.write_artifact(DASHBOARD_URN, self.build_dashboard_payload())

    @staticmethod
    def _materialize_stg_orders(connection: duckdb.DuckDBPyConnection) -> None:
        connection.execute(
            "CREATE OR REPLACE TABLE analytics.stg_orders AS "
            "SELECT order_id, customer_id, CAST(amount AS DOUBLE) AS amount "
            "FROM raw.orders ORDER BY order_id"
        )

    @staticmethod
    def _materialize_customer_revenue(
        connection: duckdb.DuckDBPyConnection,
    ) -> None:
        connection.execute(
            "CREATE OR REPLACE TABLE analytics.customer_revenue AS "
            "SELECT c.customer_id, c.customer_name, "
            "ROUND(COALESCE(SUM(o.amount), 0), 2) AS total_revenue "
            "FROM raw.customers c "
            "LEFT JOIN analytics.stg_orders o USING (customer_id) "
            "GROUP BY c.customer_id, c.customer_name ORDER BY c.customer_id"
        )

    @staticmethod
    def _table_exists(
        connection: duckdb.DuckDBPyConnection, table: str
    ) -> bool:
        schema, name = table.split(".", maxsplit=1)
        return (
            connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = ? AND table_name = ?",
                [schema, name],
            ).fetchone()[0]
            == 1
        )

    def _write_receipt(self, filename: str, receipt: dict[str, Any]) -> Path:
        path = self.receipt_root / filename
        _atomic_write(path, _canonical_bytes(receipt))
        return path


@dataclass(slots=True)
class SnapshotRestoreAdapter:
    estate: DemoEstate

    def execute(self, step: RecoveryStep, idempotency_key: str) -> AdapterEvidence:
        output_sha256, executed, row_count = self.estate.restore_orders()
        return AdapterEvidence(
            adapter=step.adapter,
            action="restored_snapshot" if executed else "reused_verified_output",
            executed=executed,
            idempotency_key=idempotency_key,
            target=TABLE_BY_URN[step.target_urn],
            output_sha256=output_sha256,
            details={
                "row_count": row_count,
                "snapshot": "demo/snapshots/raw_orders.parquet",
            },
        )


@dataclass(slots=True)
class SqlTransformAdapter:
    estate: DemoEstate

    def execute(self, step: RecoveryStep, idempotency_key: str) -> AdapterEvidence:
        model = str(step.adapter_parameters.get("model", ""))
        if model == "stg_orders":
            table = "analytics.stg_orders"
            query = (
                "SELECT order_id, customer_id, CAST(amount AS DOUBLE) AS amount "
                "FROM raw.orders ORDER BY order_id"
            )
        elif model == "customer_revenue":
            table = "analytics.customer_revenue"
            query = (
                "SELECT c.customer_id, c.customer_name, "
                "ROUND(COALESCE(SUM(o.amount), 0), 2) AS total_revenue "
                "FROM raw.customers c "
                "LEFT JOIN analytics.stg_orders o USING (customer_id) "
                "GROUP BY c.customer_id, c.customer_name ORDER BY c.customer_id"
            )
        else:
            raise RecoveryAdapterError(f"unsupported SQL model: {model}")
        output_sha256, executed, row_count = self.estate.materialize_table(
            table, query
        )
        return AdapterEvidence(
            adapter=step.adapter,
            action="executed_sql_transform" if executed else "reused_verified_output",
            executed=executed,
            idempotency_key=idempotency_key,
            target=table,
            output_sha256=output_sha256,
            details={"model": model, "row_count": row_count},
        )


@dataclass(slots=True)
class PythonBuildAdapter:
    estate: DemoEstate

    def execute(self, step: RecoveryStep, idempotency_key: str) -> AdapterEvidence:
        job = str(step.adapter_parameters.get("job", ""))
        if job == "customer_value":
            urn = FEATURE_URN
            payload = self.estate.build_feature_payload()
        elif job == "churn_model":
            urn = MODEL_URN
            payload = self.estate.build_model_payload()
        else:
            raise RecoveryAdapterError(f"unsupported Python build job: {job}")
        output_sha256, executed = self.estate.write_artifact(urn, payload)
        return AdapterEvidence(
            adapter=step.adapter,
            action="executed_python_build" if executed else "reused_verified_output",
            executed=executed,
            idempotency_key=idempotency_key,
            target=ARTIFACT_BY_URN[urn].as_posix(),
            output_sha256=output_sha256,
            details={"job": job},
        )


@dataclass(slots=True)
class ReportRefreshAdapter:
    estate: DemoEstate

    def execute(self, step: RecoveryStep, idempotency_key: str) -> AdapterEvidence:
        report = str(step.adapter_parameters.get("report", ""))
        if report != "executive_revenue":
            raise RecoveryAdapterError(f"unsupported report refresh: {report}")
        payload = self.estate.build_dashboard_payload()
        output_sha256, executed = self.estate.write_artifact(
            DASHBOARD_URN, payload
        )
        return AdapterEvidence(
            adapter=step.adapter,
            action="refreshed_report" if executed else "reused_verified_output",
            executed=executed,
            idempotency_key=idempotency_key,
            target=ARTIFACT_BY_URN[DASHBOARD_URN].as_posix(),
            output_sha256=output_sha256,
            details={"report": report},
        )


def default_adapter_registry(estate: DemoEstate) -> dict[str, Adapter]:
    return {
        "snapshot_restore": SnapshotRestoreAdapter(estate),
        "sql_transform": SqlTransformAdapter(estate),
        "python_build": PythonBuildAdapter(estate),
        "report_refresh": ReportRefreshAdapter(estate),
    }


@dataclass(slots=True)
class ValidationEngine:
    estate: DemoEstate
    clock: Any = lambda: datetime.now(UTC)

    def validate(
        self, step: RecoveryStep, adapter_evidence: AdapterEvidence
    ) -> tuple[ValidationResult, ...]:
        return tuple(
            self._validate_one(step, spec.kind, spec.parameters, spec.required, adapter_evidence)
            for spec in step.validations
        )

    def _validate_one(
        self,
        step: RecoveryStep,
        kind: str,
        parameters: dict[str, Any],
        required: bool,
        adapter_evidence: AdapterEvidence,
    ) -> ValidationResult:
        try:
            if kind == "exists":
                passed = self.estate.asset_exists(step.target_urn)
                detail = "target exists" if passed else "target is missing"
                evidence: dict[str, Any] = {"target_urn": step.target_urn}
            elif kind == "schema":
                table = TABLE_BY_URN[step.target_urn]
                actual = self.estate.table_schema(table)
                expected = EXPECTED_SCHEMAS[table]
                passed = actual == expected
                detail = "schema matches" if passed else "schema mismatch"
                evidence = {"actual": actual, "expected": expected}
            elif kind == "row_count":
                table = TABLE_BY_URN[step.target_urn]
                actual_count = len(self.estate.table_rows(table))
                minimum = int(parameters.get("minimum", 0))
                passed = actual_count >= minimum
                detail = f"row count {actual_count} >= {minimum}"
                evidence = {"actual": actual_count, "minimum": minimum}
            elif kind == "checksum":
                table = TABLE_BY_URN[step.target_urn]
                actual_hash = self.estate.table_fingerprint(table)
                passed = actual_hash == adapter_evidence.output_sha256
                detail = "output checksum matches adapter evidence"
                evidence = {
                    "actual_sha256": actual_hash,
                    "adapter_sha256": adapter_evidence.output_sha256,
                }
            elif kind == "business_rule":
                rule = str(parameters.get("rule", ""))
                if rule != "revenue_nonnegative":
                    raise DemoEstateError(f"unsupported business rule: {rule}")
                rows = self.estate.table_rows("analytics.customer_revenue")
                minimum_revenue = min(float(row["total_revenue"]) for row in rows)
                passed = minimum_revenue >= 0
                detail = "all customer revenue values are nonnegative"
                evidence = {"minimum_revenue": minimum_revenue, "rule": rule}
            elif kind == "freshness":
                path = self.estate.artifact_path(step.target_urn)
                age_seconds = max(0.0, self.clock().timestamp() - path.stat().st_mtime)
                maximum = float(parameters["maximum_age_seconds"])
                passed = age_seconds <= maximum
                detail = f"artifact age {age_seconds:.3f}s <= {maximum:.3f}s"
                evidence = {"age_seconds": age_seconds, "maximum_age_seconds": maximum}
            elif kind == "artifact_load":
                payload = self.estate.artifact_payload(step.target_urn)
                passed = bool(payload)
                detail = "artifact loaded as JSON object"
                evidence = {"keys": sorted(payload)}
            elif kind == "metric_threshold":
                payload = self.estate.artifact_payload(step.target_urn)
                metric = str(parameters["metric"])
                actual_metric = float(payload["metrics"][metric])
                minimum = float(parameters["minimum"])
                passed = actual_metric >= minimum
                detail = f"{metric} {actual_metric:.2f} >= {minimum:.2f}"
                evidence = {"metric": metric, "actual": actual_metric, "minimum": minimum}
            elif kind == "input_fingerprint":
                payload = self.estate.artifact_payload(step.target_urn)
                expected_hash = self.estate.table_fingerprint(
                    "analytics.customer_revenue"
                )
                actual_hash = str(payload["input_fingerprint"])
                passed = actual_hash == expected_hash
                detail = "report input fingerprint matches recovered revenue table"
                evidence = {"actual": actual_hash, "expected": expected_hash}
            else:
                passed = False
                detail = f"unsupported validation kind: {kind}"
                evidence = {}
        except (KeyError, OSError, ValueError, DemoEstateError) as error:
            passed = False
            detail = f"validation error: {type(error).__name__}"
            evidence = {}
        return ValidationResult(
            kind=kind,
            required=required,
            passed=passed,
            detail=detail,
            evidence=evidence,
        )