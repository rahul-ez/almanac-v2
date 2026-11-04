"""Host-side packaged-image rehearsal. Requires only Python stdlib and Docker Compose."""
import json
import os
from pathlib import Path
import secrets
import re
import subprocess
import sys
import time
from uuid import uuid4

root=Path(__file__).resolve().parents[1]
key=uuid4().hex[:12];project='almanac-verify-'+key;image='almanac-verify:'+key
password=secrets.token_hex(24)
env=dict(os.environ,ALMANAC_VERIFY_IMAGE=image,ALMANAC_VERIFY_DB_PASSWORD=password,ALMANAC_VERIFY_MODE='baseline')
compose=['docker','compose','--project-name',project,'--file',str(root/'compose.verify.yaml')]
results=[];started=time.monotonic();success=False;cleanup=False

def run(label,command,*,capture=False):
    stamp=time.monotonic();print('RUN '+label,flush=True)
    process=subprocess.run(command,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    results.append({'stage':label,'passed':process.returncode==0,'elapsed_seconds':round(time.monotonic()-stamp,3)})
    if process.returncode:
        print(process.stdout[-5000:].replace(password,'[redacted]'),file=sys.stderr)
        raise RuntimeError('Verification failed at '+label)
    if label=='regression suite':
        counts=re.findall(r'(\d+) passed',process.stdout)
        if counts: results[-1]['passed_tests']=int(counts[-1])
    if label=='frozen semantic and retrieval gate':
        results[-1]['metrics']=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{') and line.endswith('}')]
    print('PASS '+label,flush=True)
    return process.stdout if capture else None

try:
    run('build packaged image',['docker','build','--file','backend/Dockerfile','--tag',image,'.'])
    image_id=run('record image identity',['docker','image','inspect','--format','{{.Id}}',image],capture=True).strip()
    run('start fresh isolated database',compose+['up','-d','--wait','db'])
    def once(label,args): return run(label,compose+['run','--rm','--no-deps','api',*args])
    once('migrate empty database',['alembic','upgrade','head'])
    for module in ('seed','provision','seed_events','seed_rooms','seed_faculty'):
        once('initial '+module,['python','-m','app.db.'+module])
    for module in ('seed','provision','seed_events','seed_rooms','seed_faculty'):
        once('repeat insert-only '+module,['python','-m','app.db.'+module])
    once('contract drift and fixtures',['python','/workspace/scripts/contracts.py'])
    once('train reproducible prototype',['python','/workspace/scripts/train_intent.py'])
    once('frozen semantic and retrieval gate',['python','/workspace/scripts/evaluate_backend.py','--check'])
    once('regression suite',['pytest','-q'])
    run('API start to ready in baseline',compose+['up','-d','--wait','api'])
    run('all HTTP acceptance phases',compose+['exec','-T','api','python','/workspace/scripts/acceptance_all.py'])
    env['ALMANAC_VERIFY_MODE']='hybrid'
    run('API start to ready in hybrid',compose+['up','-d','--wait','api'])
    run('hybrid HTTP acceptance',compose+['exec','-T','api','python','/workspace/scripts/acceptance_all.py','--intent'])
    success=True
except (RuntimeError,OSError) as exc:
    print(str(exc).replace(password,'[redacted]'),file=sys.stderr)
finally:
    try:
        run('remove only verification containers and volumes',compose+['down','--volumes','--remove-orphans'])
        cleanup=True
    except (RuntimeError,OSError): pass
    subprocess.run(['docker','image','rm',image],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    report={'purpose':'Fresh packaged-image engineering rehearsal, not production deployment or frontend validation',
        'passed':success and cleanup,'isolated_project':project,'host_ports_published':False,'source_bind_mounts':False,
        'cleaned_up':cleanup,'elapsed_seconds':round(time.monotonic()-started,3),'stages':results}
    if 'image_id' in locals(): report['image_id']=image_id
    destination=root/'reports/phase-7/fresh-install.json';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2)+'\n')
if not (success and cleanup): raise SystemExit(1)
print('Fresh-install rehearsal passed. Existing localhost:8000 and its database were not used.',flush=True)
