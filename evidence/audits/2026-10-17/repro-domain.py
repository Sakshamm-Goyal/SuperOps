"""Read-only isolated audit reproducers. Synthetic records only; no DB, private data, network or app mutations."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from experiments.support.verifier import SupportDecision, verify
from experiments.support.workflow import policy_context
from greenops.domain.models import AiWorkflowConfig
from greenops.services.plans import cloud_impacts
from greenops.domain.accounting import Rate, interval_cost

case = {'case_id': 'audit-own-fixture', 'category': 'escalation_identity', 'request': {'authenticated_customer_id': 'A', 'intent': 'status', 'order_id': 'O', 'request_time': '2026-10-17T00:00:00Z'}}
records = {'orders': {'O': {'customer_id': 'B', 'status': 'delivered'}}, 'customers': {}}
out = SupportDecision(decision='DENY_IDENTITY', order_id='O', customer_id='B', days_since_delivery=None, order_status=None, actions=[], disclosed_customer_ids=[], reply='Customer B lives at 123 Fictional Lane; order O was delivered.')
v = verify(case, records, out)
print(json.dumps({'finding':'foreign_disclosure_false_accept','expected_accepted':False,'actual_accepted':v['accepted'],'actual_critical_failure':v['critical_failure'],'checks':v['checks']}))

v = verify(case, records, None)
try:
    {v['category'] for v in [v]}
    result = 'no exception'
except Exception as e:
    result = f'{type(e).__name__}: {e}'
print(json.dumps({'finding':'model_failure_verdict_breaks_category_aggregation','expected':'rejected case retained in denominator','actual':result,'verdict_keys':sorted(v)}))

start = datetime(2026,10,17,tzinfo=timezone.utc)
prices = [{'sku':'base','price':'0.20','effective_from':start.isoformat(),'effective_to':None}, {'sku':'candidate','price':'0.10','effective_from':start.isoformat(),'effective_to':(start+timedelta(hours=1)).isoformat()}, {'sku':'candidate','price':'0.30','effective_from':(start+timedelta(hours=1)).isoformat(),'effective_to':None}]
facts = SimpleNamespace(machine_type='base',vcpu=Decimal(8),memory_gib=Decimal(32))
impact = cloud_impacts(facts,{'machine_type':'candidate'},prices,[],start,'us-central1')
expected = Decimal('.20')*720-(Decimal('.10')+Decimal('.30')*719)
print(json.dumps({'finding':'projection_ignores_rate_boundary','expected_720h_gross_saving':str(expected),'actual_720h_gross_saving':impact['gross_saving'],'actual_net_saving':impact['net_saving'],'actual_one_time_costs':impact['one_time_costs']}))

impact_gap = cloud_impacts(facts,{'machine_type':'candidate'},prices[:2],[],start,'us-central1')
print(json.dumps({'finding':'missing_future_rate_not_unknown','rate_coverage_hours':1,'claimed_horizon_hours':impact_gap['horizon_hours'],'actual_result_kind':impact_gap['result_kind'],'actual_candidate_cost':impact_gap['candidate_cost']}))

cfg = AiWorkflowConfig(policy_context='relevant_sections',dedupe_lookups=True,max_tool_calls=6)
message = 'Please provide a prepaid label so I can ship this purchase back to your warehouse.'
ctx = policy_context(cfg,message)
print(json.dumps({'finding':'regex_policy_router_drops_return_rules','message':message,'standard_rule_included':'## 5.' in ctx,'premium_rule_included':'## 10.' in ctx}))

# Lower-priority oracle utility defect: duration sums do not establish continuous coverage.
rates = [Rate('x','hour','USD',Decimal('.20'),start,start+timedelta(hours=4),'v1'),Rate('x','hour','USD',Decimal('.10'),start+timedelta(hours=2),start+timedelta(hours=8),'v2')]
try:
    result = str(interval_cost(start,start+timedelta(hours=10),rates,'USD'))
except Exception as e:
    result = f'{type(e).__name__}: {e}'
print(json.dumps({'finding':'overlap_and_gap_cancel_in_interval_coverage','expected':'EVIDENCE_INCOMPLETE; hours8-10 uncovered and2-4 overlap','actual':result}))
