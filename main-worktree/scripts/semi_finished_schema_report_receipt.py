"""Archive checksum and recovery-stop receipt; no migration actions."""
from semi_finished_schema_production import ROOT,OUT,DB,sha,save,read,now
p=ROOT/'docs/evidence/SEMI_FINISHED_SCHEMA_PRODUCTION_FINAL_CONSOLIDATED_20260909.md'
text=p.read_text(encoding='utf-8');lines=text.splitlines()
assert len(lines)<=500 and text.count('```')%2==0
assert all(f'## {i}.' in text for i in range(1,10))
assert not any(c in text for c in ('\u200b','\ufeff','\ufffd'))
assert 'PRODUCTION MIGRATION = FAIL / ROLLED BACK' in text
assert read('FINAL_RECOVERY_CHECK.json')['status']=='PASS'
assert sha(DB)==read('PREFLIGHT.json')['sha256']==read('BACKUP.json')['backupSHA']
assert read('FINAL_INPUT_MANIFEST.json')['coreInputFiles']==25
save('REPORT_READBACK_RECEIPT.json',{'path':str(p),'sha256':sha(p),'lineCount':len(lines),'readback':'FULL_CONTENT_READ',
    'reviewLevel':'C','fullReportBodyRequired':True,'status':'BLOCKED / RECOVERY COMPLETE',
    'timestamp':now(),'productionBusinessFactCreate':0,'productionDatabaseRestored':True})
print(str(p));print('Lines:',len(lines));print('SHA256:',sha(p))
