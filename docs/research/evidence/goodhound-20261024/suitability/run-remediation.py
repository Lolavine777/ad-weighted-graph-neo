from pathlib import Path
from dataclasses import asdict
import json,time
from src.engine.graph import EngineGraph
from src.engine.remediation import prepare_baseline,request_for_baseline
from src.engine.remediation_runner import inventory_interventions,run_remediation,verify_package
from scripts.neo_decision import membership_points
from scripts.defender_brief import remediation_outcome
OUT=Path(__file__).resolve().parent;OLD=Path('reports/generated/goodhound-evaluation-20261024-v1')
def put(n,o):(OUT/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+'\n')
def main():
 g=EngineGraph.from_snapshot((OLD/'import-adaptation-v2/snapshot.json').read_text());freeze=json.loads((OUT/'freeze.json').read_text());before=g.to_canonical()
 rows=[]
 for i,c in enumerate(freeze['cells'][:2]):
  ev=json.loads((OUT/f'cell-{i}-evidence.json').read_text());rows.append({'source':c['source_id'],'target':c['goal_id'],'programs':ev['programs'],'paths':[w['path'] for w in ev['witnesses']]})
 privileged={n['id'] for n in g.nodes() if n['kind']=='Group' and (n['id'].endswith(('-512','-519',':S-1-5-32-544')))}
 points=membership_points(rows,g,privileged);put('membership-points.json',points);assert points,'No eligible membership point'
 selected=points[0]['edge'];assert selected['source']==freeze['cells'][0]['source_id'] and selected['target'].endswith(':S-1-5-32-544')
 outcomes=[];candidate=None
 for strategy in ('neo_guided','neo_refine'):
  cells=[c for c in freeze['cells'] if c['query']['search_order']==strategy]
  baseline=prepare_baseline(g,cells,run_id=f'goodhound-control-{strategy}');put(f'{strategy}-baseline.json',asdict(baseline));print(strategy,'baseline ready',flush=True)
  if candidate is None:
   inv=inventory_interventions(g,baseline);put('intervention-inventory.json',inv)
   candidate=next(c for c in inv['candidates'] if c['status']=='supported' and c['catalog_entry_id']=='group-membership' and any(e.get('edge_id')==selected['id'] for e in c['technical_edits']))
   put('intervention.json',candidate)
  request=request_for_baseline(baseline,candidate['technical_edits'],request_id=f'goodhound-control-remove-membership-{strategy}');put(f'{strategy}-request.json',request)
  package=run_remediation(request,g,baseline);put(f'{strategy}-package.json',package)
  verify_package(package,g)
  outcome={'strategy':strategy,'independent_verifier_passed':True,'outcome':remediation_outcome(g,package),'cells':package['report']['cells']};outcomes.append(outcome);put('remediation-results.json',outcomes);print(json.dumps(outcome),flush=True)
 assert before==g.to_canonical(),'Baseline mutated'
if __name__=='__main__':main()
