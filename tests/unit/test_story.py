"""Story page selection: each moment comes from the investigation's own records, or is absent (never invented)."""
from greenops.ui import present as P


def plan(pid, path, status, target, sig, checks=()):
    return {"id": pid, "path": path, "status": status, "target_key": target,
            "screening": {"signature": sig, "checks": [{"check_id": c, "status": s, "detail": c} for c, s in checks]}}


PROD, STG = "gcp/greenops-sbx-prod/worker-prod-01", "gcp/greenops-sbx-staging/worker-stg-01"
PLANS = [
    plan("p1", "cloud", "REJECTED", PROD, f"cloud:{PROD}:e2-standard-2", [("CHK-CPU-PEAK", "FAIL")]),
    plan("p2", "cloud", "REJECTED", STG, f"cloud:{STG}:e2-standard-2", [("CHK-CPU-PEAK", "FAIL")]),
    plan("p3", "cloud", "AWAITING_APPROVAL", STG, f"cloud:{STG}:e2-standard-4", [("CHK-CPU-PEAK", "PASS")]),
    plan("a1", "ai", "REJECTED", "local/sandbox/support-ai-workflow", "ai:truncated"),
    plan("a2", "ai", "AWAITING_APPROVAL", "local/sandbox/support-ai-workflow", "ai:relevant_sections"),
]
TRIALS = [{"id": "t3", "plan_id": "p3", "status": "PASSED"}, {"id": "ta1", "plan_id": "a1", "status": "FAILED"},
          {"id": "ta2", "plan_id": "a2", "status": "PASSED"}]


def test_story_picks_each_moment_from_records():
    s = P.story({"plans": PLANS, "trials": TRIALS, "memory": {"status": "off"}})
    assert s["trap"]["id"] == "p1"  # production peak failure preferred over the staging one
    assert s["revision"]["id"] == "p3" and s["rejected_first"]["id"] == "p2"
    assert s["ai_fail"][0]["id"] == "a1" and s["ai_pass"][0]["id"] == "a2"
    assert s["counts"] == {"screened": 5, "rejected": 3, "trials_passed": 2, "awaiting": 2, "recalled": 0}
    s = P.story({"plans": PLANS, "trials": [{"id": "t3", "plan_id": "p3", "status": "INCOMPLETE"}]})
    assert s["revision"] is None and [p["id"] for p in s["not_judged"]] == ["p3"]  # not judged is not a revision


def test_memory_moment_counts_only_failures_not_proposed_again():
    recalled = {"kind": "screening_rejection", "signature": f"cloud:{PROD}:e2-standard-2"}
    validated = {"kind": "validated_plan", "signature": f"cloud:{STG}:e2-standard-4"}
    s = P.story({"plans": PLANS[1:], "trials": TRIALS, "memory": {"status": "used", "applicable": [recalled, validated]}})
    assert s["trap"]["id"] == "p2"  # no production failure this run: the staging peak failure is shown
    assert s["recalled"] == [recalled] and s["not_repeated"] == [recalled]


def test_absent_moments_stay_absent():
    s = P.story({})
    assert s["trap"] is s["revision"] is s["ai_fail"] is s["ai_pass"] is None
    assert s["counts"]["screened"] == 0


def test_lost_categories_and_vcpu_points():
    result = {"baseline": {"by_category": {"premium_exceptions": {"accepted": 8, "total": 8}, "order_status": {"accepted": 8, "total": 8}}},
              "candidate": {"by_category": {"premium_exceptions": {"accepted": 4, "total": 8}, "order_status": {"accepted": 8, "total": 8}}}}
    assert P.lost_categories(result) == [{"category": "premium_exceptions", "baseline": 8, "candidate": 4, "total": 8}]
    pts = P.vcpu_points([{"observed_at": "t0", "cpu_percent": "80"}, {"observed_at": "t1", "cpu_percent": None}], "8")
    assert pts == [{"observed_at": "t0", "vcpu": 6.4}]
    assert P.pct("0.2912") == "29.1%"
