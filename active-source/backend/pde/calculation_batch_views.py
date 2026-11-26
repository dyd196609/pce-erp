from contextlib import contextmanager
from hashlib import sha256
import inspect
import json
import logging
from time import perf_counter
from types import CodeType
from uuid import uuid4

from django.db import connection
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .engineering_calculation_service import EngineeringCalculationError
from . import calculation_batch_reuse as service
from .engineering_workload_summary import (
    CONTRACT as ENGINEERING_WORKLOAD_CONTRACT,
    build_engineering_workload_summary, engineering_workload_summary_read_failure,
    stamp_engineering_workload_summary,
)
from .operation_requirement_service import OperationRequirementError, OperationRequirementService


_read_logger = logging.getLogger('django.server')


def _diagnostic_id(value):
    try:
        number = int(value)
        return number if 0 < number < 2 ** 63 else None
    except (TypeError, ValueError):
        return None


def _loaded_reader_code_sha256():
    """code-signature-v1: loaded reader code only, never stored/query values."""
    def signature(value):
        if isinstance(value, CodeType):
            return ['code', value.co_qualname, value.co_argcount, value.co_posonlyargcount,
                value.co_kwonlyargcount, value.co_nlocals, value.co_stacksize, value.co_flags,
                value.co_code.hex(), value.co_names, value.co_varnames, value.co_freevars,
                value.co_cellvars, value.co_firstlineno, value.co_linetable.hex(),
                value.co_exceptiontable.hex(), signature(value.co_consts)]
        if isinstance(value, (tuple, frozenset)):
            items = [signature(item) for item in value]
            return [type(value).__name__, sorted(items, key=repr) if isinstance(value, frozenset) else items]
        return [type(value).__name__, value.hex() if isinstance(value, bytes) else repr(value)]
    code = inspect.unwrap(OperationRequirementService.read).__code__
    payload = json.dumps(signature(code), ensure_ascii=True, separators=(',', ':'))
    return sha256(payload.encode('utf-8')).hexdigest()


class EngineeringCalculationBatchView(APIView):
    permission_classes = [IsAuthenticated]

    @contextmanager
    def _read_stage(self, name):
        diagnostic = getattr(self, '_read_diagnostic', None)
        if diagnostic is None:
            yield
            return
        started, selected = perf_counter(), diagnostic['selectCount']
        try:
            yield
        finally:
            stage = diagnostic['stages'][name]
            stage['calls'] += 1
            stage['handlerMs'] = round(stage['handlerMs'] + (perf_counter() - started) * 1000, 3)
            stage['selectCount'] += diagnostic['selectCount'] - selected

    def respond(self, request, execute=False):
        try:
            action=request.data.get('action') if execute else request.query_params.get('action')
            if execute:
                isolation=service.authorize(request.user)
            else:
                isolation=service.verify_read_isolation()
                service.authorize_read(request.user)
            selected_workbook = (request.data if execute else request.query_params).get('workbookSourceRecordId')
            if action == 'workbookSources':
                if execute:
                    raise ValueError('WORKBOOK_CANDIDATES_READ_ONLY')
                result = service.workbook_source_catalog(request.user)
                result.update(factLoadStatus='loaded', tenantId=request.user.company_id,
                    batchId='PDE-WORKBOOK-SOURCE-CANDIDATES', loadedAt=timezone.now().isoformat(),
                    apiUrl=request.path, httpStatus=200, runtimeIsolation=isolation,
                    sourceIntakeAllowed=False,
                    sourceIntakeStatusLabel='该版本仅承接核算来源；工程对象来源及已确认基线保持原关联')
                return Response(result)
            if selected_workbook not in (None, '') and action in {'saveDraft', 'saveRegisteredSourceDraft'}:
                raise EngineeringCalculationError('WORKBOOK_OBJECT_SOURCE_WRITE_NOT_SUPPORTED',
                    '选定工作簿仅承接核算来源，不能据此复制或改写工程对象来源；请使用正式主核算接续动作。')
            workbook_context = service.resolve_workbook_read_context(request.user, selected_workbook)
            include_workload_summary = True
            if not execute and action == 'designCalculationContext':
                include_value = request.query_params.get('includeWorkloadSummary')
                if include_value not in (None, 'true', 'false'):
                    raise ValueError('工程作业量汇总读取选项无效；仅允许true或false')
                include_workload_summary = include_value != 'false'
            if action == 'designCalculationContext':
                with self._read_stage('sourceContext'):
                    result=service.design_calculation_context(
                        request.user, request.query_params.get('sourceRecordId'),
                        workbook_source_context=workbook_context,
                    )
            elif action == 'draftCatalog':
                with self._read_stage('sourceContext'):
                    result=service.draft_catalog(request.user, request.query_params.get('orderEngineeringInstanceId'),
                        workbook_source_context=workbook_context)
            elif action == 'saveDraft':
                result=service.save_draft(request.user, request.data)
            elif action == 'saveRegisteredSourceDraft':
                result=service.save_registered_source_draft(request.user, request.data)
            else:
                result=(service.run_batch(request.data.get('sourceKeys'), workbook_source_context=workbook_context)
                        if execute else service.catalog(workbook_source_context=workbook_context))
            if not execute and action in {'designCalculationContext', 'draftCatalog'}:
                drafts = [result['draft']] if isinstance(result.get('draft'), dict) else result.get('drafts', [])
                for draft in drafts:
                    if isinstance(draft, dict):
                        if not include_workload_summary:
                            # The source was read; its separate workload projection
                            # has not been requested and has no quantity facts yet.
                            draft['engineeringWorkloadSummary'] = {
                                'contractVersion': ENGINEERING_WORKLOAD_CONTRACT,
                                'factSource': 'server', 'readStatus': 'not_requested',
                                'readStatusLabel': '当前工程数据录入尚未请求工程作业量汇总',
                                'factLoadStatus': 'not_requested', 'businessWriteCount': 0,
                                'sourceRecordId': draft.get('id'), 'tenantId': request.user.company_id,
                            }
                            continue
                        with self._read_stage('summary'):
                            try:
                                summary = build_engineering_workload_summary(user=request.user, draft=draft)
                            except (OperationRequirementError, ValueError, OSError) as exc:
                                summary = engineering_workload_summary_read_failure(exc, source_record_id=draft.get('id'))
                            draft['engineeringWorkloadSummary'] = stamp_engineering_workload_summary(
                                summary, tenant_id=request.user.company_id, api_url=request.path, http_status=200)
            result.update(factLoadStatus='loaded', tenantId=request.user.company_id,
                          loadedAt=timezone.now().isoformat(), apiUrl=request.path,
                          batchId='PDE-ENGINEERING-BATCH-READ', httpStatus=200, runtimeIsolation=isolation,
                          workbookSourceRecordId=workbook_context['proof']['workbookSourceRecordId'] if workbook_context is not None else None)
            return Response(result)
        except (EngineeringCalculationError, OperationRequirementError, ValueError, OSError) as exc:
            code=getattr(exc,'code','BATCH_SOURCE_READ_FAILED')
            http=(503 if code == 'NON_PRODUCTION_ISOLATION_REQUIRED' else
                  403 if code in {'PERMISSION_DENIED','SCOPE_DENIED','IDENTITY_INVALID'} else 400)
            fallback_message = str(exc) if isinstance(exc, ValueError) and str(exc) else '批量来源或范围检查失败；未执行业务写入。'
            return Response({'factLoadStatus':'read_failed','code':code,'errorCode':code,
                'message':getattr(exc,'message',fallback_message),
                'details':getattr(exc,'details',{'reason':str(exc)}), 'httpStatus':http,
                'apiUrl':request.path, 'tenantId':request.user.company_id,
                'batchId':'PDE-ENGINEERING-BATCH-READ',
                'loadedAt':timezone.now().isoformat(), 'businessWriteSideEffectCount':0}, status=http)

    def get(self, request):
        action = request.query_params.get('action')
        if action not in {'designCalculationContext', 'draftCatalog'}:
            return self.respond(request)
        diagnostic = {'requestId': uuid4().hex, 'action': action,
            'sourceRecordId': _diagnostic_id(request.query_params.get('sourceRecordId')),
            'orderEngineeringInstanceId': _diagnostic_id(request.query_params.get('orderEngineeringInstanceId')),
            'companyId': _diagnostic_id(getattr(request.user, 'company_id', None)),
            'userId': _diagnostic_id(getattr(request.user, 'pk', None)), 'selectCount': 0,
            'loadedReaderCodeSha256': _loaded_reader_code_sha256(),
            'loadedReaderCodeHashContract': 'code-signature-v1',
            'stages': {name: {'calls': 0, 'handlerMs': 0.0, 'selectCount': 0}
                for name in ('sourceContext', 'summary')}}
        self._read_diagnostic = diagnostic
        def count_select(execute, sql, params, many, context):
            first = sql.lstrip().split(None, 1)
            if first and first[0].upper() == 'SELECT':
                diagnostic['selectCount'] += 1
            return execute(sql, params, many, context)
        started, response = perf_counter(), None
        _read_logger.info('PCE_BATCH_READ_BEGIN %s', json.dumps(diagnostic, sort_keys=True))
        try:
            with connection.execute_wrapper(count_select):
                response = self.respond(request)
            return response
        finally:
            _read_logger.info('PCE_BATCH_READ_END %s', json.dumps({**diagnostic,
                'httpStatus': getattr(response, 'status_code', None),
                'handlerMs': round((perf_counter() - started) * 1000, 3)}, sort_keys=True))
            del self._read_diagnostic

    def post(self, request):
        return self.respond(request, execute=True)


