from pathlib import Path
import json,os,traceback
from types import SimpleNamespace
from scripts import run_bloodhound_baseline as ce
from scripts import neo_bloodhound_live as live
from src.engine.graph import EngineGraph
out=Path('reports/generated/goodhound-evaluation-20261024-v1');project='neo-goodhound-20261024-adaptation-v2'
assert ce.BLOODHOUND_URL=='http://127.0.0.1:48080'
assert ce.NEO4J_URL=='http://127.0.0.1:48474/db/neo4j/tx/commit'
password=ce.get_admin_password(compose_file=live.COMPOSE,project_name=project)
token=ce.login(password); ce.wait_for_bloodhound_ready(token)
def configuration(raw,manifest,dataset):
    m=json.loads(manifest.read_text())
    return {'dataset_id':dataset,'snapshot_id':m['snapshot_id'],'raw_root':raw,'manifest_path':manifest,'file_pattern':'*.json','expected_files':6,'archive_name':'20211017151337_BloodHound.zip','archive_sha256':json.loads((out/'input-metadata.json').read_text())['archive_sha256'],'collector':'SharpHound v3; version unknown'}
original=configuration(Path('data/raw/goodhound-detectionlab-c2d8915'),out/'manifest.json','goodhound-original')
ce.SNAPSHOTS['goodhound-original']=original
try:
    result=ce.ingest_snapshot('goodhound-original',original,token)
    (out/'ce-original-schema3-result.json').write_text(json.dumps({'status':'success','result':result},indent=2)+'\n')
except Exception as exc:
    (out/'ce-original-schema3-result.json').write_text(json.dumps({'status':'input_error','error':str(exc)},indent=2)+'\n')
count=ce.query_neo4j('MATCH (n) WHERE NOT n:MigrationData RETURN count(n) AS nodes;')[0]['nodes']
assert count==0,('Original import populated graph; use a separate fresh project for adapted import',count)
adapted=configuration(out/'ce-schema6-inputs',out/'ce-schema6-manifest.json','goodhound-adaptation-v2-ce6')
ce.SNAPSHOTS['goodhound']=adapted
result=ce.ingest_snapshot('goodhound',adapted,token)
(out/'ce-adaptation-v2-ingest.json').write_text(json.dumps(result,indent=2)+'\n')
snapshot=out/'import-adaptation-v2/snapshot.json'; graph=EngineGraph.from_snapshot(snapshot.read_text());pack=json.loads((out/'comparison-pack.json').read_text())
folder=out/'ce-live';folder.mkdir(exist_ok=False)
collected=live.collect(SimpleNamespace(dataset='goodhound',output_dir=folder),pack,graph,token)
(out/'ce-collection-summary.json').write_text(json.dumps(collected,indent=2)+'\n')
inventory=json.loads((folder/'inventory.json').read_text())
# Existing parity helper uses the historical wraith selector for HOST_EDGES.
parity=live.parity(graph,inventory,'wraith')
(folder/'parity-host.json').write_text(json.dumps({'dataset':'goodhound','helper_edge_scope_selector':'wraith selects HOST_EDGES only; data is GoodHound','result':parity},indent=2)+'\n')
print(json.dumps({'collection':collected,'parity_counts':parity['counts']},indent=2))
