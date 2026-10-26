// Port of greenops/ui/present.py:story — selects the moments one investigation can tell. Each picker returns null
// when the run did not produce that moment, so the page says what is missing instead of inventing it.
import type { InvestigationData, MemoryItem, PlanSummary, TrialSummary } from "./api";
import { checkOf, environmentOf } from "./format";

export interface Story {
  trap: PlanSummary | null;
  revision: PlanSummary | null;
  rejectedFirst: PlanSummary | null;
  notJudged: PlanSummary[];
  aiFail: [PlanSummary, TrialSummary] | null;
  aiPass: [PlanSummary, TrialSummary] | null;
  memoryStatus: string | undefined;
  recalled: MemoryItem[];
  notRepeated: MemoryItem[];
  historical: MemoryItem[];
  awaiting: PlanSummary[];
  counts: { screened: number; rejected: number; trialsPassed: number; awaiting: number; recalled: number };
}

export function buildStory(d: InvestigationData): Story {
  const plans = d.plans ?? [];
  const trialOf = new Map<string, TrialSummary>();
  for (const t of d.trials ?? []) if (t.plan_id) trialOf.set(t.plan_id, t);
  const cloud = plans.filter((p) => p.path === "cloud");
  const peakFail = cloud.filter((p) => checkOf(p, "CHK-CPU-PEAK")?.status === "FAIL");
  const trap = peakFail.find((p) => environmentOf(p.target_key).startsWith("production")) ?? peakFail[0] ?? null;
  const revision = cloud.find((p) => trialOf.get(p.id)?.status === "PASSED") ?? null;
  const rejectedFirst = revision ? cloud.find((p) => p.target_key === revision.target_key && p.status === "REJECTED") ?? null : null;
  const aiTrials = plans.filter((p) => p.path === "ai" && trialOf.has(p.id)).map((p) => [p, trialOf.get(p.id)!] as [PlanSummary, TrialSummary]);
  const mem = d.memory ?? {};
  const proposed = new Set(plans.map((p) => p.screening?.signature));
  const recalled = (mem.applicable ?? []).filter((m) => m.kind === "screening_rejection" || m.kind === "rejected_trial");
  return {
    trap,
    revision,
    rejectedFirst,
    notJudged: cloud.filter((p) => trialOf.get(p.id)?.status === "INCOMPLETE"),
    aiFail: aiTrials.find(([, t]) => t.status === "FAILED") ?? null,
    aiPass: aiTrials.find(([, t]) => t.status === "PASSED") ?? null,
    memoryStatus: mem.status,
    recalled,
    notRepeated: recalled.filter((m) => !proposed.has(m.signature)),
    historical: mem.historical ?? [],
    awaiting: plans.filter((p) => p.status === "AWAITING_APPROVAL"),
    counts: {
      screened: plans.length,
      rejected: plans.filter((p) => p.status === "REJECTED").length,
      trialsPassed: [...trialOf.values()].filter((t) => t.status === "PASSED").length,
      awaiting: plans.filter((p) => p.status === "AWAITING_APPROVAL").length,
      recalled: recalled.length,
    },
  };
}

export const STAGES: { id: string; label: string; sub: string }[] = [
  { id: "SCOPE", label: "Scope & evidence", sub: "Coordinator scopes; investigator reads federated evidence and recalls memory" },
  { id: "PROPOSE", label: "Propose · screen · critique", sub: "Optimizer proposes ≤3 per path; code screens; critic demands evidence or revisions" },
  { id: "TRIALS", label: "Matched trials", sub: "Survivors run on sandbox fixtures under identical load or the locked dev suite" },
  { id: "DONE", label: "Decision", sub: "Outcome committed; awaiting human review, or a justified no-change" },
];
