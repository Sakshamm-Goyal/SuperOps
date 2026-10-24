import json
import httpx
from tests.unit.test_adapters_contract import settings, fake_zetaris
from greenops.adapters.evidence import ZetarisClient
http,_=fake_zetaris(205)
r=ZetarisClient(settings(),http=http).query('pagination_probe',{},max_rows=150)
print(json.dumps({'case':'row_budget','requested_max':150,'returned':len(r.rows),'completeness':r.completeness}))
log=[]
def handler(req):
 log.append(req.url.path)
 if '/close/' in req.url.path: return httpx.Response(200)
 return httpx.Response(200,json={'pageNumber':1 if req.url.path.endswith('/start') else 2,'totalCount':2,'totalPages':2,'queryToken':'qt','records':[{'probe_id':1}]})
r=ZetarisClient(settings(),http=httpx.Client(base_url='https://zetaris.invalid',transport=httpx.MockTransport(handler))).query('pagination_probe',{})
print(json.dumps({'case':'duplicate_pages','rows':r.rows,'completeness':r.completeness}))
log=[]
def malformed(req):
 log.append(req.url.path)
 return httpx.Response(200,json={'pageNumber':1,'totalCount':1,'totalPages':1,'queryToken':'qt','records':[123]})
try: ZetarisClient(settings(),http=httpx.Client(base_url='https://zetaris.invalid',transport=httpx.MockTransport(malformed))).query('pagination_probe',{})
except Exception as e: print(json.dumps({'case':'malformed_initial_record','error':type(e).__name__,'closed':any('/close/' in p for p in log)}))
