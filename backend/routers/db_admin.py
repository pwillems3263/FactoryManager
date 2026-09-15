"""
backend/routers/db_admin.py
-----------------------------
Admin-only database maintenance tools.

Currently exposes a single, carefully-guarded operation: replicate the full
content of the PRODUCTION database into the TEST/DEV database.

Safety measures:
  - Requires niveau 4 (Administrator), via the existing "users" permission.
  - Requires the caller's active session to be on the TEST database (you
    must "Switch to TEST" in the app before this is allowed) — this can
    never run while the caller is switched into PRODUCTION.
  - Requires the client to send an exact confirmation phrase, to prevent an
    accidental click from wiping TEST.
  - Only ever WRITES to the TEST database. PRODUCTION is only ever read.

Implementation notes:
  - "prod" and "test" are two entirely separate PostgreSQL databases (see
    database.py), so a single cross-database SQL query isn't possible
    without extensions like dblink/postgres_fdw. Instead, each table is
    read from PROD and re-inserted into TEST, in FK-safe dependency order
    (Base.metadata.sorted_tables), inside one TEST transaction.
  - TEST is wiped first with TRUNCATE ... RESTART IDENTITY CASCADE (cascade
    handles FK order for the delete; RESTART IDENTITY resets the
    auto-increment sequences), then every row from PROD is inserted with
    its original primary key, then each single-column integer PK sequence
    is re-synced to MAX(id) so future inserts continue from the right
    number.
  - For very large datasets this loads one table at a time into memory;
    fine for this app's scale, but worth knowing if tables grow huge.
"""
import models  # noqa: F401 — ensures every model is registered on Base.metadata
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, text

from auth import require_permission, get_db_key_from_token
from database import Base, _engines

router = APIRouter(prefix="/db-admin", tags=["Database Admin"])

CONFIRM_PHRASE = "REPLICATE PROD TO DEV"


class ReplicateRequest(BaseModel):
    confirm_phrase: str


class ReplicateResult(BaseModel):
    tables_copied: int
    rows_copied:   int


@router.get("/status")
def status(_user=Depends(require_permission("users"))):
    return {
        "environments": [
            {"key": "prod", "label": "PRODUCTION"},
            {"key": "test", "label": "TEST"},
        ],
        "confirm_phrase": CONFIRM_PHRASE,
    }


@router.post("/replicate-prod-to-test", response_model=ReplicateResult)
def replicate_prod_to_test(
    payload: ReplicateRequest,
    _user            = Depends(require_permission("users")),
    active_db_key    = Depends(get_db_key_from_token),
):
    if active_db_key == "prod":
        raise HTTPException(
            400,
            "Switch to the TEST environment (top bar) before running this operation."
        )

    if payload.confirm_phrase.strip() != CONFIRM_PHRASE:
        raise HTTPException(
            400,
            f'Type exactly "{CONFIRM_PHRASE}" to confirm this destructive operation.'
        )

    prod_engine = _engines["prod"]
    test_engine = _engines["test"]

    # Parent tables first, children after — resolved from the FK graph.
    tables = Base.metadata.sorted_tables

    rows_copied = 0
    with test_engine.begin() as test_conn:
        # Wipe TEST. CASCADE takes care of FK ordering for us; RESTART
        # IDENTITY resets every sequence to 1 (fixed up per-table below).
        if tables:
            table_list = ", ".join(f'"{t.name}"' for t in tables)
            test_conn.exec_driver_sql(
                f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"
            )

        with prod_engine.connect() as prod_conn:
            for table in tables:
                rows = prod_conn.execute(select(table)).mappings().all()
                if not rows:
                    continue

                test_conn.execute(table.insert(), [dict(r) for r in rows])
                rows_copied += len(rows)

                # Re-sync this table's PK sequence (single-column integer
                # PKs only — the only kind used in this schema).
                pk_cols = list(table.primary_key.columns)
                if len(pk_cols) == 1:
                    max_id = test_conn.execute(select(func.max(pk_cols[0]))).scalar()
                    if max_id is not None:
                        test_conn.execute(
                            text(
                                "SELECT setval(pg_get_serial_sequence(:tbl, :col), :val, true)"
                            ),
                            {"tbl": table.name, "col": pk_cols[0].name, "val": max_id},
                        )

    return ReplicateResult(tables_copied=len(tables), rows_copied=rows_copied)
