from pathlib import Path
import json
from scripts import run_bloodhound_baseline as ce
from scripts import neo_bloodhound_live as live
from scripts.neo_bloodhound import path_query
from src.engine.ranking.resolution_service import canonical_digest
OUT=Path(__file__).resolve().parent;OLD=Path('reports/generated/goodhound-evaluation-20261024-v1');PROJECT='neo-goodhound-20261024-adaptation-v2'
def put(n,o):(OUT/n).write_text(json.dumps(o,indent=2)+'\n')
assert ce.BLOODHOUND_URL=='http://127.0.0.1:48080'
for service,port,expected in [('bloodhound','8080',ce.BLOODHOUND_URL),('graph-db','7474',ce.NEO4J_URL.removesuffix('/db/neo4j/tx/commit'))]:
 published=ce.run_cmd(['docker','compose','--env-file',str(OLD/'compose.env'),'-f',str(live.COMPOSE),'-p',PROJECT,'port',service,port]).strip();assert expected=='http://'+published
secret=ce.get_admin_password(compose_file=live.COMPOSE,project_name=PROJECT);token=ce.login(secret);ce.wait_for_bloodhound_ready(token)
f=json.loads((OUT/'freeze.json').read_text());pairs=[(c['source_id'],c['goal_id']) for c in f['cells'][:2]]
nodecount=ce.query_neo4j('MATCH (n) WHERE n.objectid IS NOT NULL RETURN count(n) AS nodes')[0]['nodes'];assert nodecount==1391
edge=json.loads((OUT/'membership-points.json').read_text())[0]['edge'];params={'source':edge['source'],'target':'WINDOMAIN.LOCAL-S-1-5-32-544'}
match='MATCH (s {objectid:$source})-[r:MemberOf]->(t {objectid:$target})'
saved=live.parameter_query(match+' RETURN properties(r) AS props',params);assert len(saved)==1

def fingerprint():
 rows=ce.query_neo4j(live.INVENTORY_EDGES+', properties(r) AS props');return canonical_digest(sorted(rows,key=lambda x:json.dumps(x,sort_keys=True)))
def collect(phase):
 rows=[]
 for s,t in pairs:
  for enabled in (False,True):
   q=path_query(s,t,'host-compromise',enabled_users=enabled)
   result=live.bloodhound_query(q,token,s,t)
   allq=q.replace('shortestPath','allShortestPaths').replace('RETURN p;','RETURN [n IN nodes(p) | n.objectid] AS nodes, [r IN relationships(p) | type(r)] AS kinds;')
   allpaths=ce.query_neo4j(allq)
   rows.append({'source':s,'target':t,'enabled_users':enabled,'result':result,'all_shortest_query':allq,'all_shortest_paths':allpaths})
 put(f'ce-{phase}.json',rows);return rows
original=fingerprint();before=collect('before');put('ce-restore-journal.json',{**params,'kind':'MemberOf','props':saved[0]['props'],'before_digest':original,'project':PROJECT})
try:
 live.parameter_query(match+' DELETE r',params)
 after=collect('after')
finally:
 live.parameter_query('MATCH (s {objectid:$source}),(t {objectid:$target}) MERGE (s)-[r:MemberOf]->(t) SET r=$props',{**params,'props':saved[0]['props']})
 restored=fingerprint();assert restored==original
put('ce-results.json',{'project':PROJECT,'nodecount':nodecount,'relationship_digest_before':original,'relationship_digest_restored':restored,'restore_verified':True,'before':[{'target':r['target'],'enabled_users':r['enabled_users'],'http_status':r['result']['http_status'],'all_shortest_count':len(r['all_shortest_paths'])} for r in before],'after':[{'target':r['target'],'enabled_users':r['enabled_users'],'http_status':r['result']['http_status'],'empty_confirmed':r['result'].get('empty_confirmed',False),'all_shortest_count':len(r['all_shortest_paths'])} for r in after],'C_comparison':'not claimed: CE graph hops and neo semantic programs are different workloads'})
print((OUT/'ce-results.json').read_text())
