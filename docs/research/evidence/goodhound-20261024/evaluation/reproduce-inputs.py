"""Rebuild the audited native/CE inputs from the immutable public ZIP."""
from pathlib import Path
from copy import deepcopy
import hashlib, json, subprocess, sys, zipfile
from scripts.convert_seamless_ce import convert_records, validate_conservation, encoded
archive=Path(sys.argv[1]); output=Path(sys.argv[2]); output.mkdir(parents=True,exist_ok=False)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='8477a020eb9312ce469177500941f23f13563bdae3f2a4813370c174e72dc4ed'
original=output/'original'; adapted=output/'adapted'; ce=output/'ce6'
for p in (original,adapted,ce):p.mkdir()
raw={}; removed=[]; metadata={}
with zipfile.ZipFile(archive) as zipped:
    for info in zipped.infolist():
        assert Path(info.filename).name==info.filename and info.filename.endswith('.json')
        body=zipped.read(info); source=json.loads(body.decode('utf-8-sig')); data=deepcopy(source); kind=data['meta']['type']
        (original/info.filename).write_bytes(body)
        for index,row in enumerate(data[kind]):
            if kind!='groups':continue
            for j in reversed(range(len(row['Members']))):
                member=row['Members'][j]
                if member['MemberId'] in {'WINDOMAIN.LOCAL-S-1-5-20','S-1-5-21-2099590610-328841986-2664697228-11659'}:
                    removed.append((kind,index,j,row['Members'].pop(j)))
        restored=deepcopy(data)
        for k,index,j,member in sorted(removed,key=lambda x:x[2]):
            if k==kind:restored[k][index]['Members'].insert(j,member)
        assert restored==source
        (adapted/info.filename).write_bytes(body if data==source else (json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode())
        raw[kind]=data[kind];metadata[kind]=(info.filename,data['meta'])
assert len(removed)==2 and sum(map(len,raw.values()))==1386
converted=convert_records(raw); validate_conservation(raw,converted)
for kind,rows in converted.items():
    filename,meta=metadata[kind];(ce/filename).write_bytes(encoded({'data':rows,'meta':{**meta,'version':6}}))
for name,folder,dataset in [('original',original,'goodhound-detectionlab-c2d8915'),('adapted',adapted,'goodhound-detectionlab-adaptation-v2'),('ce6',ce,'goodhound-adaptation-v2-ce6')]:
    subprocess.run([sys.executable,'scripts/snapshot_manifest.py','generate',str(folder),'--output',str(output/(name+'-manifest.json')),'--dataset-id',dataset,'--collector-name','SharpHound','--collector-version','unknown','--collected-at','unknown'],check=True)
print('Reproduced original, audited two-reference adaptation, and losslessly converted CE6 inputs.')
