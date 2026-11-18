"""Reproduce isolated install and offline acceptance; no provider credentials inherited."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--environment',required=True);p.add_argument('--report',required=True);p.add_argument('--render-dependencies',action='store_true');a=p.parse_args()
home=Path(a.environment).absolute();report=Path(a.report).absolute()
if home.exists() or home.is_relative_to(ROOT) or report.is_relative_to(ROOT):raise ValueError('Fresh external environment/report required')
if sys.version_info<(3,12):raise RuntimeError('Reproduction runner requires Python >=3.12')
home.mkdir(mode=0o700,parents=True);(home/'home').mkdir(mode=0o700)
env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(home/'home'),'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','TOOLKIT_STATE_DIR':str(home/'state')}
results=[]
def run(label,command):
 log=home/(label+'.txt')
 with log.open('w') as out:
  done=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
 log.chmod(0o600);results.append({'step':label,'exit_code':done.returncode})
 report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps({'steps':results,'external_provider_acceptance':False},indent=2))
 if done.returncode:raise RuntimeError('Acceptance failed: '+label+'; see private log')
run('venv',[sys.executable,'-m','venv',str(home/'venv')]);python=str(home/'venv/bin/python')
req=[python,'-m','pip','install','-r',str(ROOT/'requirements.txt')]
if a.render_dependencies:req+=['-r',str(ROOT/'requirements-render.txt')]
run('install',req);run('pip-check',[python,'-m','pip','check'])
run('python-tests',[python,'-m','unittest','discover','-s','tests','-v'])
run('release-gate',[python,'tests/release_gate.py'])
run('native-tests',['node','--test','tests/test_product_native_bridge.mjs','tests/test_support_guards.mjs'])
run('native-social-syntax',['node','--check','plugins/social-owner-bridge/index.mjs'])
print(json.dumps({'passed':len(results),'total':len(results),'report':str(report),'provider_credentials_inherited':False}))
