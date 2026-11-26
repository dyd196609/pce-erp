"""Full configured frontend build; logs isolated from previous evidence."""
import json, os, subprocess, sys
from semi_finished_schema_retry import ROOT, ISO, OUT, save
stage=sys.argv[1]
frontend=(ISO if stage=='rehearsal' else ROOT)/'frontend'
env=dict(os.environ);env['PATH']='D:/nodejs;'+env.get('PATH','')
commands=[('frontend-full-build',['D:/nodejs/node.exe','D:/nodejs/node_modules/npm/bin/npm-cli.js','run','build']),
    ('foundation-preview',['D:/nodejs/node.exe','src/meta/runtime/foundationWave1ImportPreview.test.mjs'])]
results=[]
for name,args in commands:
    with open(OUT/(stage.upper()+'_'+name+'.log'),'w',encoding='utf-8') as log:
        r=subprocess.run(args,cwd=frontend,env=env,stdout=log,stderr=subprocess.STDOUT)
    results.append({'name':name,'exitCode':r.returncode,'status':'PASS' if r.returncode==0 else 'FAIL'})
    print(name,r.returncode,flush=True)
    save(stage.upper()+'_FRONTEND_BUILD.json',{'status':'PASS' if all(r['exitCode']==0 for r in results) else 'FAIL','commands':results})
    if r.returncode:sys.exit(r.returncode)
