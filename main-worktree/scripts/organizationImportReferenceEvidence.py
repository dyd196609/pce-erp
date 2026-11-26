"""Read-only replay of the user file; export through the existing application service."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/evidence/pce-organization-import-reference-20260914'
DB=Path('D:/Dev-PCE/Acceptance/PDE-Operable-20260912/pde-operable-acceptance.sqlite3')
SOURCE=Path('C:/Users/DAODA/Downloads/部门-正式导入模板.xlsx')
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(ROOT/'backend'))
os.environ['DJANGO_SETTINGS_MODULE']='pce_backend.settings'
os.environ['PCE_DATABASE_PATH']=str(DB)
import django
django.setup()
from django.db import connection
from system.models import User,Department
from system.organization_import_service import OrganizationImportService as Service
from system.tests_organization_import_v1 import NamedBytesIO

with connection.cursor() as cursor: cursor.execute('PRAGMA query_only=ON')
actor=User.objects.only('id','username','company_id','is_superuser','is_active').get(username='admin',is_superuser=True,is_active=True)
before=hashlib.sha256(DB.read_bytes()).hexdigest()
source_content=SOURCE.read_bytes()
preview,_=Service.preview('departments',uploaded_file=NamedBytesIO(source_content,SOURCE.name),user=actor)
OUT.mkdir(parents=True,exist_ok=True)
def save_json(name,value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
save_json('ACTUAL_FILE_PREVIEW.json',preview)
(OUT/'部门三行-原值复验报告.xlsx').write_bytes(Service.error_report_bytes(preview))
templates=[]
for entity in ('departments','positions','employees'):
    filename=Service.schema(entity)['label']+'-修订导入模板-V1.1.xlsx'
    (OUT/filename).write_bytes(Service.template_bytes(entity,user=actor))
    templates.append(filename)
save_json('FIELD_MAPPING.json',{entity:{'fields':Service.schema(entity)['fields'],'context':Service.target_context(entity,actor)} for entity in ('departments','positions','employees')})

# Diagnose the already authorized target's existing objects without altering the file.
# This is explicitly conditional, not a claim that the user's company name matched.
schema=Service.schema('departments')
conditional=[]
for rowno,raw in Service._parse(schema,source_content):
    data={item['name']:Service._convert(item,raw.get(item['name'])) for item in schema['fields']}
    errors=[];notes=[]
    Service._normalize_references('departments',data,rowno,errors,notes,actor.company_id,{'KLG','PPG','MGC'},{})
    Service._validate_references('departments',data,rowno,errors,actor.company_id,{'KLG','PPG','MGC'})
    for error in errors:
        error['fieldLabel']=next((item['label'] for item in schema['fields'] if item['name']==error['field']), '关联校验')
    existing=Department.objects.filter(company_id=actor.company_id,code=data['code']).first()
    differences=Service._differences('departments',existing,data,actor.company_id) if existing else []
    conditional.append({'sourceRow':rowno,'identity':data['code'],'assumption':'仅当用户确认目标公司COMP001后适用；未修改原文件或正式数据','errors':errors,'normalizations':notes,'existingId':existing.pk if existing else None,'differences':differences})
save_json('CONDITIONAL_TARGET_REVIEW.json',conditional)
conditional_preview={'rows':[], 'errors':[]}
for item in conditional:
    raw=next(raw for number,raw in Service._parse(schema,source_content) if number==item['sourceRow'])
    errors=[]
    for error in item['errors']:
        errors.append({**error,'objectCode':item['identity'],'objectName':raw['name'],'inputValue':str(raw.get(error['field'],'')), 'resolvedValue':'目标公司COMP001尚待确认'})
    for difference in item['differences']:
        errors.append({'rowNumber':item['sourceRow'],'objectCode':item['identity'],'objectName':raw['name'],'fieldLabel':difference['fieldLabel'],'field':difference['field'],'errorType':'EXISTING_DIFFERENCE','inputValue':difference['inputValue'],'resolvedValue':difference['existingValue'],'message':'仅在目标公司确认为COMP001时适用：填写值与已有记录不同。','suggestedAction':'核对已有值；需要修改时使用原维护流程明确确认，本次新增导入不会覆盖。'})
    for error in errors: error['rawValue']=error.pop('inputValue','')
    conditional_preview['rows'].append({'sourceRow':item['sourceRow'],'rowNumber':item['sourceRow'],'identity':item['identity'],'objectCode':item['identity'],'objectName':raw['name'],'errors':errors,'normalizations':item['normalizations']})
    conditional_preview['errors'].extend(errors)
(OUT/'部门三行-条件性差异报告-非导入文件.xlsx').write_bytes(Service.error_report_bytes(conditional_preview))
after=hashlib.sha256(DB.read_bytes()).hexdigest()
result={'source':str(SOURCE),'sourceSha256':hashlib.sha256(source_content).hexdigest(),'sourceUnchanged':SOURCE.read_bytes()==source_content,'databaseBefore':before,'databaseAfter':after,'databaseUnchanged':before==after,'actorForReadOnlyServiceCheck':{'username':actor.username,'companyId':actor.company_id},'browserIdentityVerified':False,'counts':preview['counts'],'templates':templates,'businessWrites':0}
save_json('REPLAY_RESULT.json',result)
print(json.dumps(result,ensure_ascii=False,indent=2))
