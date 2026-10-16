"""Pure presentation helpers: status labels, icons, basis labels, timestamps and plain-language reasons.

No Streamlit imports here so the mapping rules stay unit-testable. Every status label carries text and a
glyph/icon; color is only ever an extra cue.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

MODE_LABELS = {"sample": "Sample", "connected_demo": "Connected demo", "replay": "Recorded replay"}
EXECUTOR_LABEL = "local analogue (real local config change, not a GCP resize)"

# tone -> (table glyph, material icon, st.badge color)
TONES = {
    "ok": ("✔", ":material/check_circle:", "green"),
    "fail": ("✖", ":material/cancel:", "red"),
    "attention": ("⚠", ":material/warning:", "orange"),
    "progress": ("…", ":material/hourglass_top:", "blue"),
    "neutral": ("○", ":material/radio_button_unchecked:", "gray"),
    "unknown": ("?", ":material/help:", "orange"),
    "restored": ("↺", ":material/settings_backup_restore:", "blue"),
}

# Action outcomes that share a tone still need distinct icons (UX_SPEC: RECOVERY_REQUIRED / RECOVERED / FAILED and
# EXECUTING / PENDING_VERIFICATION must be visibly different, not only by color).
STATUS_ICON = {
    "FAILED": ":material/cancel:",
    "RECOVERY_REQUIRED": ":material/engineering:",
    "RECOVERED": ":material/settings_backup_restore:",
    "RECOVERING": ":material/restore:",
    "PENDING_VERIFICATION": ":material/pending:",
    "EXECUTING": ":material/hourglass_top:",
}

STATUS_TONE = {
    # checks / trials / readiness
    "PASS": "ok", "PASSED": "ok", "ready": "ok", "complete": "ok", "VERIFIED": "ok", "RECOVERED": "restored",
    "VALIDATED": "ok", "COMPLETED": "ok", "SENT": "ok", "ACTIVE": "ok", "ELIGIBLE_FOR_TRIAL": "ok",
    "FAIL": "fail", "FAILED": "fail", "REJECTED": "fail", "REJECT": "fail", "unavailable": "fail",
    "UNKNOWN": "unknown", "unknown": "unknown", "INCOMPLETE": "attention", "partial": "attention",
    # plan / investigation lifecycle
    "AWAITING_APPROVAL": "attention", "NEEDS_REVIEW": "attention", "NEEDS_EVIDENCE": "attention",
    "STALE": "attention", "APPROVED": "attention", "RECOVERY_REQUIRED": "fail", "degraded": "attention",
    "PENDING_VERIFICATION": "attention", "PENDING": "attention", "EXPIRED": "attention", "REVOKED": "neutral",
    "QUEUED": "progress", "RUNNING": "progress", "EXECUTING": "progress", "RECOVERING": "progress",
    "CANCEL_REQUESTED": "neutral", "DRAFT": "neutral", "NO_CHANGE": "neutral", "CANCELLED": "neutral",
    "NOT_REQUIRED": "neutral", "SKIPPED": "neutral",
}

STATUS_MEANING = {
    "DRAFT": "Draft — next step is a sandbox trial or more evidence",
    "NEEDS_EVIDENCE": "Evidence required before this can be screened",
    "REJECTED": "A required check failed; the reason is retained",
    "VALIDATED": "Checks passed",
    "AWAITING_APPROVAL": "Checks and trial passed — waiting for human review",
    "APPROVED": "Scoped approval recorded; execution is still pending",
    "STALE": "The plan or approval no longer matches current facts",
    "QUEUED": "Accepted and waiting for the worker",
    "RUNNING": "Work in progress",
    "EXECUTING": "Change in progress — the effect is not yet verified",
    "PENDING_VERIFICATION": "Change applied — effect not yet verified; do not retry",
    "VERIFIED": "Intended state and required health checks confirmed",
    "RECOVERY_REQUIRED": "Human intervention needed; see recovery details",
    "RECOVERING": "Restoring the exact prior configuration",
    "RECOVERED": "Prior configuration restored and read back; the intended change is not in effect",
    "FAILED": "Operation failed; see the precise outcome",
    "NO_CHANGE": "Investigation completed without an acceptable change",
    "NEEDS_REVIEW": "Investigation finished; candidates need human review",
    "COMPLETED": "Investigation completed with a verified change",
    "CANCELLED": "Cancelled at a safe boundary",
}


def tone(status: Any) -> str:
    return STATUS_TONE.get(str(status), "neutral")


def glyph(status: Any) -> str:
    """Table-safe status cell: glyph + text, e.g. '✔ PASS'."""
    if status is None or status == "":
        return "? UNKNOWN"
    return f"{TONES[tone(status)][0]} {status}"


def icon(status: Any) -> str:
    return STATUS_ICON.get(str(status)) or TONES[tone(status)][1]


def badge_color(status: Any) -> str:
    return TONES[tone(status)][2]


def dep_glyph(value: Any) -> str:
    """Dependency readiness cell: 'ready'/'configured' pass, 'unavailable:*'/'not_configured' fail, else unknown."""
    v = str(value)
    if value is None:
        return "? unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if v in ("ready", "configured"):
        return f"✔ {v}"
    if v.startswith("unavailable") or v == "not_configured":
        return f"✖ {v}"
    return f"? {v}"


def mode_label(mode: str | None) -> str:
    return MODE_LABELS.get(mode or "", f"Unknown mode ({mode})" if mode else "Unknown")


def fmt_ts(value: Any) -> str:
    """ISO timestamp -> 'YYYY-MM-DD HH:MM:SS UTC'. Unparseable values are shown verbatim."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if dt.tzinfo is None:
        return f"{dt:%Y-%m-%d %H:%M:%S} (no timezone)"
    return f"{dt.astimezone(timezone.utc):%Y-%m-%d %H:%M:%S} UTC"


def now_utc() -> str:
    return f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC"


def fmt_num(value: Any, places: int = 4) -> str:
    """Display-only rounding of decimal strings; None stays explicit."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    if not d.is_finite():
        return str(value)
    q = d.quantize(Decimal(1).scaleb(-places)) if d.as_tuple().exponent < -places else d
    s = format(q, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def cell(value: Any, limit: int = 160) -> str:
    """Stringify any value for a table cell (keeps Arrow column types uniform)."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        s = json.dumps(value, default=str, separators=(", ", ": "))
    else:
        s = str(value)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def inline(value: Any, limit: int = 240) -> str:
    """Readable one-line form of a nested value for a table cell: 'key: value · key: value' instead of raw JSON."""
    if isinstance(value, dict):
        if not value:
            return "—"
        s = " · ".join(f"{k}: {inline(v, limit)}" for k, v in value.items())
        return s if len(s) <= limit else s[: limit - 1] + "…"
    if isinstance(value, list):
        return ", ".join(inline(v, limit) for v in value) or "—"
    return cell(value, limit)


def short_id(value: Any) -> str:
    return str(value)[:8] if value else "—"


def impact_basis(impacts: dict | None) -> str:
    """Explicit basis label for the money impact of a plan."""
    if not impacts:
        return "Unknown"
    kind = impacts.get("result_kind")
    if kind == "projected":
        return "Projected at dated rate"
    if kind == "measured":
        return "Measured workload"
    if kind == "observed":
        return "Observed billing"
    if kind == "estimated":
        return "Estimated"
    reason = impacts.get("reason")
    return f"Unknown — {reason}" if reason else "Unknown"


def carbon_basis(carbon: dict | None) -> str:
    if carbon and carbon.get("result_kind") == "estimated" and carbon.get("method_version"):
        return "Estimated carbon"
    return "Unknown — emission factors unavailable"


def failing_checks(plan: dict) -> list[dict]:
    return [c for c in ((plan.get("screening") or {}).get("checks") or []) if c.get("status") != "PASS"]


def plan_reason(plan: dict, feedback: list[dict] | None = None) -> str:
    """Plain-language reason for a queue row, built from failing/unknown checks and trial feedback."""
    status = plan.get("status")
    bad = failing_checks(plan)
    if bad:
        verb = "Rejected" if status == "REJECTED" else "Attention"
        parts = [f"{c.get('check_id')} {c.get('status')}: {c.get('detail')}" for c in bad]
        return f"{verb}: " + "; ".join(parts)
    trial = (plan.get("critic") or {}).get("trial") or {}
    if trial.get("status") in ("FAILED", "INCOMPLETE"):
        sig = (plan.get("screening") or {}).get("signature")
        for f in feedback or []:
            if f.get("trial_id") == trial.get("trial_id") or (f.get("signature") == sig and f.get("trial_id")):
                return f"Trial {trial.get('status').lower()}: {f.get('reasons')}"
        return f"Trial {trial.get('status').lower()} (trial {short_id(trial.get('trial_id'))})"
    if plan.get("stale_reason"):
        return f"Stale: {plan['stale_reason']}"
    return STATUS_MEANING.get(status, str(status))


def freshness(plan: dict) -> str:
    for c in (plan.get("screening") or {}).get("checks") or []:
        if c.get("check_id") == "CHK-FRESHNESS":
            return f"{glyph(c.get('status'))} — {c.get('measured')} old (limit {c.get('limit')})"
    if plan.get("path") == "ai":
        return "Not applicable — measured by development-suite trial"
    return "? UNKNOWN — no freshness check recorded"


def before_after_rows(action: dict | None) -> list[dict]:
    """Rows of (setting, before, after) for any action shape."""
    if not action:
        return []
    before, after = action.get("before"), action.get("after")
    if isinstance(before, dict) or isinstance(after, dict):
        before, after = before or {}, after or {}
        return [{"Setting": k, "Before": cell(before.get(k)), "After": cell(after.get(k))}
                for k in list(dict.fromkeys([*before, *after]))]
    if "new_machine_type" in action:
        return [{"Setting": "machine_type", "Before": cell(action.get("expected_machine_type")),
                 "After": cell(action.get("new_machine_type"))}]
    return [{"Setting": k, "Before": "—", "After": cell(v)} for k, v in action.items() if k != "action_type"]


def environment_of(target_key: str | None) -> str:
    t = target_key or ""
    if t.startswith("local/sandbox/"):
        return "local sandbox"
    if "-prod" in t or "/prod" in t:
        return "production (not executable)"
    if "staging" in t or "-stg" in t:
        return "staging"
    return "unknown"


def cost_per_accepted(value: Any) -> str:
    return "Undefined: no accepted tasks" if value is None else f"{fmt_num(value, 8)} USD"


def usage_basis_label(basis: str | None) -> str:
    return {"provider": "provider-reported usage", "scripted_estimate": "scripted estimate (not provider billing)"}.get(
        basis or "", f"unknown basis ({basis})" if basis else "unknown basis")
