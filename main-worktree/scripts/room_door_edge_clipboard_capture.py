"""Capture the actual Windows clipboard produced by the user's visible Copy action.

The browser automation session clipboard retained an old snapshot. This reads
only the current diagnostic payload and rejects unrelated clipboard contents.
"""
import json,subprocess
from room_door_edge import OUT,read,save,sha
result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
    '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); Get-Clipboard -Raw'],
    capture_output=True,encoding='utf-8',check=True,creationflags=subprocess.CREATE_NO_WINDOW)
data=json.loads(result.stdout)
assert data['semiFinishedConfiguration']['version']=='PCE-SEMI-FINISHED-CONFIGURATION-PREVIEW-4'
api=read('API_READONLY_EVIDENCE.json')
assert data['semiFinishedConfiguration']==api['semiFinishedConfiguration']
assert data['strictFacts']==data['strictServerFacts']
assert all(data['strictFacts'][k]==v for k,v in api['strictFacts'].items() if k!='loadedAt')
previous=read('UI_DIAGNOSTIC.json')
if previous['semiFinishedConfiguration']['version']!='PCE-SEMI-FINISHED-CONFIGURATION-PREVIEW-4':
    save('TOOL_CLIPBOARD_STALE_DIAGNOSTIC.json',previous)
save('UI_DIAGNOSTIC.json',data)
save('CLIPBOARD_CAPTURE_AUDIT.json',{'status':'PASS','capturedFrom':'Windows clipboard after actual visible Copy diagnostic click',
    'browserToolClipboard':'STALE_VERSION_3_NOT_USED_FOR_ACCEPTANCE','applicationClipboard':'CURRENT_VERSION_4',
    'diagnosticGeneratedAt':data['diagnosticGeneratedAt'],'fullProjectionEqualsReadonlyAPI':True,
    'clipboardContentWrittenByScript':False,'productionBusinessWrite':0})
print('Actual application clipboard version 4 == API full projection; no page code change required')
