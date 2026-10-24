"""Durable spend/call reservations (audit A08). Every model request reserves BEFORE dispatch, independent of whether
the provider later reports usage, so restarts, retries and failed attempts cannot escape the cap."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from greenops.adapters.model import Budget, BudgetExceeded
from greenops.db import connect

_SCOPES = ("eval_run", "trial_id", "investigation_id")


class DurableBudget(Budget):
    def __init__(self, db: str, *, investigation_id=None, trial_id=None, eval_run: str | None = None, limits: dict,
                 parent_limits: dict | None = None, daily_cap_usd: Decimal | None = None, deadline: datetime | None = None):
        """`limits` bind the most specific scope given (eval_run > trial > investigation); `parent_limits` bind the
        investigation when a trial is also given. Each dict: max_calls, max_cost_usd, per_call_usd."""
        self.db, self.daily_cap, self.deadline = db, daily_cap_usd, deadline
        self.ids = {"investigation_id": investigation_id, "trial_id": trial_id, "eval_run": eval_run}
        primary = next(s for s in _SCOPES if self.ids[s] is not None)
        self.rules = [(primary, limits)]
        if parent_limits and primary != "investigation_id" and investigation_id is not None:
            self.rules.append(("investigation_id", parent_limits))
        self.per_call = Decimal(str(limits["per_call_usd"]))
        super().__init__(int(limits["max_calls"]), Decimal(str(limits["max_cost_usd"])), self.per_call, 0)

    def reserve(self) -> None:
        with connect(self.db) as c:
            c.execute("SELECT pg_advisory_xact_lock(4208)")  # ponytail: one global budget lock; per-scope locks if contention matters
            now = c.execute("SELECT now() AS n").fetchone()["n"]
            if self.deadline is not None and now >= self.deadline:
                raise BudgetExceeded("time budget for this stage is exhausted")
            for col, lim in self.rules:
                row = c.execute(f"SELECT COUNT(*) AS n, COALESCE(SUM(conservative_cost_usd), 0) AS cost FROM budget_reservations WHERE {col}::text=%s",
                                (str(self.ids[col]),)).fetchone()
                if row["n"] + 1 > int(lim["max_calls"]):
                    raise BudgetExceeded(f"{col} call budget {lim['max_calls']} exhausted")
                if row["cost"] + self.per_call > Decimal(str(lim["max_cost_usd"])):
                    raise BudgetExceeded(f"{col} conservative spend reservation would exceed {lim['max_cost_usd']} USD")
            if self.daily_cap is not None:
                day = c.execute("SELECT COALESCE(SUM(conservative_cost_usd), 0) AS cost FROM budget_reservations "
                                "WHERE created_at >= date_trunc('day', now())").fetchone()["cost"]
                if day + self.per_call > self.daily_cap:
                    raise BudgetExceeded(f"daily cap {self.daily_cap} USD would be exceeded")
            c.execute("INSERT INTO budget_reservations (id, investigation_id, trial_id, eval_run, conservative_cost_usd) VALUES (%s,%s,%s,%s,%s)",
                      (uuid.uuid4(), self.ids["investigation_id"], self.ids["trial_id"], self.ids["eval_run"], self.per_call))
        self.used_calls += 1


def investigation_limits(inv: dict) -> dict:
    b = inv["budget_snapshot"]
    return {"max_calls": b["max_model_calls"], "max_cost_usd": b["max_run_cost_usd"], "per_call_usd": b["max_conservative_cost_per_call_usd"]}
