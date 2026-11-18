"""Unchanged delivered scheduling primitives, shared by the test source adapter."""
from copy import deepcopy
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal
from hashlib import sha256
import json
from django.conf import settings
from django.db import models
from .models import SchedulingCompanyMutex as Mutex
from pde.manufacturing_time_calculation import _minutes
from pde.order_routing_execution_service import fail as _fail

def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False))

def _hash(value):
    return sha256(json.dumps(_json(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

def _writer_lock(actor):
    # This is an actual UPDATE as the first transaction query: SQLite obtains
    # its cross-process writer lock before any source or reservation is read.
    if not Mutex.objects.filter(company_id=actor.company_id).update(revision=models.F("revision") + 1):
        Mutex.objects.create(company_id=actor.company_id, revision=1)

def _instant(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        _fail("FORMAL_SCHEDULE_TIMEZONE_REQUIRED", "正式分段必须包含明确时区。")
    return result

def _db_instant(value):
    """Only these new scheduling interval fields use UTC storage semantics.

    Legacy USE_TZ=False remains untouched. SQLite then stores UTC without a
    timezone marker; every read of these interval fields reattaches UTC.
    """
    value = value.astimezone(datetime_timezone.utc)
    return value if settings.USE_TZ else value.replace(tzinfo=None)

def _read_instant(value):
    return value.replace(tzinfo=datetime_timezone.utc) if value.tzinfo is None else value

def _segments(preview, company_id):
    from pde.manufacturing_time_calculation import _minutes
    rows = []
    for step in preview["dates"]:
        for phase in step.get("phases", []):
            if phase["phase"] != "processing":
                if phase.get("occupancy") not in {"WORK_TIME_ONLY", "WAIT_ONLY"}:
                    _fail("SCHEDULE_PHASE_RESOURCE_RULE_UNSUPPORTED", "当前正式保存仅开放加工资源占用；其他资源阶段须另有正式实现。")
                continue
            if phase["occupancy"] != "WORK_CENTER" or not step.get("workCenterId"):
                _fail("SCHEDULE_PROCESSING_RESOURCE_REQUIRED", "加工阶段缺少正式工作中心资源规则。")
            for allocation in phase["allocations"]:
                begin, end = _instant(allocation["start"]), _instant(allocation["end"])
                if begin >= end:
                    _fail("SCHEDULE_PROCESSING_SEGMENT_INVALID", "正式加工占用分段必须具有正时间长度。")
                rows.append({"companyId": company_id, "stepId": step["rootStepId"], "sequence": step["sequence"],
                    "workCenterId": step["workCenterId"], "start": begin.isoformat(), "end": end.isoformat(),
                    "productionDate": allocation["productionDate"], "minutes": str(_minutes(begin, end)),
                    "stepLabel": step["operationName"]})
    return rows
