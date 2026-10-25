from pathlib import Path
import sys,json,subprocess,copy,hashlib,socket
from scripts.neo_bloodhound import prepare_dataset, BUDGET
from scripts.convert_seamless_ce import convert_records,validate_conservation,encoded
from src.engine.graph import EngineGraph
out=Path('reports/generated/goodhound-evaluation-20261024-v1'); snapshot=out/'import-adaptation-v2/snapshot.json'
graph=EngineGraph.from_snapshot(snapshot.read_text())
pack=prepare_dataset(graph,snapshot,'host-compromise',out/'native-guided')
assert BUDGET=={'max_paths':10,'max_steps':12,'max_expansions':4096}
assert len(pack['pairs'])==10,pack['pairs']
(out/'comparison-pack.json').write_text(json.dumps({'datasets':{'goodhound':pack}},indent=2)+'\n')
raw={}; files={}
for f in (out/'adapted-input-v2').glob('*.json'):
    o=json.loads(f.read_text(encoding='utf-8-sig'));kind=o['meta']['type'];raw[kind]=o[kind];files[kind]=(f,o['meta'])
converted=convert_records(raw)
conservation=validate_conservation(raw,converted)
ceinputs=out/'ce-schema6-inputs';ceinputs.mkdir(exist_ok=False)
for kind,rows in converted.items():
    f,meta=files[kind]
    (ceinputs/f.name).write_bytes(encoded({'data':rows,'meta':{**meta,'version':6}}))
(out/'ce-conversion-audit.json').write_text(json.dumps({'method':'existing scripts.convert_seamless_ce.convert_records + validate_conservation, applied to GoodHound adaptation-v2','records_retained':sum(map(len,raw.values())),'conservation':conservation},indent=2)+'\n')
ports=(48080,48474,48687)
for p in ports:
    with socket.socket() as sock:sock.bind(('127.0.0.1',p))
(out/'compose.env').write_text('BLOODHOUND_PORT=48080\nNEO4J_WEB_PORT=48474\nNEO4J_BOLT_PORT=48687\n')
subprocess.run(['docker','volume','ls','--format','json'],stdout=(out/'volumes-before.json').open('w'),check=True)
print(json.dumps({'cohort':[{'source':p['source_label'],'goal':p['target_label']} for p in pack['pairs']],'input_coverage':pack['input_coverage'],'conservation':conservation},indent=2))
