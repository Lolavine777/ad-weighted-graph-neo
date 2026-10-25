from pathlib import Path
from copy import deepcopy
import json
from scripts.neo_import import prepare_records
from scripts.neo_remediation import rebuild,verify_result
from src.parser import ManifestRawDataLoader
from src.parser.adapters import adapt_bloodhound_v3_records
from src.parser.cli import load_time_policy
from src.parser.snapshot_facts import serialize_snapshot
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.query_cli import wire
from src.engine.ranking.resolution_service import canonical_digest
OUT=Path(__file__).resolve().parent;OLD=Path('reports/generated/goodhound-evaluation-20261024-v1')
def put(n,o):(OUT/n).write_text(json.dumps(o,indent=2)+'\n')
g=EngineGraph.from_snapshot((OLD/'import-adaptation-v2/snapshot.json').read_text());loader=ManifestRawDataLoader(OLD/'adapted-manifest-v2.json',time_policy=load_time_policy(OLD/'time-policy.json'))
records,_=prepare_records(list(loader.load(OLD/'adapted-input-v2')),'20211017151337');records=adapt_bloodhound_v3_records(records)
baseline=rebuild(records,g.metadata)
assert baseline.to_canonical()==g.to_canonical() and wire(baseline.snapshot_facts.facts)==wire(g.snapshot_facts.facts)
original=canonical_digest(wire(records));edited=deepcopy(records);edge=json.loads((OUT/'membership-points.json').read_text())[0]['edge'];removed=[]
for r in edited:
 if r.data['ObjectIdentifier']==edge['target']:
  members=r.data.get('Members',[])
  removed.extend([m for m in members if m.get('MemberId',m.get('ObjectIdentifier'))==edge['source']])
  r.data['Members']=[m for m in members if m not in removed]
assert len(removed)==1,removed
after=rebuild(edited,g.metadata);be={e['id']:e for e in g.edges()};ae={e['id']:e for e in after.edges()}
assert edge['id'] not in ae
assert canonical_digest(wire(records))==original
(OUT/'rebuilt-after-snapshot.json').write_text(serialize_snapshot(after.to_canonical(),after.snapshot_facts))
put('rebuild-audit.json',{'baseline_reproduced_exactly':True,'raw_records_unchanged':True,'removed_member_observations':removed,'removed_edges':[be[k] for k in sorted(be.keys()-ae.keys())],'added_edges':[ae[k] for k in sorted(ae.keys()-be.keys())],'changed_edges':[k for k in be.keys()&ae.keys() if be[k]!=ae[k]],'input_records_digest':original,'after_graph_digest':canonical_digest(after.to_canonical()),'semantics':'counterfactual copied records; full parser/facts/inference rebuild; fresh declared foothold and token refresh, no live action'})
rows=[]
for i,c in enumerate(json.loads((OUT/'freeze.json').read_text())['cells']):
 result=run_attack_query(c['query'],after);row,ev=verify_result(result,after);row.update(target=c['goal_id'],strategy=c['query']['search_order']);rows.append(row);put(f'rebuilt-after-cell-{i}-evidence.json',ev);put('rebuilt-after-results.json',rows);print(json.dumps(row),flush=True)
