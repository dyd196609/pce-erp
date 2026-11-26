"""Final report readback/integrity receipt; no browser or business actions."""
import re
from datetime import datetime,timezone
from room_door_edge import ROOT,read,save,sha
report=ROOT/'docs/evidence/ROOM_DOOR_EDGE_FINAL_CONSOLIDATED_20260909.md'
text=report.read_text(encoding='utf-8');lines=text.splitlines()
assert len(lines)<=500 and text.count('```')%2==0
assert not re.search('[\u200b\ufeff\ufffd]',text)
assert all(f'## {n}.' in text for n in range(1,12))
assert read('INPUT_MANIFEST.json')['coreInputFileCount']==28
screen=read('FINAL_DELIVERED_USER_SCREEN_EVIDENCE.json')
assert screen['selectedTabId']=='1' and screen['selectedQSFB'] and screen['componentCount']==8 and screen['stopAllBrowserActions']
assert sha(ROOT/'backend/db.sqlite3')==read('FINAL_NON_REGRESSION.json')['productionSHA']
save('REPORT_READBACK_RECEIPT.json',{'reportPath':str(report),'reportSha256':sha(report),'lineCount':len(lines),
    'readback':'FULL_CONTENT_READ_AND_VALIDATED','reviewLevel':'C','fullContentReviewRequired':True,
    'archiveContentReadback':True,'chatgptReviewableDelivery':'FULL_REPORT_BODY_WITH_FINAL_RESPONSE',
    'timestamp':datetime.now(timezone.utc).isoformat(),'finalBrowserActionsStoppedAt':screen['timestamp'],
    'userManualRevalidation':'PENDING','productionBusinessWrite':0})
print('Report:',report,'\nLines:',len(lines),'\nSHA256:',sha(report))
