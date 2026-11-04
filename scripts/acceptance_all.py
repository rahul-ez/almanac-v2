"""Run HTTP phases without disabling or resetting authentication rate limits."""
import subprocess
import sys
import time
from datetime import datetime,timezone
from sqlalchemy import select
from app.auth.security import digest
from app.config import Settings
from app.db.connection import make_engine
from app.db.models import AuthRateLimit


def wait_for_budget(engine,settings,required):
    if min(settings.login_limit_per_minute,settings.csrf_limit_per_minute)<required:
        raise SystemExit('Configured authentication budget is too small for this phase; use the documented individual walkthrough')
    announced=False
    while True:
        window=int(datetime.now(timezone.utc).timestamp())//60
        with engine.connect() as conn:
            counts=[conn.execute(select(AuthRateLimit.count).where(AuthRateLimit.key==digest(f'{scope}:127.0.0.1:{window}'))).scalar_one_or_none() or 0 for scope in ('login-ip','csrf')]
            users=[conn.execute(select(AuthRateLimit.count).where(AuthRateLimit.key==digest(f'login-user:{name}:{window}'))).scalar_one_or_none() or 0 for name in ('admin','student-a','student-b')]
        if counts[0]+required<=settings.login_limit_per_minute and counts[1]+required<=settings.csrf_limit_per_minute and (not required or all(count+1<=settings.login_limit_per_minute for count in users)): return
        if not announced: print('Waiting for authentication rate-limit budget; limits remain enabled.',flush=True);announced=True
        time.sleep(min(5,max(.1,(window+1)*60-time.time()+.1)))


def main():
    settings=Settings();engine=make_engine(settings)
    try:
        phases=[('intent',1)] if '--intent' in sys.argv else [(str(n),needed) for n,needed in enumerate((0,3,2,2,2,2,3))]
        for phase,needed in phases:
            wait_for_budget(engine,settings,needed)
            script='acceptance_intent.py' if phase=='intent' else 'acceptance_phase'+phase+'.py'
            subprocess.run([sys.executable,'/workspace/scripts/'+script],check=True)
    finally: engine.dispose()

if __name__=='__main__': main()
