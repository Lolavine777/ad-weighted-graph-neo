from pathlib import Path
import json
from src.engine.graph import EngineGraph
from src.engine.query import run_attack_query
from src.engine.top_k import effort_programs
from src.engine.ranking.resolution_service import canonical_digest
OUT=Path(__file__).resolve().parent;OLD=Path('reports/generated/goodhound-evaluation-20261024-v1')
g=EngineGraph.from_snapshot((OLD/'import-adaptation-v2/snapshot.json').read_text());f=json.loads((OUT/'freeze.json').read_text());rows=[]
for i,c in enumerate(f['cells']):
 result=run_attack_query(c['query'],g);programs,_=effort_programs(result);old=json.loads((OUT/f'cell-{i}-evidence.json').read_text())
 assert [(p['program_id'],p['effort']) for p in programs]==[(p['program_id'],p['effort']) for p in old['programs']]
 top=result.top_k_result;costs=[p['effort'] for p in top['programs']]
 assert costs==sorted(costs) and costs==sorted(p['effort'] for p in programs)[:3]
 expected=f['independent_recipe_C'];best=old['witnesses'][0]['path']['transition_history'];techniques=[s['result']['request']['technique_id'] for s in best]
 assert techniques==['propagate_group_entitlement','grant_new_object_right','genericall_add_member','propagate_group_entitlement']
 assert sum(expected[t] for t in techniques)==min(p['effort'] for p in programs)==3
 rows.append({'strategy':c['query']['search_order'],'target':c['goal_id'],'candidate_C': [p['effort'] for p in programs],'top_k':top,'native_candidate_set_reproduced':True,'independent_expected_recipe_C':3,'ranking_correct_within_returned_candidates':True,'program_set_sha256':canonical_digest([(p['program_id'],p['effort']) for p in programs])})
 (OUT/'ranking-checks.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps({'strategy':c['query']['search_order'],'target':c['goal_id'],'top3':costs}),flush=True)
