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
 timed_out=False
 try:
  done=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=600)
  stdout,stderr,exit_code=done.stdout,done.stderr,done.returncode
 except subprocess.TimeoutExpired as exc:
  stdout,stderr,exit_code=exc.stdout or b'',exc.stderr or b'',None;timed_out=True
 for suffix,content in [('stdout',stdout),('stderr',stderr)]:
  log=home/(label+'.'+suffix);log.write_bytes(content);log.chmod(0o600)
 results.append({'step':label,'exit_code':exit_code,'timed_out':timed_out})
 report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps({'steps':results,'external_provider_acceptance':False},indent=2));report.chmod(0o600)
 if timed_out or exit_code:raise RuntimeError('Acceptance failed: '+label+'; see private logs')
run('venv',[sys.executable,'-m','venv',str(home/'venv')]);python=str(home/'venv/bin/python')
req=[python,'-m','pip','install','-r',str(ROOT/'requirements.txt')]
if a.render_dependencies:req+=['-r',str(ROOT/'requirements-render.txt')]
run('install',req);run('pip-check',[python,'-m','pip','check'])
run('python-tests',[python,'-m','unittest','discover','-s','tests','-v'])
run('release-gate',[python,'tests/release_gate.py'])
run('native-tests',['node','--test',*[str(p.relative_to(ROOT)) for p in sorted((ROOT/'tests').glob('test_*.mjs'))]])
for entry in sorted((ROOT/'plugins').glob('*/index.mjs')):
 run('native-syntax-'+entry.parent.name,['node','--check',str(entry.relative_to(ROOT))])
print(json.dumps({'passed':len(results),'total':len(results),'report':str(report),'provider_credentials_inherited':False}))
