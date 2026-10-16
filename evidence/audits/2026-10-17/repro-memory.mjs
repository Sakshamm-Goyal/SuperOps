import fs from 'node:fs';
import path from 'node:path';
import {tempDataDir,startSidecar,rememberBody,recallBody} from '../../../memory-sidecar/test/helpers.ts';
const dir=tempDataDir();
let sc=await startSidecar({HMEM_DATA_DIR:dir,EMBEDDING_MODE:'hash_conformance'});
try {
 const body=rememberBody();
 const first=await sc.req('POST','/memory/remember',body);
 await sc.stop();
 const sf=path.join(dir,'state.json');
 const state=JSON.parse(fs.readFileSync(sf,'utf8'));state.records=[];fs.writeFileSync(sf,JSON.stringify(state));
 sc=await startSidecar({HMEM_DATA_DIR:dir,EMBEDDING_MODE:'hash_conformance'});
 const health=await sc.req('GET','/health');
 const dup=await sc.req('POST','/memory/remember',body);
 const recall=await sc.req('POST','/memory/recall',recallBody());
 console.log(JSON.stringify({case:'missing_memory_duplicate_ack',first:first.status,health:health.body.status,missing:health.body.store.missing_engine_records,duplicate_status:dup.status,persisted:dup.body.persisted,remembered_items:recall.body.items.length}));
} finally {await sc.stop();fs.rmSync(dir,{recursive:true,force:true});}
