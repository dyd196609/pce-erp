from pde.baseline_usage_service import production_baselines, production_status
"""Versioned workbook evidence for the existing approved adapter, not a calculator.

Raw workbook columns are projected into explicitly published adapter aliases.
The original arithmetic methods remain the only calculation implementation.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

from .source_format_mapping_service import SourceFormatMappingError

FORMAT='XLSX_ADAPTER'
BLOB_CONTRACT='PCE-ENGINEERING-WORKBOOK-BLOB-V1'
CONTRACT='PCE-ENGINEERING-WORKBOOK-SOURCE-V1'
MAX_BYTES=20*1024*1024
MAX_EXPANDED=256*1024*1024
COLUMN=re.compile(r'^[A-Z]{1,3}$')
CELL=re.compile(r'^([A-Z]{1,3})([1-9][0-9]*)$')


class WorkbookSourceError(SourceFormatMappingError):
    pass


def fail(code,message,**details):
    raise WorkbookSourceError(code,message,details)


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()


def _safe(value):
    return json.loads(json.dumps(value,ensure_ascii=False,default=str))


def is_workbook_rule(rule):
    spec=rule.specification if hasattr(rule,'specification') else rule
    return isinstance(spec,dict) and isinstance(spec.get('sourceFormatMapping'),dict) and spec['sourceFormatMapping'].get('format')==FORMAT


def is_workbook_source(source):
    payload=source.source_payload if hasattr(source,'source_payload') else source
    return isinstance(payload,dict) and isinstance(payload.get('rawContent'),dict) and payload['rawContent'].get('contractVersion')==BLOB_CONTRACT


def validate_workbook_mapping(config):
    from .source_format_mapping_service import CONTRACT as MAPPING,validate_mapping
    from .calculation_batch_reuse import VERSION
    if (not isinstance(config,dict) or config.get('contractVersion')!=MAPPING or config.get('format')!=FORMAT
        or config.get('adapterContract')!=VERSION or not isinstance(config.get('sheets'),list)
        or not 1<=len(config['sheets'])<=32):
        fail('WORKBOOK_MAPPING_INVALID','工作簿必须明确引用已批准适配合同及有效Sheet映射')
    names=set();row_count=0
    for sheet in config['sheets']:
        if not isinstance(sheet,dict) or not isinstance(sheet.get('sheetName'),str) or not sheet['sheetName'].strip() or sheet['sheetName'] in names:
            fail('WORKBOOK_MAPPING_INVALID','工作簿Sheet名称必须明确且唯一')
        names.add(sheet['sheetName']);rows=sheet.get('sourceRows');fields=sheet.get('fields')
        if (not isinstance(rows,list) or not rows or len(rows)!=len(set(rows))
            or any(type(row) is not int or not 1<=row<=10000 for row in rows)):
            fail('WORKBOOK_MAPPING_INVALID','必须维护明确、不重复且有界的来源行')
        row_count+=len(rows)
        if row_count>1000 or not isinstance(fields,list) or not fields or len(fields)>100:
            fail('WORKBOOK_MAPPING_INVALID','工作簿映射最多1000行，每个Sheet最多100列')
        # Reuse the existing numeric, null, zero and unit syntax validation.
        validate_mapping({'contractVersion':MAPPING,'format':'JSON_ROWS','fields':fields})
        identities=[]
        for field in fields:
            if not COLUMN.fullmatch(field['rawField']) or not CELL.fullmatch(str(field.get('headerCell',''))):
                fail('WORKBOOK_MAPPING_INVALID','实际列和表头单元格必须为有效Excel坐标')
            if CELL.fullmatch(field['headerCell']).group(1)!=field['rawField'] or 'headerValue' not in field:
                fail('WORKBOOK_MAPPING_INVALID','实际列必须固定同列表头值，不能猜测列含义')
            if field.get('identity'):
                if field['valueType']!='text' or not isinstance(field.get('baselinePath'),str):
                    fail('WORKBOOK_MAPPING_INVALID','对象身份必须使用有正式基线路径的文本字段')
                identities.append(field)
            path=field.get('baselinePath')
            if path is not None and (not isinstance(path,str) or not path or any(not part or part.startswith('_') for part in path.split('.'))):
                fail('WORKBOOK_MAPPING_INVALID','基线核对路径必须为明确的结构化字段路径')
            override=field.get('designOverrideField')
            if override is not None and (not isinstance(override,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]*',override)):
                fail('WORKBOOK_MAPPING_INVALID','当前设计覆盖必须引用正式核算输入字段')
            method=field.get('methodReference',False)
            if type(method) is not bool or (method and (path or override or field['sourceType']=='ENGINEERING_DERIVED')):
                fail('WORKBOOK_MAPPING_INVALID','方法输入引用必须为布尔声明，并与基线路径、设计覆盖及派生输出分开')
            if field['sourceType']!='ENGINEERING_DERIVED' and not (path or method):
                fail('WORKBOOK_INPUT_AUTHORITY_REQUIRED','真实输入必须配置正式基线或已批准方法输入依据，不得仅按行号认定同一对象',adapterSlot=field['canonicalName'])
        if not identities:fail('WORKBOOK_OBJECT_IDENTITY_REQUIRED','每个Sheet必须维护实际对象身份字段')
    return config


def _root():
    from django.conf import settings
    return Path(getattr(settings,'PCE_ENGINEERING_SOURCE_STORAGE_ROOT',Path(settings.BASE_DIR)/'data'/'engineering-workbooks')).resolve()


def _blob_path(blob,company_id):
    expected=f"{company_id}/{blob.get('sha256','')}.xlsx" if isinstance(blob,dict) else ''
    if (not isinstance(blob,dict) or blob.get('contractVersion')!=BLOB_CONTRACT or type(company_id) is not int
        or not re.fullmatch(r'[0-9a-f]{64}',str(blob.get('sha256',''))) or blob.get('storageKey')!=expected
        or type(blob.get('bytes')) is not int or not 0<blob['bytes']<=MAX_BYTES):
        fail('WORKBOOK_BLOB_INVALID','工作簿必须引用当前公司受控内容寻址文件，不接受任意路径')
    root=_root();path=(root/expected).resolve()
    if root not in path.parents:fail('WORKBOOK_STORAGE_SCOPE_INVALID','工作簿存储路径越出受控目录')
    return path


def _check_zip(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries=archive.infolist()
            if (len(entries)>5000 or sum(item.file_size for item in entries)>MAX_EXPANDED
                or any(item.flag_bits&1 or item.filename.startswith(('/','\\')) or '..' in Path(item.filename).parts for item in entries)
                or 'xl/workbook.xml' not in archive.namelist() or any('vbaProject' in item.filename for item in entries)):
                fail('WORKBOOK_ARCHIVE_INVALID','工作簿压缩包超出边界、含宏或不可校验内容')
    except BadZipFile:
        fail('WORKBOOK_ARCHIVE_INVALID','文件不是有效XLSX工作簿')


def store_workbook_bytes(content,*,filename,company_id):
    if not isinstance(content,bytes) or not 0<len(content)<=MAX_BYTES or type(company_id) is not int or company_id<=0:
        fail('WORKBOOK_BLOB_INVALID','上传文件必须为有界XLSX字节和明确公司')
    _check_zip(content);hash_value=sha256(content).hexdigest()
    blob={'contractVersion':BLOB_CONTRACT,'sha256':hash_value,'bytes':len(content),
        'storageKey':f'{company_id}/{hash_value}.xlsx','originalName':Path(str(filename)).name[:200]}
    path=_blob_path(blob,company_id);path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as target:target.write(content)
    except FileExistsError:
        if path.read_bytes()!=content:fail('WORKBOOK_STORAGE_CONFLICT','同一内容地址已有不同字节，禁止覆盖')
    if sha256(path.read_bytes()).hexdigest()!=hash_value:fail('WORKBOOK_STORAGE_HASH_MISMATCH','工作簿保存后Hash不一致')
    return blob


def _read_blob(blob,company_id):
    path=_blob_path(blob,company_id)
    try:content=path.read_bytes()
    except OSError as error:fail('WORKBOOK_FILE_READ_FAILED','正式工作簿无法读取',error=str(error))
    if len(content)!=blob['bytes'] or sha256(content).hexdigest()!=blob['sha256']:
        fail('WORKBOOK_FILE_HASH_MISMATCH','工作簿实际字节与正式来源版本Hash不一致')
    _check_zip(content);return content


def _reference():
    from .semi_finished_configuration_preview import SOURCE_PATH,SOURCE_SHA
    content=SOURCE_PATH.read_bytes()
    if sha256(content).hexdigest().upper()!=SOURCE_SHA:fail('WORKBOOK_ADAPTER_REFERENCE_CHANGED','已批准方法参考快照Hash不一致')
    return json.loads(content)


def _adapter_reference_proof(payload,blob):
    from .semi_finished_configuration_preview import SOURCE_SHA
    from .calculation_batch_reuse import VERSION
    reference=_reference()
    sources=[{'sha256':str(row.get('sha256','')).lower(),
        'file':row.get('file') or Path(str(row.get('path',''))).name} for row in reference.get('sourceFiles',[])]
    if not sources or any(not re.fullmatch(r'[0-9a-f]{64}',row['sha256']) for row in sources):
        fail('WORKBOOK_ADAPTER_REFERENCE_UNPROVEN','已批准方法参考缺少真实来源文件Hash合同')
    continuation=payload.get('sourceVersionContinuation')
    if continuation is not None:
        predecessor=continuation.get('predecessorAuthority') if isinstance(continuation,dict) else None
        if (not isinstance(predecessor,dict) or predecessor.get('kind')!='HASH_VERIFIED_FROZEN_WORKBOOK'
            or str(predecessor.get('sourceSnapshotSha256','')).upper()!=SOURCE_SHA
            or str(predecessor.get('workbookSha256','')).lower() not in {row['sha256'] for row in sources}
            or str(continuation.get('successorWorkbookSha256','')).lower()!=blob['sha256']
            or continuation.get('adapterContract')!=VERSION):
            fail('WORKBOOK_VERSION_CONTINUATION_UNPROVEN','来源版本承接声明与已批准参考、真实新文件或适配合同不一致')
    return {'kind':'HASH_VERIFIED_FROZEN_ADAPTER_REFERENCE','sourceSnapshotSha256':SOURCE_SHA.lower(),
        'adapterContract':VERSION,'sourceFiles':sources}


def _formula_signature(formula,inverse):
    if not formula:return None
    from openpyxl.formula.tokenizer import Tokenizer
    pieces=[]
    for token in Tokenizer(formula).items:
        value=token.value
        if token.subtype=='RANGE' and '!' not in value:
            value=re.sub(r'(\$?)([A-Z]{1,3})(\$?[0-9]+)?',lambda match:
                match[1]+inverse.get(match[2],match[2])+(match[3] or ''),value)
        if token.type!='WHITE-SPACE':pieces.append((token.type,token.subtype,value))
    return pieces


def _path(value,path):
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value:
            fail('WORKBOOK_BASELINE_FIELD_MISSING','映射引用的正式基线字段不存在，不能当作空值',baselinePath=path,missingField=part)
        value=value[part]
    return value


def _equal(left,right):
    if isinstance(left,bool) or isinstance(right,bool):return type(left) is type(right) and left==right
    if left is None or right is None:return left is right
    try:return Decimal(str(left))==Decimal(str(right))
    except (InvalidOperation,ValueError):return str(left)==str(right)


def _scope(rows,config,context,company_id):
    from .models import OrderEngineeringBaseline
    from .formal_engineering_continuation_service import _baseline_reference,_snapshot_design_input
    from .product_version_management_service import _content_snapshot
    if (not isinstance(context,dict) or type(context.get('baselineId')) is not int
        or type(context.get('objectSourceRecordId')) is not int or not isinstance(context.get('baselineSnapshotHash'),str)):
        fail('WORKBOOK_OBJECT_SCOPE_REQUIRED','工作簿必须明确核对已确认基线和原工程对象来源')
    baseline=production_baselines().select_related('sales_order').filter(pk=context['baselineId'],company_id=company_id,status='confirmed').first()
    if not baseline or baseline.snapshot_hash!=context['baselineSnapshotHash']:
        fail('WORKBOOK_BASELINE_MISMATCH','工作簿对象范围没有固定当前公司明确已确认的基线Hash')
    items=list(baseline.items.select_related('design_item__sales_order_item','design_item__source_record',
        'design_item__source_attribute','design_item__physical_uom','source_record','source_attribute')
        .prefetch_related('design_item__design_revisions').order_by('pk'))
    _baseline_reference(baseline,items)
    current={row['sourceKey']:row for row in rows};by_sheet={s['sheetName']:s for s in config['sheets']};objects=[];seen=set()
    for item in items:
        design=_snapshot_design_input(item);key=design['sourceKey'];row=current.get(key)
        latest=max(item.design_item.design_revisions.all(),key=lambda revision:(revision.revision,revision.pk),default=None)
        if (not row or key in seen or item.source_record_id!=context['objectSourceRecordId']
            or item.source_record.company_id!=company_id or item.source_record.status!='confirmed'
            or not item.confirmable or digest(item.content_snapshot)!=item.content_hash
            or item.design_item.version!=item.design_item_version or (latest.pk if latest else None)!=item.design_revision_id
            or _safe(_content_snapshot(item.design_item,latest))!=item.content_snapshot):
            fail('WORKBOOK_OBJECT_SCOPE_MISMATCH','实际来源、对象内容或当前设计修订与固定基线不一致',baselineItemId=item.pk)
        comparisons=[]
        for field in by_sheet[row['sheet']]['fields']:
            path=field.get('baselinePath')
            if not path:continue
            actual=row['canonicalInputs'][field['canonicalName']]['value'];old=_path(item.content_snapshot,path)
            if field['valueType']=='text' and old in (None,''):old=None
            override=design.get(field.get('designOverrideField')) if field.get('designOverrideField') else None
            if field.get('identity') and actual in (None,''):fail('WORKBOOK_OBJECT_IDENTITY_REQUIRED','来源对象身份不得为空',sourceKey=key)
            if not _equal(actual,old) and (override is None or not _equal(actual,override)):
                fail('WORKBOOK_OBJECT_INPUT_CHANGED','新版实际输入既不等于冻结来源事实，也没有已确认设计修订依据',
                    sourceKey=key,adapterSlot=field['canonicalName'],baselinePath=path,actual=actual,baselineValue=old,confirmedDesignValue=override)
            comparisons.append({'adapterSlot':field['canonicalName'],'baselinePath':path,'actual':actual,
                'baselineValue':old,'confirmedDesignValue':override,'matchesFrozenSource':_equal(actual,old),
                'matchesConfirmedDesign':override is not None and _equal(actual,override)})
        seen.add(key);objects.append({'baselineItemId':item.pk,'designItemId':item.design_item_id,
            'sourceAttributeId':item.source_attribute_id,'designRevisionId':item.design_revision_id,
            'contentHash':item.content_hash,'sourceKey':key,'comparisons':comparisons})
    if seen!=set(current):fail('WORKBOOK_OBJECT_SCOPE_MISMATCH','新版来源存在额外对象、重复对象或未覆盖固定基线完整范围')
    return {'baselineId':baseline.pk,'baselineSnapshotHash':baseline.snapshot_hash,'objectSourceRecordId':context['objectSourceRecordId'],
        'objectCount':len(objects),'objects':objects,'statusLabel':'工作簿对象、原来源和已确认设计内容核对一致'}


@lru_cache(maxsize=4)
def _parsed_rows(content,config_json):
    from openpyxl import load_workbook
    from openpyxl.utils.cell import column_index_from_string,get_column_letter
    from .source_format_mapping_service import _value
    from .calculation_batch_reuse import source_rows
    config=json.loads(config_json)
    values=load_workbook(BytesIO(content),read_only=True,data_only=True,keep_links=False)
    formulas=load_workbook(BytesIO(content),read_only=True,data_only=False,keep_links=False)
    reference={f"{r['sheet']}:{r['row']}":r for r in _reference()['realRows']};rows=[]
    try:
        for sheet in config['sheets']:
            name=sheet['sheetName'];fields=sheet['fields']
            if name not in values.sheetnames:fail('WORKBOOK_SHEET_MISSING','新版工作簿缺少已发布映射指定的Sheet',sheet=name)
            wanted={f"{f['rawField']}{row}" for row in sheet['sourceRows'] for f in fields}|{f['headerCell'] for f in fields}
            maximum_column=max(column_index_from_string(CELL.fullmatch(cell)[1]) for cell in wanted)
            maximum_row=max(int(CELL.fullmatch(cell)[2]) for cell in wanted)
            # Explicit bounded columns ignore styled blanks out to XFA.
            def selected_cells(worksheet):
                result={}
                for r,values_row in enumerate(worksheet.iter_rows(min_row=1,max_row=maximum_row,max_col=maximum_column,values_only=True),1):
                    for c,value in enumerate(values_row,1):
                        coordinate=f'{get_column_letter(c)}{r}'
                        if coordinate in wanted:result[coordinate]=value
                return result
            data=selected_cells(values[name]);formula_data=selected_cells(formulas[name])
            inverse={field['rawField']:field['canonicalName'] for field in fields}
            for field in fields:
                if data.get(field['headerCell'])!=field['headerValue']:
                    fail('WORKBOOK_HEADER_MISMATCH','实际表头与已发布字段含义不一致',sheet=name,cell=field['headerCell'],expected=field['headerValue'],actual=data.get(field['headerCell']))
            for row_number in sheet['sourceRows']:
                key=f'{name}:{row_number}';old=reference.get(key)
                if old is None:fail('WORKBOOK_ADAPTER_SCOPE_UNPROVEN','当前来源行没有已批准方法的参考合同',sourceKey=key)
                by_slot={field['canonicalName']:field for field in fields}
                required_inputs={item['adapterSlot'] for item in source_rows({'realRows':[old]})[0]['businessInputs']}
                for slot in required_inputs:
                    field=by_slot.get(slot)
                    if field is None:
                        fail('WORKBOOK_ADAPTER_INPUT_MAPPING_REQUIRED','已批准方法的实际输入缺少正式映射',sourceKey=key,adapterSlot=slot)
                    if not (field.get('baselinePath') or field.get('methodReference')):
                        fail('WORKBOOK_ADAPTER_INPUT_AUTHORITY_REQUIRED','实际算法输入不能仅标为派生展示而免除正式依据核对',sourceKey=key,adapterSlot=slot)
                inputs={};cells={};coordinates={};method_comparisons=[]
                for field in fields:
                    slot=field['canonicalName'];actual=f"{field['rawField']}{row_number}";raw=data.get(actual)
                    formula=formula_data.get(actual)
                    if not isinstance(formula,str):formula=getattr(formula,'text',None)
                    formula=formula if isinstance(formula,str) and formula.startswith('=') else None
                    old_formula=old['cells'].get(f'{slot}{row_number}',{}).get('formula')
                    if _formula_signature(formula,inverse)!=_formula_signature(old_formula,{}):
                        fail('WORKBOOK_ADAPTER_FORMULA_CHANGED','新版公式不能证明仅为已批准方法的字段迁移',sourceKey=key,
                            adapterSlot=slot,sourceCell=actual,formula=formula,referenceFormula=old_formula)
                    coordinate={'adapterSlot':slot,'sourceSheet':name,'sourceColumn':field['rawField'],'sourceCell':actual,
                        'headerCell':field['headerCell'],'headerValue':field['headerValue'],'sourceHeader':field['headerValue'],'sourceFormula':formula}
                    # Cached results are preserved as comparison evidence, never
                    # injected into the existing adapter's raw input contract.
                    nonnumeric_cache=field['sourceType']=='ENGINEERING_DERIVED' and isinstance(raw,bool)
                    normalized=None if nonnumeric_cache else _value(str(raw) if isinstance(raw,float) else raw,field,config,len(rows)+1)
                    if field.get('methodReference'):
                        reference_cell=old['cells'].get(f'{slot}{row_number}')
                        if not isinstance(reference_cell,dict) or 'value' not in reference_cell:
                            fail('WORKBOOK_METHOD_INPUT_UNPROVEN','方法输入必须有明确的已批准输入参考',sourceKey=key,adapterSlot=slot)
                        reference_raw=reference_cell['value']
                        reference_value=_value(str(reference_raw) if isinstance(reference_raw,float) else reference_raw,field,config,len(rows)+1)
                        if not _equal(normalized,reference_value):
                            fail('WORKBOOK_METHOD_INPUT_CHANGED','新版实际方法输入与已批准方法参考不一致，缺少正式变更依据',
                                sourceKey=key,adapterSlot=slot,sourceCell=actual,actual=normalized,referenceValue=reference_value)
                        method_comparisons.append({'adapterSlot':slot,'sourceCell':actual,'actual':normalized,
                            'actualRawValue':_safe(raw),'referenceValue':reference_value,'referenceRawValue':_safe(reference_raw),
                            'sourceFormula':formula,'referenceFormula':old_formula,
                            'valueAuthority':'APPROVED_FORMULA_PARAMETER_CACHE' if formula else 'APPROVED_LITERAL_PARAMETER',
                            'matchesApprovedMethod':True})
                    inputs[slot]={'value':normalized,'valueType':field['valueType'],'sourceType':field['sourceType'],
                        'unit':field.get('unit'),'unitDimension':field.get('unitDimension'),**coordinate}
                    cells[f'{slot}{row_number}']={'value':normalized,'formula':formula,'rawValue':_safe(raw),**coordinate}
                    if nonnumeric_cache:
                        evidence={'valueType':'boolean','value':raw,'quantified':False}
                        inputs[slot]['cacheEvidence']=deepcopy(evidence);cells[f'{slot}{row_number}']['cacheEvidence']=evidence
                    coordinates[slot]=coordinate
                rows.append({'rowNumber':len(rows)+1,'sourceKey':key,'sheet':name,'row':row_number,
                    'canonicalInputs':inputs,'cells':cells,'coordinates':coordinates,'methodReferenceComparisons':method_comparisons})
    finally:values.close();formulas.close()
    return rows


def normalize_workbook_payload(payload,*,company_id,mapping_rule,config):
    validate_workbook_mapping(config);blob=payload.get('rawContent');content=_read_blob(blob,company_id)
    authority=_adapter_reference_proof(payload,blob)  # Also checked on parse-cache hits.
    rows=deepcopy(_parsed_rows(content,json.dumps(config,ensure_ascii=False,sort_keys=True,separators=(',',':'))))
    scope=_scope(rows,config,payload.get('sourceContext'),company_id)
    selected=payload.get('sourceFormatRow',0)
    if type(selected) is not int or not 0<=selected<len(rows):fail('SOURCE_FORMAT_ROW_SELECTION_REQUIRED','选取的来源行索引无效')
    normalization={'contractVersion':CONTRACT,'format':FORMAT,'rowCount':len(rows),'rawContentHash':blob['sha256'],
        'mappingHash':digest(config),'selectedRow':selected,'sourceFormatReference':deepcopy(payload['sourceFormatReference']),
        'sourceScope':scope,'adapterReference':authority,'rows':rows}
    return {**deepcopy(payload),'normalization':normalization,'canonicalInputs':deepcopy(rows[selected]['canonicalInputs'])}


def audit_proof(obj):
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import BusinessStateTransition
    rule=is_workbook_rule(obj) if obj.__class__.__name__=='EngineeringRuleDefinition' else False
    stages=[('','draft','production.engineering.rule.create' if rule else 'production.engineering.source.maintain')]
    stages+=([('draft','reviewed','production.engineering.rule.release'),('reviewed','released','production.engineering.rule.release')]
        if rule else [('draft','confirmed','production.engineering.source.maintain')])
    states=list(BusinessStateTransition.objects.filter(object_type=obj.__class__.__name__,object_id=obj.pk).order_by('version'))
    if len(states)!=len(stages):fail('WORKBOOK_PUBLICATION_UNPROVEN','来源或映射缺少完整正式状态转换链',objectId=obj.pk)
    keys=('company_id','rule_code','version','specification') if rule else ('company_id','source_no','source_version','source_payload','content_hash')
    immutable={key:_safe(getattr(obj,key)) for key in keys};audits=[]
    for index,(state,expected) in enumerate(zip(states,stages),1):
        reference=state.audit_reference;prefix='OrganizationOperatingAuditRecord:'
        if (not isinstance(reference,str) or not reference.startswith(prefix) or not reference[len(prefix):].isdigit()
            or (state.source_state,state.target_state,state.action_code)!=expected or state.version!=index):
            fail('WORKBOOK_PUBLICATION_UNPROVEN','来源或映射状态动作、顺序或审计引用不一致')
        audit=OrganizationOperatingAuditRecord.objects.select_related('actor').only('id','organization_id','action_code',
            'actor_id','target_type','target_id','before_snapshot','after_snapshot','actor__id','actor__username','actor__company_id').filter(pk=int(reference[len(prefix):])).first()
        after=(audit.after_snapshot or {}) if audit else {};snapshot=after.get('state',{})
        if (not audit or audit.organization_id!=obj.company_id or audit.actor.company_id!=obj.company_id
            or audit.actor_id!=state.operator_id or audit.action_code!=expected[2] or audit.target_type!=obj.__class__.__name__
            or audit.target_id!=obj.pk or snapshot.get('status')!=expected[1]
            or (index>1 and any(snapshot.get(key)!=value for key,value in immutable.items()))
            or after.get('authorization',{}).get('allowed') is not True
            or after.get('executionChain',{}).get('account')!=audit.actor.username):
            fail('WORKBOOK_PUBLICATION_UNPROVEN','来源或映射正式审计与不可变内容、公司或办理人不一致')
        audits.append(audit.pk)
    return {'auditIds':audits,'stateTransitionIds':[s.pk for s in states]}


def resolve_workbook_source(source_record_id,*,company_id,baseline=None,require_confirmed=True):
    from .models import EngineeringSourceRecord,EngineeringRuleDefinition
    from .source_format_mapping_service import normalize_source_payload
    from .engineering_rule_foundation import specification_hash
    if type(source_record_id) is not int:fail('WORKBOOK_SOURCE_REQUIRED','必须明确选择正式工作簿来源版本')
    source=EngineeringSourceRecord.objects.filter(pk=source_record_id,company_id=company_id).first()
    if not source or not is_workbook_source(source):fail('WORKBOOK_SOURCE_NOT_VISIBLE','工作簿来源不在当前公司正式范围')
    if require_confirmed and source.status!='confirmed':fail('WORKBOOK_SOURCE_NOT_CONFIRMED','工作簿来源必须通过原正式确认动作')
    payload=source.source_payload;normalized=normalize_source_payload(payload,company_id=company_id)
    if normalized!=payload or source.content_hash!=normalized['normalization']['rawContentHash']:
        fail('WORKBOOK_SOURCE_SNAPSHOT_CHANGED','工作簿来源规范快照或内容Hash发生变化')
    reference=payload['sourceFormatReference'];mapping=EngineeringRuleDefinition.objects.get(pk=reference['ruleId'],company_id=company_id)
    scope=payload['normalization']['sourceScope']
    if baseline is not None and (scope['baselineId']!=baseline.pk or scope['baselineSnapshotHash']!=baseline.snapshot_hash):
        fail('WORKBOOK_BASELINE_MISMATCH','所选工作簿没有固定本次明确基线及完整对象范围')
    proof=_workbook_proof(source,mapping,require_confirmed=require_confirmed)
    rows=payload['normalization']['rows']
    return {'sourceRecord':source,'mappingRule':mapping,'proof':proof,
        'sourceData':{'realRows':deepcopy(rows),'sourceFiles':[{'file':payload['rawContent']['originalName'],'sha256':source.content_hash}]}}


def _workbook_proof(source,mapping,*,require_confirmed=True):
    """Project the same audited proof for current execution and saved reads."""
    from .engineering_rule_foundation import specification_hash
    payload=source.source_payload;scope=payload['normalization']['sourceScope']
    proof={'contractVersion':CONTRACT,'sourceRecordId':source.pk,'workbookSourceRecordId':source.pk,
        'objectSourceRecordId':scope['objectSourceRecordId'],'sourceNo':source.source_no,'sourceVersion':source.source_version,
        'contentHash':source.content_hash,'workbookSha256':payload['rawContent']['sha256'],
        'mappingRuleId':mapping.pk,'mappingRuleVersion':mapping.version,'mappingSpecificationHash':specification_hash(mapping.specification),
        'mappingHash':payload['normalization']['mappingHash'],'sourceScope':scope,
        'adapterReference':payload['normalization']['adapterReference'],
        'mappingPublication':audit_proof(mapping)}
    if require_confirmed:proof['sourceConfirmation']=audit_proof(source)
    return proof


def _saved_publication(proof, *, object_type, object_id, company_id, read_cache=None):
    """Read the exact native publication named by a saved input proof.

    Current import payloads and mapping implementations are not the authority
    for an already completed calculation. The bound row must still belong to
    this company; its original audited publication supplies the frozen input.
    """
    from .models import EngineeringSourceRecord, EngineeringRuleDefinition
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import BusinessStateTransition
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, company_id)
    rule = object_type == 'EngineeringRuleDefinition'
    model = EngineeringRuleDefinition if rule else EngineeringSourceRecord
    stages = ([('', 'draft', 'production.engineering.rule.create'),
        ('draft', 'reviewed', 'production.engineering.rule.release'),
        ('reviewed', 'released', 'production.engineering.rule.release')] if rule else
        [('', 'draft', 'production.engineering.source.maintain'),
         ('draft', 'confirmed', 'production.engineering.source.maintain')])
    if (type(object_id) is not int or not _read_once(cache,
        ('saved_publication_object_present', company_id, object_type, object_id), lambda:
            model.objects.filter(pk=object_id, company_id=company_id).exists())
        or not isinstance(proof, dict) or set(proof) != {'auditIds', 'stateTransitionIds'}
        or any(not isinstance(proof.get(key), list) or len(proof[key]) != len(stages)
            or any(type(pk) is not int or pk <= 0 for pk in proof[key])
            or len(set(proof[key])) != len(stages) for key in ('auditIds', 'stateTransitionIds'))):
        fail('WORKBOOK_PUBLICATION_UNPROVEN', '固定来源或映射缺少精确同公司正式发布身份')
    states = {row.pk: row for row in _read_once(cache,
        ('saved_publication_states', company_id, object_type, object_id, tuple(proof['stateTransitionIds'])), lambda:
        list(BusinessStateTransition.objects.filter(pk__in=proof['stateTransitionIds'])))}
    audits = {row.pk: row for row in _read_once(cache,
        ('saved_publication_audits', company_id, object_type, object_id, tuple(proof['auditIds'])), lambda:
        list(OrganizationOperatingAuditRecord.objects.select_related('actor').only(
        'id', 'organization_id', 'action_code', 'actor_id', 'target_type', 'target_id', 'before_snapshot', 'after_snapshot',
        'actor__id', 'actor__username', 'actor__company_id').filter(pk__in=proof['auditIds'])))}
    snapshots = []
    for version, (state_id, audit_id, expected) in enumerate(zip(
            proof['stateTransitionIds'], proof['auditIds'], stages), 1):
        state, audit = states.get(state_id), audits.get(audit_id)
        after = audit.after_snapshot if audit and isinstance(audit.after_snapshot, dict) else {}
        snapshot = after.get('state', {})
        if (not state or not audit or state.object_type != object_type or state.object_id != object_id
            or state.version != version or (state.source_state, state.target_state, state.action_code) != expected
            or state.audit_reference != f'OrganizationOperatingAuditRecord:{audit_id}'
            or audit.organization_id != company_id or audit.actor.company_id != company_id
            or audit.actor_id != state.operator_id or audit.action_code != expected[2]
            or audit.target_type != object_type or audit.target_id != object_id
            or not isinstance(snapshot, dict) or snapshot.get('status') != expected[1]
            or snapshot.get('company_id') != company_id
            or after.get('authorization', {}).get('allowed') is not True
            or after.get('executionChain', {}).get('account') != audit.actor.username):
            fail('WORKBOOK_PUBLICATION_UNPROVEN', '固定来源或映射的原生发布审计、状态、公司或办理人不一致')
        snapshots.append(snapshot)
    keys = ('company_id', 'rule_code', 'version', 'specification') if rule else (
        'company_id', 'source_no', 'source_version', 'source_payload', 'content_hash')
    final = snapshots[-1]
    if any(any(snapshot.get(key) != final.get(key) for key in keys) for snapshot in snapshots[1:]):
        fail('WORKBOOK_PUBLICATION_UNPROVEN', '固定发布链内的不可变内容不一致')
    for audit_id in proof['auditIds'][1:]:
        before = audits[audit_id].before_snapshot.get('state', {})
        if any(before.get(key) != final.get(key) for key in keys):
            fail('WORKBOOK_PUBLICATION_UNPROVEN', '固定发布动作前后的不可变内容不一致')
    return deepcopy(final)


def saved_workbook_input(origin,reference,objects,*,read_cache=None):
    """Prove saved input without parsing Excel or consulting latest designs.

    The original native completion audit prevents deleting a workbook proof
    and rehashing the record as legacy. Legacy records retain their old gate.
    Published source/mapping snapshots supply historical evidence only, not
    current execution eligibility, which still uses resolve_workbook_source.
    """
    from .models import EngineeringSourceRecord,EngineeringRuleDefinition
    from .engineering_rule_foundation import specification_hash
    from system.models import OrganizationOperatingAuditRecord
    from workflow_runtime.models import BusinessStateTransition
    from .operation_requirement_service import _read_once, _requirement_read_cache
    cache = _requirement_read_cache(read_cache, origin.company_id)
    trace=origin.trace or {};action='production.engineering.calculation.execute'
    markers=('workbookSource','workbookSourceRecordId')
    present=any(key in trace for key in markers) or 'workbookSource' in trace.get('idempotencyPayload',{})
    states=_read_once(cache, ('saved_workbook_completion_states', origin.company_id, origin.pk), lambda:
        list(BusinessStateTransition.objects.filter(object_type='EngineeringCalculationRecord',
        object_id=origin.pk,action_code=action,target_state='completed').order_by('pk')))
    audit=None;state={}
    if len(states)==1:
        ref=states[0].audit_reference;prefix='OrganizationOperatingAuditRecord:'
        if isinstance(ref,str) and ref.startswith(prefix) and ref[len(prefix):].isdigit():
            audit_id=int(ref[len(prefix):])
            audit=_read_once(cache, ('saved_workbook_completion_audit', origin.company_id, origin.pk, audit_id), lambda:
                OrganizationOperatingAuditRecord.objects.select_related('actor').only('id','organization_id',
                'action_code','actor_id','target_type','target_id','after_snapshot',
                'actor__id','actor__username','actor__company_id').filter(pk=audit_id).first())
            state=(audit.after_snapshot or {}).get('state',{}) if audit else {}
    recorded=state.get('trace',{}) if isinstance(state.get('trace'),dict) else {}
    if not present and not any(key in recorded for key in markers):
        # A removed transition must not turn a recorded workbook input into a
        # legacy input. The native audit is an independent contract anchor.
        calculation_audits=OrganizationOperatingAuditRecord.objects.filter(
            target_type='EngineeringCalculationRecord',target_id=origin.pk,action_code=action).order_by().values('pk')
        # Keep one SQL snapshot while limiting JSON inspection to this exact
        # native audit identity; unrelated large audit snapshots are not inputs.
        audited_workbook=_read_once(cache, ('saved_workbook_marker_present', origin.company_id, origin.pk), lambda:
            OrganizationOperatingAuditRecord.objects.filter(pk__in=calculation_audits,
            after_snapshot__state__trace__has_any_keys=list(markers)).exists())
        if not audited_workbook:
            return {}  # Original envelope and original metadata checks are unchanged.
    proof=trace.get('workbookSource')
    if (not isinstance(proof,dict) or proof.get('contractVersion')!=CONTRACT
        or trace.get('workbookSourceRecordId')!=proof.get('sourceRecordId')
        or trace.get('idempotencyPayload',{}).get('workbookSource')!=proof
        or not audit or len(states)!=1 or states[0].source_state!='running'
        or audit.organization_id!=origin.company_id or audit.actor.company_id!=origin.company_id
        or audit.actor_id!=states[0].operator_id or audit.action_code!=action
        or audit.target_type!='EngineeringCalculationRecord' or audit.target_id!=origin.pk
        or state.get('status')!='completed' or state.get('trace')!=trace
        or state.get('inputHash')!=origin.input_hash or state.get('resultHash')!=origin.result_hash
        or audit.after_snapshot.get('authorization',{}).get('allowed') is not True
        or audit.after_snapshot.get('executionChain',{}).get('account')!=audit.actor.username):
        fail('WORKBOOK_INPUT_COMPLETION_UNPROVEN','核算工作簿输入与原生完成审计或完整输入合同不一致')
    source=_saved_publication(proof.get('sourceConfirmation'),object_type='EngineeringSourceRecord',
        object_id=proof.get('sourceRecordId'),company_id=origin.company_id,read_cache=cache)
    payload=source.get('source_payload',{});normal=payload.get('normalization',{});blob=payload.get('rawContent',{})
    mapped=payload.get('sourceFormatReference',{})
    mapping=_saved_publication(proof.get('mappingPublication'),object_type='EngineeringRuleDefinition',
        object_id=proof.get('mappingRuleId'),company_id=origin.company_id,read_cache=cache)
    spec=mapping.get('specification',{})
    if (mapped.get('ruleId')!=proof.get('mappingRuleId') or mapped.get('ruleVersion')!=mapping.get('version')
        or mapped.get('specificationHash')!=specification_hash(spec)):
        fail('WORKBOOK_MAPPING_UNPROVEN','固定来源缺少同公司精确发布映射及规格Hash')
    config=spec.get('sourceFormatMapping',{})
    scope=normal.get('sourceScope',{});context=payload.get('sourceContext',{})
    rows=normal.get('rows');scope_objects=scope.get('objects')
    if (normal.get('contractVersion')!=CONTRACT or normal.get('format')!=FORMAT
        or blob.get('contractVersion')!=BLOB_CONTRACT or source.get('content_hash')!=blob.get('sha256')
        or not isinstance(blob.get('sha256'),str) or not re.fullmatch(r'[0-9a-f]{64}',blob['sha256'])
        or normal.get('rawContentHash')!=blob['sha256']
        or normal.get('mappingHash')!=digest(config) or normal.get('sourceFormatReference')!=mapped
        or not isinstance(rows,list) or not rows or normal.get('rowCount')!=len(rows)
        or not isinstance(scope_objects,list) or len(scope_objects)!=len(rows)
        or scope.get('objectCount')!=len(scope_objects)
        or scope.get('baselineId')!=reference.get('id') or scope.get('baselineSnapshotHash')!=reference.get('snapshotHash')
        or scope.get('objectSourceRecordId')!=origin.source_record_id
        or any(context.get(key)!=scope.get(key) for key in ('baselineId','baselineSnapshotHash','objectSourceRecordId'))
        or not isinstance(normal.get('adapterReference'),dict)
        or normal.get('adapterReference')!=proof.get('adapterReference')):
        fail('WORKBOOK_SOURCE_SNAPSHOT_CHANGED','固定工作簿来源、映射、完整基线范围或已批准方法证明不一致')
    by_item={row.get('baselineItemId'):row for row in scope_objects if isinstance(row,dict)}
    if len(by_item)!=len(scope_objects) or any(not isinstance(obj,dict) or
        any(by_item.get(obj.get('baselineItemId'),{}).get(key)!=obj.get(key)
            for key in ('baselineItemId','designItemId','sourceAttributeId','contentHash','sourceKey')) for obj in objects):
        fail('WORKBOOK_OBJECT_SCOPE_MISMATCH','核算固定对象未被已审计工作簿完整范围精确覆盖')
    rebuilt={'contractVersion':CONTRACT,'sourceRecordId':proof['sourceRecordId'],
        'workbookSourceRecordId':proof['sourceRecordId'],'objectSourceRecordId':scope['objectSourceRecordId'],
        'sourceNo':source.get('source_no'),'sourceVersion':source.get('source_version'),
        'contentHash':source.get('content_hash'),'workbookSha256':blob['sha256'],
        'mappingRuleId':mapped['ruleId'],'mappingRuleVersion':mapping.get('version'),
        'mappingSpecificationHash':specification_hash(spec),'mappingHash':normal['mappingHash'],
        'sourceScope':scope,'adapterReference':normal['adapterReference'],
        'mappingPublication':proof['mappingPublication'],'sourceConfirmation':proof['sourceConfirmation']}
    if rebuilt!=proof:
        fail('WORKBOOK_SOURCE_PROOF_CHANGED','核算保存的来源证明与正式来源、映射及审计不一致')
    return {'workbook_source':proof}


def restore_coordinates(rows,context):
    coordinates={row['sourceKey']:row['coordinates'] for row in context['sourceData']['realRows']};result=deepcopy(rows)
    for row in result:
        by_slot=coordinates.get(row.get('sourceKey'),{});slot=row.get('column');original=row.get('sourceCell','')
        cell=CELL.fullmatch(original) if isinstance(original,str) else None
        coordinate=by_slot.get(slot) or (by_slot.get(cell[1]) if cell else None)
        if coordinate is None:fail('WORKBOOK_OUTPUT_COORDINATE_UNPROVEN','批准方法输出没有真实工作簿坐标映射',adapterSlot=slot)
        row.update(deepcopy(coordinate));row['adapterSlot']=slot
        row['workbookSource']={key:deepcopy(value) for key,value in context['proof'].items() if key not in (
            'sourceScope','mappingPublication','sourceConfirmation')}
        row['workbookSource']['sourceScopeHash']=digest(context['proof']['sourceScope'])
        for item in row.get('inputs',[]):
            source_cell=item.get('sourceCell');match=CELL.fullmatch(source_cell) if isinstance(source_cell,str) else None
            if match:
                mapped=by_slot.get(match[1])
                if mapped is None:fail('WORKBOOK_INPUT_COORDINATE_UNPROVEN','批准方法输入没有真实工作簿坐标映射',adapterSlot=match[1])
                item.update(deepcopy(mapped))
    return result


def workbook_source_facts(company_id,baseline=None):
    from .models import EngineeringSourceRecord
    result=[]
    for source in EngineeringSourceRecord.objects.filter(company_id=company_id,status='confirmed').order_by('source_no','source_version','pk'):
        if not is_workbook_source(source):continue
        payload=source.source_payload;scope=payload.get('normalization',{}).get('sourceScope',{})
        if baseline is not None and scope.get('baselineId')!=baseline.pk:continue
        result.append({'id':source.pk,'sourceNo':source.source_no,'sourceName':source.source_name,
            'sourceVersion':source.source_version,'contentHash':source.content_hash,'statusLabel':source.get_status_display(),
            'formatRule':deepcopy(payload.get('sourceFormatReference')),'sourceScope':deepcopy(scope),
            'label':f'{source.source_name} · {source.source_version} · {source.get_status_display()}'})
    return result
