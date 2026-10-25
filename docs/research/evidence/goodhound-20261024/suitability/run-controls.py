from pathlib import Path
import json,hashlib,subprocess,time
from scripts.neo_domain import build_survey,scenario_profile,techniques_for
from scripts.neo_remediation import verify_result
from src.engine.graph import EngineGraph
from src.engine.batch import _query_for_cell,execution_source_pins
from src.engine.query import run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.effort_profiles import load_effort_profile
from src.engine.ranking.resolution_service import canonical_digest
OUT=Path(__file__).resolve().parent
OLD=Path('reports/generated/goodhound-evaluation-20261024-v1')
def put(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=OLD/'import-adaptation-v2/snapshot.json';g=EngineGraph.from_snapshot(p.read_text());nodes={n['id']:n for n in g.nodes()};s=next(n['id'] for n in nodes.values() if n.get('label','').startswith('BENNY_SNIDER'))
 _,r=build_survey(g,max_paths=10,max_steps=12,max_expansions=4096,scenario='host-compromise',source_ids=[s])
 cells=[]
 for strategy in ('neo_guided','neo_refine'):
  for goal in r.resolve_target_goals():
   q,error=_query_for_cell(r,r.sources[0],goal,g,techniques_for('host-compromise'),r.common_budget,scenario_policy=scenario_profile(g,'host-compromise'),effort_profile=load_effort_profile('neo-c-v1'),search_order=strategy)
   assert error is None,error
   cells.append({'source_id':s,'goal_id':goal.target_node_id,'query':q})
 freeze={'version':'goodhound-positive-control/1','revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'classification':'outcome-directed public-data positive control, not blind holdout or random cohort','selection':'sole non-DA-member User/Computer in supported structural predecessor closure of DA; already a member of built-in Administrators, so not an unprivileged foothold','expected':'conditional witness to both DA/EA through existing membership and directory ACL capability; expected recipe C=2+1=3, not a global minimum claim','independent_recipe_C':{'grant_new_object_right':2,'genericall_add_member':1,'propagate_group_entitlement':0},'scenario':'unchanged neo-host-session-v1; usable source identity and policy assumptions are declared, not live validation','snapshot_sha256':sha(p),'original_results_sha256':sha(Path('reports/neo/goodhound-evaluation-results.json')),'original_matrix_sha256':{x:sha(OLD/x/'cells.jsonl') for x in ('native-guided','native-refine')},'source_pins':execution_source_pins(),'effort_profile':load_effort_profile('neo-c-v1'),'cells':cells,'remediation_plan':'use existing observed-support inventory, select removal of the source membership into built-in Administrators if eligible, replay and independently rediscover from same fresh foothold; preserve bypass/cap/Unknown'}
 assert not (OUT/'freeze.json').exists()
 put('freeze.json',freeze)
 rows=[]
 for i,c in enumerate(cells):
  t=time.perf_counter();result=run_attack_query(c['query'],g);row,ev=verify_result(result,g)
  row.update(source=c['source_id'],target=c['goal_id'],strategy=c['query']['search_order'],seconds=time.perf_counter()-t,query_sha256=canonical_digest(c['query']))
  put(f'cell-{i}-evidence.json',ev);rows.append(row);put('positive-controls.json',{'freeze_sha256':sha(OUT/'freeze.json'),'rows':rows});print(json.dumps(row),flush=True)
 assert sha(Path('reports/neo/goodhound-evaluation-results.json'))==freeze['original_results_sha256']
if __name__=='__main__':main()
