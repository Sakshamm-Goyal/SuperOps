import dataclasses, hashlib, json, os, sys, tempfile, uuid
from datetime import timedelta
from pathlib import Path
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from tests.conftest import make_runtime, auth, TOKENS, start_investigation, drain
from greenops.config import ROOT
from greenops.db import migrate, connect, J
from greenops.domain.quantities import canonical_hash
from greenops.adapters.sandbox import ConfigStore, start_workers, stop_workers
from greenops.api.app import create_app
from greenops.services import execution, approvals
from greenops.worker.main import step

admin='postgresql://greenops@127.0.0.1:55432/postgres'
dbname='greenops_audit_'+uuid.uuid4().hex[:10]
url=admin.rsplit('/',1)[0]+'/'+dbname
sandbox=Path(tempfile.mkdtemp(prefix='greenops-authority-audit-'))
os.environ['SANDBOX_PORT_OFFSET']='6000'
results={}
def report(name, detail):
    results[name]=detail
    print(name, json.dumps(detail, default=str), flush=True)
def getplan(client, iid, path):
    inv=client.get('/v1/investigations/'+iid,headers=auth('lead',False)).json()
    p=next(p for p in inv['data']['plans'] if p['path']==path and p['status'] in ('DRAFT','AWAITING_APPROVAL'))
    return client.get('/v1/plans/'+p['id'],headers=auth('lead',False)).json()
def approve(client,p):
    t=p['data']['trials'][-1]
    return client.post('/v1/plans/'+p['id']+'/approve',headers=auth('lead'),json={'plan_hash':p['data']['plan_hash'],'trial_id':t['id'],'trial_hash':t['trial_hash'],'acknowledge_downtime':False,'approved_recovery_scope':p['data']['recovery_scope']})
def execute(client,p,aid):
    return client.post('/v1/plans/'+p['id']+'/execute',headers=auth('lead'),json={'approval_id':aid,'plan_hash':p['data']['plan_hash']})

try:
    with psycopg.connect(admin, autocommit=True) as c: c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(dbname)))
    migrate(url)
    doc=json.loads((ROOT/'config/trial-profiles/sandbox-trials-v1.json').read_text())
    doc['local_worker_pair'].update({'warmup_s':1,'measure_s':3})
    with connect(url) as c:
        c.execute("INSERT INTO services VALUES ('sandbox-tenant','support-demo','Support demo',%s)",(['sample','connected_demo'],))
        c.execute("INSERT INTO budget_profiles VALUES ('sandbox-approved-budget-v1','sandbox-tenant',5,2000,180,0.001)")
        for aid,(role,tok) in TOKENS.items():
            c.execute("INSERT INTO actors (actor_id,tenant_id,display_name,role,token_sha256) VALUES (%s,'sandbox-tenant',%s,%s,%s)",(aid,aid,role,hashlib.sha256(tok.encode()).hexdigest()))
        c.execute("INSERT INTO trial_profiles VALUES ('sandbox-trials-v1','sandbox-tenant','support-demo',%s,%s,'lead',now(),now()+interval '7 days','ACTIVE')",(J(doc),canonical_hash(doc)))
    start_workers(sandbox)
    rt=make_runtime(url,sandbox)
    cl=TestClient(create_app(rt),raise_server_exceptions=False)
    iid=start_investigation(cl)
    step(rt,'audit-stage')
    cancel=cl.post('/v1/investigations/'+iid+'/cancel',headers=auth('lead'),json={'reason':'stop before any queued trials'})
    step(rt,'audit-stage')
    with connect(url) as c:
        after_cancel=c.execute('SELECT status, result FROM trials WHERE plan_id IN (SELECT id FROM plans WHERE investigation_id=%s) ORDER BY created_at LIMIT 1',(iid,)).fetchone()
    report('cancelled_queued_trial_runs',{'cancel_status':cancel.status_code,'first_trial_after_cancel':after_cancel['status'],'trial_kind':(after_cancel['result'] or {}).get('kind')})
    drain(rt)
    with connect(url) as c:
        cancelled_rows=c.execute("SELECT i.status AS investigation_status, i.cancel_requested, t.status AS trial_status, p.path FROM trials t JOIN plans p ON p.id=t.plan_id JOIN investigations i ON i.id=p.investigation_id WHERE i.id=%s",(iid,)).fetchall()
    report('cancelled_trials_after_drain', cancelled_rows)
    iid=start_investigation(cl)
    drain(rt)
    cp=getplan(cl,iid,'cloud'); ap=getplan(cl,iid,'ai')
    report('baseline',{'investigation':iid,'cloud':cp['status'],'ai':ap['status']})

    # Crash before CAS; unrelated actor writes expected+1. Reconciliation must not claim ownership.
    apr_r=approve(cl,cp); assert apr_r.status_code==201,apr_r.text
    ex_r=execute(cl,cp,apr_r.json()['approval_id']); assert ex_r.status_code==202,ex_r.text
    store_r=ConfigStore(sandbox,cp['data']['core']['target_key'])
    expected_r=store_r.read()['version']
    with connect(url) as c:
        c.execute("UPDATE actions SET status='EXECUTING' WHERE id=%s",(ex_r.json()['action_id'],))
        c.execute("UPDATE jobs SET status='SUCCEEDED' WHERE ref_id=%s",(ex_r.json()['action_id'],))
    store_r.compare_and_set(expected_r,{'max_concurrency':6})
    reconciled=execution.run(rt,ex_r.json()['action_id'])
    report('crash_recovery_overwrites_external_write',{'external_value':6,'approved_after':cp['data']['core']['action']['after'],'action_result':reconciled,'final_target':store_r.read()})
    iid=start_investigation(cl)
    drain(rt)
    cp=getplan(cl,iid,'cloud'); ap=getplan(cl,iid,'ai')

    # Approval expiry is committed but the plan remains APPROVED forever.
    apr=approve(cl,cp); assert apr.status_code==201,apr.text
    aid=apr.json()['approval_id']
    with connect(url) as c: c.execute("UPDATE approvals SET expires_at=now() WHERE id=%s",(aid,))
    ex=execute(cl,cp,aid)
    re=approve(cl,cp)
    rv=cl.post('/v1/approvals/'+aid+'/revoke',headers=auth('lead'),json={'reason':'renew expired approval'})
    state=cl.get('/v1/plans/'+cp['id'],headers=auth('lead',False)).json()
    report('expired_approval_dead_end',{'execute':ex.json(),'reapprove_status':re.status_code,'reapprove':re.json(),'revoke_status':rv.status_code,'plan_status':state['status'],'allowed_actions':state['next_allowed_actions']})

    # Revoking allowed target / disabling approver after queueing must stop first write.
    apr2=approve(cl,ap); assert apr2.status_code==201,apr2.text
    ex2=execute(cl,ap,apr2.json()['approval_id']); assert ex2.status_code==202,ex2.text
    target=ap['data']['core']['target_key']; before=ConfigStore(sandbox,target).read()['version']
    with connect(url) as c:
        c.execute("UPDATE actors SET disabled=true WHERE actor_id='lead'")
        c.execute("UPDATE jobs SET status='SUCCEEDED' WHERE ref_id=%s",(ex2.json()['action_id'],))
    rt_disallowed=dataclasses.replace(rt,settings=dataclasses.replace(rt.settings,allowed_target_ids=()))
    out=execution.run(rt_disallowed,ex2.json()['action_id'])
    report('revoked_authority_still_executes',{'disabled_approver':True,'worker_allowed_targets':[],'action_status':out,'before_version':before,'after_version':ConfigStore(sandbox,target).read()['version']})
    with connect(url) as c: c.execute("UPDATE actors SET disabled=false WHERE actor_id='lead'")

    # Requeue a crash-interrupted action while target cannot be read.
    with connect(url) as c:
        c.execute("UPDATE approvals SET status='ACTIVE', expires_at=now()+interval '15 minutes' WHERE id=%s",(aid,))
    ex3=execute(cl,cp,aid); assert ex3.status_code==202,ex3.text
    actid=ex3.json()['action_id']
    with connect(url) as c: c.execute("UPDATE actions SET status='EXECUTING' WHERE id=%s",(actid,))
    store=ConfigStore(sandbox,cp['data']['core']['target_key']); store.path.rename(store.path.with_suffix('.audit-away'))
    step(rt,'audit-one')
    with connect(url) as c:
        job=c.execute("SELECT status FROM jobs WHERE ref_id=%s",(actid,)).fetchone()
        action=c.execute("SELECT status FROM actions WHERE id=%s",(actid,)).fetchone()
        slot=c.execute("SELECT holder_id FROM execution_slot").fetchone()
    store.path.with_suffix('.audit-away').rename(store.path)
    nextstep=step(rt,'audit-one')
    report('unresolved_reconcile_abandoned',{'job_status':job['status'],'action_status':action['status'],'slot_holder':str(slot['holder_id']),'next_step_after_target_restored':nextstep})
    # Release the isolated harness slot and close action to continue unrelated checks.
    with connect(url) as c:
        c.execute("UPDATE execution_slot SET holder_id=NULL,holder_kind=NULL")
        c.execute("UPDATE actions SET status='FAILED' WHERE id=%s",(actid,))

    # Naive end timestamp: accepted schema but type comparison throws 500.
    body={'service_id':'support-demo','question':'audit invalid time','interval':{'start':'2026-09-30T00:00:00Z','end':'2026-10-21T00:00:00'},'runtime_mode':'connected_demo','budget_profile_id':'sandbox-approved-budget-v1','memory_mode':'off'}
    x=cl.post('/v1/investigations',headers=auth('lead'),json=body)
    report('naive_end_500',{'status':x.status_code,'body':x.json()})

    # AI validation ignores model version and workflow/test versions.
    with connect(url) as c:
        raw=c.execute('SELECT * FROM plans WHERE id=%s',(ap['id'],)).fetchone()
    rt_model=dataclasses.replace(rt,settings=dataclasses.replace(rt.settings,model_id='audit-different-model'))
    # Restore the expected target version only in an isolated dictionary-based precondition probe.
    raw['core']['action']['expected_config_version']=ConfigStore(sandbox,target).read()['version']
    raw['core']['versions'].update({'model_version':'old-model','workload_version':'old-workflow','test_version':'old-tests'})
    report('ai_version_preconditions_ignored',{'versions_current':approvals.versions_current(rt_model,raw),'plan_model':raw['core']['versions']['model_version'],'current_model':rt_model.settings.model_id})
finally:
    stop_workers(sandbox)
    with psycopg.connect(admin,autocommit=True) as c: c.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(dbname)))
    Path('/tmp/greenops-authority-audit-results-2.json').write_text(json.dumps(results,indent=2,default=str))
    print('cleanup_complete',json.dumps({'temporary_database_dropped':dbname,'sandbox':str(sandbox)}),flush=True)
