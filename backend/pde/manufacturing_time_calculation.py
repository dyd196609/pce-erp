"""Pure manufacturing-time calculations; no ORM, persistence or authority grants.

The caller proves company, source, revision and permission facts.  This module
only calculates supplied JSON and returns independent result objects.  Incomplete
drafts retain diagnostics; they never become a verified schedule by fallback.
"""
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CONTRACT = "PCE-MANUFACTURING-TIME-CALCULATION-V1"
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
KINDS = {"SHARED_ARRANGEMENT", "WC_APPLICATION", "OPERATION_RESTRICTION", "CAPACITY_TIME_BASIS"}
MODES = {"WINDOWS_WITH_BREAKS", "NET_WORK_SEGMENTS"}
UTC = timezone.utc


def _issue(errors, code, path, message, *, incomplete=False):
    item = {"code": code, "path": path, "message": message,
            "severity": "INCOMPLETE" if incomplete else "ERROR"}
    if item not in errors:
        errors.append(item)


def _object(value, allowed, path, errors):
    if not isinstance(value, dict):
        _issue(errors, "OBJECT_REQUIRED", path, "必须填写对象", incomplete=value is None)
        return {}
    for key in value:
        if key not in allowed:
            _issue(errors, "UNKNOWN_FIELD", f"{path}.{key}", "未声明字段，不得作为计算依据")
    return value


def _required(value, path, errors):
    if value is None or isinstance(value, str) and not value.strip():
        _issue(errors, "FIELD_REQUIRED", path, "资料待完善", incomplete=True)
        return False
    return True


def _meaningful_json(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_meaningful_json(item) for item in value.values())
    if isinstance(value, list):
        return any(_meaningful_json(item) for item in value)
    return isinstance(value, (int, float, bool))


def _enum_value(value, path, errors):
    if value is not None and not isinstance(value, str):
        _issue(errors, "STRING_REQUIRED", path, "枚举选项必须为字符串")
        return None
    return value


def _number(value, path, errors, *, positive=False):
    if not _required(value, path, errors):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or positive and result == 0:
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        _issue(errors, "INVALID_NUMBER", path, "必须为有限正数" if positive else "必须为有限非负数")
        return None


def _boolean(value, path, errors, *, required=True):
    if value is None and not required:
        return None
    if value is None:
        _issue(errors, "FIELD_REQUIRED", path, "请明确选择", incomplete=True)
    elif type(value) is not bool:
        _issue(errors, "INVALID_BOOLEAN", path, "必须为明确的是或否")
    return value if type(value) is bool else None


def _date(value, path, errors):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        _issue(errors, "INVALID_DATE", path, "日期必须为有效的年-月-日", incomplete=value in (None, ""))
        return None


def _zone(value, path, errors):
    if not _required(value, path, errors):
        return None
    try:
        if not isinstance(value, str):
            raise ValueError
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        _issue(errors, "INVALID_TIMEZONE", path, "必须选择有效的业务时区，不使用服务器默认时区")
        return None


def _merge(spans):
    result = []
    for start, end in sorted(spans):
        if start >= end:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def _subtract(spans, cuts):
    result = list(spans)
    for lower, upper in _merge(cuts):
        next_result = []
        for start, end in result:
            if upper <= start or lower >= end:
                next_result.append((start, end))
            else:
                if start < lower:
                    next_result.append((start, lower))
                if upper < end:
                    next_result.append((upper, end))
        result = next_result
    return result


def _intersect(left, right):
    return _merge((max(a, c), min(b, d)) for a, b in left for c, d in right
                  if max(a, c) < min(b, d))


def _clock(value, path, errors):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d|24:00", value):
        _issue(errors, "INVALID_CLOCK", path, "时间必须为HH:mm，24:00仅表示次日00:00",
               incomplete=value in (None, ""))
        return None
    hours, minutes = map(int, value.split(":"))
    return hours * 60 + minutes


def _segment(row, path, errors):
    row = _object(row, {"start", "end", "startDayOffset", "endDayOffset", "startFold", "endFold"}, path, errors)
    clocks = [_clock(row.get(name), f"{path}.{name}", errors) for name in ("start", "end")]
    offsets = [row.get(name, 0) for name in ("startDayOffset", "endDayOffset")]
    for index, key in enumerate(("startDayOffset", "endDayOffset")):
        if type(offsets[index]) is not int or not 0 <= offsets[index] <= 2:
            _issue(errors, "INVALID_DAY_OFFSET", f"{path}.{key}", "跨日偏移必须明确为0、1或2")
            return None
    for key in ("startFold", "endFold"):
        if key in row and (type(row[key]) is not int or row[key] not in (0, 1)):
            _issue(errors, "INVALID_FOLD", f"{path}.{key}", "重复时刻必须明确选择0或1")
    if None in clocks:
        return None
    start, end = [clocks[index] + offsets[index] * 1440 for index in (0, 1)]
    if end <= start or end - start > 2880:
        _issue(errors, "INVALID_INTERVAL", path, "结束必须晚于开始；跨日必须填写明确偏移，单段不得超过两天")
        return None
    return start, end


def _arrangement(value, path, errors):
    value = _object(value, {"inputMode", "segments", "breaks"}, path, errors)
    mode = _enum_value(value.get("inputMode"), f"{path}.inputMode", errors)
    if mode not in MODES:
        _issue(errors, "INPUT_MODE_REQUIRED", f"{path}.inputMode", "请选择总窗口扣休或已剔休工作段",
               incomplete=mode in (None, ""))
    parsed = {}
    for key in ("segments", "breaks"):
        rows = value.get(key, [] if key == "breaks" else None)
        if not isinstance(rows, list):
            _issue(errors, "LIST_REQUIRED", f"{path}.{key}", "必须为时段列表", incomplete=rows is None)
            rows = []
        spans = []
        for index, row in enumerate(rows):
            span = _segment(row, f"{path}.{key}[{index}]", errors)
            if span:
                if any(max(span[0], a) < min(span[1], b) for a, b in spans):
                    _issue(errors, "OVERLAPPING_INTERVAL", f"{path}.{key}[{index}]", "同一资源时段重叠或重复；请修正后生效")
                spans.append(span)
        parsed[key] = spans
    gross, rests = _merge(parsed["segments"]), _merge(parsed["breaks"])
    inside_rests = _intersect(gross, rests)
    if mode == "NET_WORK_SEGMENTS" and inside_rests:
        _issue(errors, "REST_OVERLAPS_NET_WORK", f"{path}.breaks", "已剔休的工作段与休息冲突，不能再次扣休")
    if mode == "WINDOWS_WITH_BREAKS" and _subtract(rests, gross):
        _issue(errors, "REST_OUTSIDE_WORK_WINDOW", f"{path}.breaks", "休息超出班段总窗口")
    net = _subtract(gross, rests) if mode == "WINDOWS_WITH_BREAKS" else gross
    return {"grossMinutes": str(sum(b - a for a, b in parsed["segments"])),
            "restMinutes": str(sum(b - a for a, b in parsed["breaks"])),
            "uniqueRestMinutes": str(sum(b - a for a, b in rests)),
            "deductedRestMinutes": str(sum(b - a for a, b in inside_rests) if mode == "WINDOWS_WITH_BREAKS" else 0),
            "netMinutes": str(sum(b - a for a, b in net)),
            "segments": [{"startMinute": a, "endMinute": b, "sourcePaths": [path]} for a, b in net]}


def _pattern(value, path, errors, *, restriction=False, target="BOTH"):
    allowed = {"processing"} if restriction else {"processing", "resource"}
    value = _object(value, allowed, path, errors)
    if target != "BOTH":
        for key in value:
            if key.upper() != target:
                _issue(errors, "EXCEPTION_COMPONENT_MISMATCH", f"{path}.{key}", "例外只允许维护明确选中的对象")
    facts = {}
    for key in ("processing", "resource"):
        if restriction and key == "resource" or target != "BOTH" and key.upper() != target:
            continue
        if key not in value:
            _issue(errors, "ARRANGEMENT_REQUIRED", f"{path}.{key}", "净加工安排或实际资源总窗口待完善", incomplete=True)
        else:
            facts[key] = _arrangement(value[key], f"{path}.{key}", errors)
    if "processing" in facts and "resource" in facts:
        proc = [(row["startMinute"], row["endMinute"]) for row in facts["processing"]["segments"]]
        resource = [(row["startMinute"], row["endMinute"]) for row in facts["resource"]["segments"]]
        if _subtract(proc, resource):
            _issue(errors, "PROCESSING_OUTSIDE_RESOURCE", path, "加工安排必须落在明确维护的资源总开放窗口内")
    return facts


def _calendar_fields(payload, errors, *, restriction=False, required=True):
    facts = {"patterns": {}}
    patterns = payload.get("patterns")
    weekly = payload.get("weeklyPatterns")
    if required or patterns is not None or weekly is not None:
        if not isinstance(patterns, dict) or not patterns:
            _issue(errors, "PATTERNS_REQUIRED", "$.patterns", "请维护至少一个命名工作模式", incomplete=patterns in (None, {}))
            patterns = {}
        for name, pattern in patterns.items():
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
                _issue(errors, "INVALID_PATTERN_NAME", "$.patterns", "模式编码限字母、数字、下划线或短横线")
            facts["patterns"][name] = _pattern(pattern, f"$.patterns.{name}", errors, restriction=restriction)
        if not isinstance(weekly, dict) or set(weekly) != set(WEEKDAYS):
            _issue(errors, "WEEKLY_PATTERN_REQUIRED", "$.weeklyPatterns", "请分别明确周一至周日模式，休息日选空",
                   incomplete=weekly is None or isinstance(weekly, dict) and set(weekly) <= set(WEEKDAYS))
        if isinstance(weekly, dict):
            for key, name in weekly.items():
                if key not in WEEKDAYS or name is not None and (not isinstance(name, str) or name not in patterns):
                    _issue(errors, "UNKNOWN_PATTERN_REFERENCE", f"$.weeklyPatterns.{key}", "必须引用本配置存在的模式，休息日为null")
    exceptions = payload.get("exceptions", [])
    if not isinstance(exceptions, list):
        _issue(errors, "LIST_REQUIRED", "$.exceptions", "日期例外必须为列表")
        exceptions = []
    seen = set()
    for index, exception in enumerate(exceptions):
        path = f"$.exceptions[{index}]"
        exception = _object(exception, {"date", "dateBasis", "target", "action", "pattern"}, path, errors)
        _date(exception.get("date"), f"{path}.date", errors)
        basis, target, action = (_enum_value(exception.get(key), f"{path}.{key}", errors)
                                for key in ("dateBasis", "target", "action"))
        if basis not in {"NATURAL_DATE", "PRODUCTION_DAY"}:
            _issue(errors, "DATE_BASIS_REQUIRED", f"{path}.dateBasis", "请选择自然日期或生产日归属", incomplete=basis is None)
        if target not in ({"PROCESSING"} if restriction else {"PROCESSING", "RESOURCE", "BOTH"}):
            _issue(errors, "EXCEPTION_TARGET_REQUIRED", f"{path}.target", "请明确例外作用的加工图或资源图", incomplete=target is None)
        if action not in {"CLOSE", "ADD", "REPLACE"}:
            _issue(errors, "EXCEPTION_ACTION_REQUIRED", f"{path}.action", "请选择停工、追加或替换", incomplete=action is None)
        for component in (("PROCESSING", "RESOURCE") if target == "BOTH" else (target,)):
            identity = (str(exception.get("date")), basis, component)
            if identity in seen:
                _issue(errors, "EXCEPTION_CONFLICT", path, "同日期、归属和对象存在重复或冲突例外")
            seen.add(identity)
        if action == "CLOSE":
            if exception.get("pattern") not in (None, {}):
                _issue(errors, "CLOSE_HAS_PATTERN", f"{path}.pattern", "停工不得同时声明增加时段")
        elif action in {"ADD", "REPLACE"}:
            _pattern(exception.get("pattern"), f"{path}.pattern", errors,
                     restriction=restriction, target=target)
    return facts


def _phase(value, path, errors):
    value = _object(value, {"clock", "value", "unit", "basisReference", "standardDayMinutes",
                            "occupancy", "interruptible", "parallel"}, path, errors)
    clock = _enum_value(value.get("clock"), f"{path}.clock", errors)
    if clock in (None, "UNRESOLVED"):
        _issue(errors, "TIME_BASIS_UNRESOLVED", f"{path}.clock", "时间口径未明确，旧DAY原值保留，不自动换分钟", incomplete=True)
    elif clock not in {"RESOURCE_WORK_TIME", "ELAPSED_TIME", "STANDARD_CAPACITY_DAY"}:
        _issue(errors, "INVALID_TIME_BASIS", f"{path}.clock", "未知时间口径")
    quantity = _number(value.get("value"), f"{path}.value", errors)
    unit = _enum_value(value.get("unit"), f"{path}.unit", errors)
    if unit not in {"MINUTE", "DAY"}:
        _issue(errors, "TIME_UNIT_REQUIRED", f"{path}.unit", "请明确分钟或DAY原值", incomplete=unit is None)
    if (_required(value.get("basisReference"), f"{path}.basisReference", errors)
            and not isinstance(value["basisReference"], str)):
        _issue(errors, "STRING_REQUIRED", f"{path}.basisReference", "时间依据必须为明确文本")
    occupancy = _enum_value(value.get("occupancy"), f"{path}.occupancy", errors)
    if occupancy not in {"WORK_CENTER", "WORK_TIME_ONLY", "WAIT_ONLY", "EXTERNAL_RESOURCE"}:
        _issue(errors, "OCCUPANCY_REQUIRED", f"{path}.occupancy", "请明确实际占用资源或仅等待", incomplete=occupancy is None)
    if occupancy == "WORK_TIME_ONLY" and clock not in {"RESOURCE_WORK_TIME", "STANDARD_CAPACITY_DAY"}:
        _issue(errors, "WORK_TIME_ONLY_REQUIRES_WORK_CLOCK", f"{path}.clock", "只累计工作时间必须使用正式工作时段，不能作为连续经过时间")
    interruptible = _boolean(value.get("interruptible"), f"{path}.interruptible", errors)
    parallel = _boolean(value.get("parallel"), f"{path}.parallel", errors)
    if parallel is True:
        _issue(errors, "PARALLEL_MODE_NOT_SUPPORTED", f"{path}.parallel", "本最小版本不支持无正式转出触发的并行转运", incomplete=True)
    if clock == "RESOURCE_WORK_TIME" and occupancy == "WAIT_ONLY":
        _issue(errors, "WORK_TIME_REQUIRES_RESOURCE", f"{path}.occupancy", "工作时间必须明确占用资源")
    if clock == "STANDARD_CAPACITY_DAY" and occupancy == "WAIT_ONLY":
        _issue(errors, "STANDARD_DAY_WAIT_MODE_NOT_SUPPORTED", f"{path}.occupancy", "标准日等待缺独立日历消费能力，不能当作连续经过时间", incomplete=True)
    if clock == "ELAPSED_TIME" and interruptible is True:
        _issue(errors, "ELAPSED_TIME_IS_CONTINUOUS", f"{path}.interruptible", "连续经过时间不能拆成工作分钟")
    if occupancy == "EXTERNAL_RESOURCE":
        _issue(errors, "EXTERNAL_RESOURCE_MODE_NOT_SUPPORTED", f"{path}.occupancy", "独立资源占用能力未开放，不能当作无占用", incomplete=True)
    minutes = None
    if quantity is not None and unit == "MINUTE" and clock in {"RESOURCE_WORK_TIME", "ELAPSED_TIME"}:
        minutes = quantity
    elif quantity is not None and unit == "DAY" and clock in {"STANDARD_CAPACITY_DAY", "ELAPSED_TIME"}:
        day_minutes = _number(value.get("standardDayMinutes"), f"{path}.standardDayMinutes", errors, positive=True)
        if clock == "ELAPSED_TIME" and day_minutes is not None and day_minutes != 1440:
            _issue(errors, "ELAPSED_DAY_MUST_BE_EXPLICIT_24_HOURS", f"{path}.standardDayMinutes", "连续日仅在正式明确24小时依据时按1440分钟换算")
        if day_minutes is not None:
            minutes = quantity * day_minutes
    elif clock not in (None, "UNRESOLVED") and unit in {"MINUTE", "DAY"}:
        _issue(errors, "TIME_UNIT_BASIS_MISMATCH", f"{path}.unit", "时间单位与明确口径不一致，不能隐含换算")
    return {"minutes": str(minutes) if minutes is not None else None, "clock": clock,
            "occupancy": occupancy, "interruptible": interruptible}


def _arrangement_summaries(kind, payload, facts, errors):
    """Present the existing server minute facts without changing their formula.

    These summaries describe a single maintained pattern, not effective resource
    availability or authority to confirm a policy.  Incomplete/invalid component
    input must not turn the parser's diagnostic zero into a successful readout.
    """
    patterns = payload.get("patterns")
    if not isinstance(patterns, dict):
        return []
    result = []
    for index, (name, pattern) in enumerate(patterns.items(), 1):
        if not isinstance(name, str):
            continue
        path = f"$.patterns.{name}"
        summary = {"patternName": name, "patternLabel": f"工作安排{index}",
                   "sourcePath": path, "scope": "DRAFT_PATTERN_MINUTES_ONLY",
                   "ready": False, "processing": None, "resource": None, "errors": []}
        for component, label in (("processing", "净加工"), ("resource", "资源可用")):
            if component == "resource" and kind == "OPERATION_RESTRICTION":
                continue
            component_path = f"{path}.{component}"
            source = pattern.get(component) if isinstance(pattern, dict) else None
            statistics = facts.get("patterns", {}).get(name, {}).get(component)
            issues = deepcopy([item for item in errors
                               if item.get("path") in {"$", "$.patterns", path, component_path}
                               or item.get("path", "").startswith(component_path + ".")])
            if not isinstance(source, dict) or not isinstance(source.get("segments"), list) or not source["segments"]:
                _issue(issues, "ARRANGEMENT_SEGMENTS_REQUIRED", component_path + ".segments",
                       "请至少维护一段有效工作时段后再核算分钟。", incomplete=True)
            mode = source.get("inputMode") if isinstance(source, dict) else None
            mode = mode if isinstance(mode, str) else None
            ready = not issues and isinstance(statistics, dict) and mode in MODES
            minutes = statistics.get("netMinutes") if ready else None
            if ready:
                try:
                    count = Decimal(minutes)
                    ready = count.is_finite() and count >= 0 and count == count.to_integral_value()
                except (TypeError, ValueError, InvalidOperation):
                    ready = False
                if not ready:
                    _issue(issues, "ARRANGEMENT_MINUTES_UNAVAILABLE", component_path,
                           "本次服务端没有可核验的分钟结果。")
                    minutes = None
            hours = None
            if ready:
                hours, remainder = divmod(int(count), 60)
                hours = f"{hours}小时" + (f"{remainder}分钟" if remainder else "")
            deducted = statistics.get("deductedRestMinutes") if ready else None
            rest_text = (f"已扣休息{deducted}分钟，仅扣一次。" if mode == "WINDOWS_WITH_BREAKS"
                         else "已剔休息的工作段，不再扣休。") if ready else None
            summary[component] = {"ready": ready, "minutes": minutes, "hoursDisplay": hours,
                                  "displayText": f"{label}：{minutes}分钟（{hours}）" if ready else None,
                                  "inputMode": mode,
                                  "inputModeLabel": {"WINDOWS_WITH_BREAKS": "总班段＋休息",
                                                     "NET_WORK_SEGMENTS": "已剔休息的工作段"}.get(mode),
                                  "deductedRestMinutes": deducted, "restDisplayText": rest_text,
                                  "errors": issues}
            for item in issues:
                if item not in summary["errors"]:
                    summary["errors"].append(deepcopy(item))
        expected = ("processing",) if kind == "OPERATION_RESTRICTION" else ("processing", "resource")
        summary["ready"] = all(summary[key]["ready"] for key in expected)
        result.append(summary)
    return result


def normalize_policy_payload(kind, payload, *, strict=False):
    """Return copied typed JSON and useful draft diagnostics, without authority."""
    errors, warnings, facts = [], [], {}
    try:
        canonical = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError):
        canonical = {}
        _issue(errors, "JSON_VALUE_REQUIRED", "$", "内容必须是有限数值、字符串、布尔、数组或对象")
    kind = _enum_value(kind, "$.kind", errors)
    if kind not in KINDS:
        _issue(errors, "UNKNOWN_POLICY_KIND", "$", "未知制度配置类别")
    allowed = {
        "SHARED_ARRANGEMENT": {"timezone", "patterns", "weeklyPatterns", "exceptions"},
        "WC_APPLICATION": {"mode", "patterns", "weeklyPatterns", "exceptions"},
        "OPERATION_RESTRICTION": {"patterns", "weeklyPatterns", "exceptions", "interruptible", "minimumContinuousMinutes"},
        "CAPACITY_TIME_BASIS": {"standardDaySource", "standardPattern", "conversionMode", "linearApproved", "processing",
                                "preparation", "transfer", "standardCapacityHash", "businessBasis", "applicability", "approvalBasis"},
    }.get(kind, set())
    canonical = _object(canonical, allowed, "$", errors)
    if kind == "SHARED_ARRANGEMENT":
        _zone(canonical.get("timezone"), "$.timezone", errors)
        facts = _calendar_fields(canonical, errors)
    elif kind == "WC_APPLICATION":
        mode = _enum_value(canonical.get("mode"), "$.mode", errors)
        if mode not in {"INHERIT", "REPLACE_WORK_PATTERN"}:
            _issue(errors, "APPLICATION_MODE_REQUIRED", "$.mode", "请选择继承或明确替换", incomplete=mode is None)
        if mode == "INHERIT" and any(key in canonical for key in ("patterns", "weeklyPatterns")):
            _issue(errors, "INHERIT_HAS_REPLACEMENT", "$", "继承模式不能暗中替换基础周图")
        facts = _calendar_fields(canonical, errors, required=mode == "REPLACE_WORK_PATTERN")
    elif kind == "OPERATION_RESTRICTION":
        facts = _calendar_fields(canonical, errors, restriction=True, required=False)
        if "interruptible" in canonical:
            _boolean(canonical["interruptible"], "$.interruptible", errors)
        if "minimumContinuousMinutes" in canonical:
            _number(canonical["minimumContinuousMinutes"], "$.minimumContinuousMinutes", errors)
    elif kind == "CAPACITY_TIME_BASIS":
        source = _enum_value(canonical.get("standardDaySource"), "$.standardDaySource", errors)
        if source != "WORK_SYSTEM_REVISION":
            _issue(errors, "STANDARD_DAY_UNRESOLVED", "$.standardDaySource", "标准日必须指向明确正式制度版本/模式", incomplete=source in (None, "UNRESOLVED"))
        if (_required(canonical.get("standardPattern"), "$.standardPattern", errors)
                and not isinstance(canonical["standardPattern"], str)):
            _issue(errors, "STRING_REQUIRED", "$.standardPattern", "必须选择模式编码")
        mode = _enum_value(canonical.get("conversionMode"), "$.conversionMode", errors)
        if mode != "LINEAR_NET_MINUTES":
            _issue(errors, "MODE_NOT_SUPPORTED", "$.conversionMode", "未明确线性资格或所选非线性模式尚未开放，不能输出精确日期",
                   incomplete=mode in (None, "UNDETERMINED", "FIXED_PRODUCTION_DAY_QUOTA", "DISCRETE_BATCH"))
        if _boolean(canonical.get("linearApproved"), "$.linearApproved", errors) is False:
            _issue(errors, "LINEAR_CONVERSION_NOT_APPROVED", "$.linearApproved", "不能未经明确依据按工作分钟比例换算", incomplete=True)
        for key in ("businessBasis", "approvalBasis"):
            if _required(canonical.get(key), f"$.{key}", errors) and not isinstance(canonical[key], str):
                _issue(errors, "STRING_REQUIRED", f"$.{key}", "依据必须为明确文本")
        fingerprint = canonical.get("standardCapacityHash")
        if _required(fingerprint, "$.standardCapacityHash", errors) and (not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint)):
            _issue(errors, "INVALID_REFERENCE_HASH", "$.standardCapacityHash", "必须绑定实际标准产能内容Hash")
        if not isinstance(canonical.get("applicability"), dict) or not _meaningful_json(canonical.get("applicability")):
            _issue(errors, "APPLICABILITY_REQUIRED", "$.applicability", "请维护实际适用条件",
                   incomplete=canonical.get("applicability") is None or isinstance(canonical.get("applicability"), dict))
        processing = _object(canonical.get("processing"), {"interruptible", "minimumContinuousMinutes", "overtimeAllowed", "minDailyMinutes", "maxDailyMinutes"}, "$.processing", errors)
        _boolean(processing.get("interruptible"), "$.processing.interruptible", errors)
        _boolean(processing.get("overtimeAllowed"), "$.processing.overtimeAllowed", errors)
        for key in ("minimumContinuousMinutes", "minDailyMinutes", "maxDailyMinutes"):
            if key in processing:
                _number(processing[key], f"$.processing.{key}", errors)
        if "minDailyMinutes" in processing and "maxDailyMinutes" in processing:
            lower = _number(processing["minDailyMinutes"], "$.processing.minDailyMinutes", errors)
            upper = _number(processing["maxDailyMinutes"], "$.processing.maxDailyMinutes", errors)
            if lower is not None and upper is not None and lower > upper:
                _issue(errors, "INVALID_DAILY_RANGE", "$.processing.maxDailyMinutes", "上限不能小于下限")
        facts = {name: _phase(canonical.get(name), f"$.{name}", errors) for name in ("preparation", "transfer")}
    if kind in {"SHARED_ARRANGEMENT", "WC_APPLICATION", "OPERATION_RESTRICTION"}:
        facts["arrangementSummaries"] = _arrangement_summaries(kind, canonical, facts, errors)
    return {"contractVersion": CONTRACT, "payload": canonical, "facts": facts,
            "errors": errors, "warnings": warnings, "ready": not errors, "strict": bool(strict)}


def _local_instant(day, minute, zone, fold, path, errors):
    naive = datetime.combine(day, time()) + timedelta(minutes=minute)
    candidates = []
    for chosen in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=chosen)
        if aware.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == naive:
            candidates.append(aware)
    if not candidates:
        _issue(errors, "NONEXISTENT_LOCAL_TIME", path, "该本地时刻不存在，请修正跨日或夏令时安排")
        return None
    ambiguous = len({item.utcoffset() for item in candidates}) > 1
    if ambiguous and fold is None:
        _issue(errors, "AMBIGUOUS_LOCAL_TIME", path, "该本地时刻重复，必须明确选择前一次或后一次")
        return None
    return naive.replace(tzinfo=zone, fold=fold or 0).astimezone(UTC)


def _actual_arrangement(value, day, zone, path, errors):
    """Convert each original boundary before subtracting, including DST folds."""
    spans = {}
    for key in ("segments", "breaks"):
        spans[key] = []
        for index, row in enumerate(value.get(key, [])):
            point = f"{path}.{key}[{index}]"
            parsed = _segment(row, point, errors)
            if parsed is None:
                continue
            start = _local_instant(day, parsed[0], zone, row.get("startFold"), point + ".start", errors)
            end = _local_instant(day, parsed[1], zone, row.get("endFold"), point + ".end", errors)
            if start is not None and end is not None:
                if end <= start:
                    _issue(errors, "INVALID_ACTUAL_INTERVAL", point, "时区换算后结束不晚于开始")
                else:
                    spans[key].append((start, end))
    result = _merge(spans["segments"])
    if value.get("inputMode") == "WINDOWS_WITH_BREAKS":
        result = _subtract(result, spans["breaks"])
    return [(a, b, day.isoformat(), (path,)) for a, b in result]


def _clip(rows, start, end):
    return [(max(a, start), min(b, end), label, paths) for a, b, label, paths in rows
            if max(a, start) < min(b, end)]


def _remove(rows, cuts, *, production_date=None):
    result = []
    for start, end, label, paths in rows:
        if production_date is not None and label != production_date:
            result.append((start, end, label, paths))
        else:
            result.extend((a, b, label, paths) for a, b in _subtract([(start, end)], cuts))
    return result


def _intersect_rows(rows, windows):
    merged = _merge((a, b) for a, b, *_ in windows)
    return [(a, b, label, paths) for start, end, label, paths in rows
            for a, b in _intersect([(start, end)], merged)]


def _day_bounds(day, zone, errors, path):
    start = _local_instant(day, 0, zone, None, path + ".start", errors)
    end = _local_instant(day + timedelta(days=1), 0, zone, None, path + ".end", errors)
    return start, end


def _exceptions(rows, exceptions, component, zone, errors, prefix):
    result, closed = list(rows), []
    for index, item in enumerate(exceptions):
        if item.get("target") not in {component.upper(), "BOTH"}:
            continue
        path = f"{prefix}.exceptions[{index}]"
        day = _date(item.get("date"), path + ".date", errors)
        if day is None:
            continue
        lower, upper = _day_bounds(day, zone, errors, path)
        if lower is None or upper is None:
            continue
        production = item.get("dateBasis") == "PRODUCTION_DAY"
        selected = [(a, b) for a, b, label, _ in result if label == day.isoformat()] if production else [(lower, upper)]
        if item.get("action") in {"CLOSE", "REPLACE"}:
            result = _remove(result, selected, production_date=day.isoformat() if production else None)
        if item.get("action") == "CLOSE":
            if production:
                closed.append((None, None, day.isoformat()))
            else:
                closed.append((lower, upper, None))
        elif item.get("action") in {"ADD", "REPLACE"}:
            arrangement = item.get("pattern", {}).get(component)
            if arrangement:
                added = _actual_arrangement(arrangement, day, zone, path + ".pattern." + component, errors)
                result.extend(added if production else _clip(added, lower, upper))
    # CLOSE remains a hard exclusion even after a later ADD/REPLACE layer.
    for lower, upper, label in closed:
        result = ([row for row in result if row[2] != label] if label is not None else
                  _remove(result, [(lower, upper)]))
    return result, closed


def _check_ownership(rows, errors, path):
    previous = None
    for row in sorted(rows):
        if previous is not None and row[0] < previous[1]:
            _issue(errors, "RESOURCE_INTERVAL_OVERLAP", path,
                   "同一资源有重复时段或多个生产日归属，不能重复计时")
        if previous is None or row[1] > previous[1]:
            previous = row


def _minutes(start, end):
    delta = end - start
    microseconds = delta.days * 86400000000 + delta.seconds * 1000000 + delta.microseconds
    return Decimal(microseconds) / Decimal(60000000)


def _serialize(rows, zone):
    return [{"start": a.astimezone(zone).isoformat(), "end": b.astimezone(zone).isoformat(),
             "productionDate": label, "sourcePaths": list(paths)} for a, b, label, paths in sorted(rows)]


def _rollups(processing, resource, zone, errors):
    natural, production = {}, {}
    for name, rows in (("processingMinutes", processing), ("resourceMinutes", resource)):
        for start, end, label, _ in rows:
            bucket = production.setdefault(label, {"processingMinutes": Decimal(0), "resourceMinutes": Decimal(0)})
            bucket[name] += _minutes(start, end)
            current = start
            while current < end:
                current_day = current.astimezone(zone).date()
                _, midnight = _day_bounds(current_day, zone, errors, "$.naturalDays")
                if midnight is None or midnight <= current:
                    break
                stop = min(end, midnight)
                bucket = natural.setdefault(current_day.isoformat(), {"processingMinutes": Decimal(0), "resourceMinutes": Decimal(0)})
                bucket[name] += _minutes(current, stop)
                current = stop
    return ({key: {name: str(value) for name, value in row.items()} for key, row in natural.items()},
            {key: {name: str(value) for name, value in row.items()} for key, row in production.items()})


def _expand(payload, start, end, zone, errors, prefix):
    result = {"processing": [], "resource": []}
    # Prior production days participate in a natural-date range, including carry-in.
    current = start - timedelta(days=2)
    while current <= end:
        name = payload.get("weeklyPatterns", {}).get(WEEKDAYS[current.weekday()])
        pattern = payload.get("patterns", {}).get(name, {})
        for component in result:
            if component in pattern:
                result[component].extend(_actual_arrangement(pattern[component], current, zone,
                    f"{prefix}.patterns.{name}.{component}", errors))
        current += timedelta(days=1)
    closures = {}
    for component in result:
        result[component], closures[component] = _exceptions(result[component], payload.get("exceptions", []),
            component, zone, errors, prefix)
    return result, closures


def expand_calendar_window(payload, *, start_date, end_date, company_id, work_center_id):
    """Expand one shared arrangement; not a resource/source authorization."""
    return resolve_time_window(payload, start_date=start_date, end_date=end_date,
                               company_id=company_id, work_center_id=work_center_id)


def preview_arrangement_pattern(payload, *, pattern_name, production_date):
    """Observe one explicitly selected draft pattern, never effective WC facts.

    Weekly selection, exceptions, resource assignment and revision authority are
    deliberately outside this observation.  No real resource identity is made up.
    Other incomplete draft fields remain visible in errors while valid selected
    pattern calculations can be displayed as draft-derived facts.
    """
    checked = normalize_policy_payload("SHARED_ARRANGEMENT", payload)
    errors, local_errors = deepcopy(checked["errors"]), []
    zone = _zone(checked["payload"].get("timezone"), "$.timezone", local_errors)
    day = _date(production_date, "$.productionDate", local_errors)
    if day is not None and day > date.max - timedelta(days=3):
        _issue(local_errors, "INVALID_PREVIEW_WINDOW", "$.productionDate", "日期无法安全表示跨日结束边界")
    selected = None
    patterns = checked["payload"].get("patterns")
    if isinstance(pattern_name, str) and isinstance(patterns, dict):
        selected = patterns.get(pattern_name)
    if not isinstance(selected, dict):
        _issue(local_errors, "PATTERN_REQUIRED", "$.patternName", "请明确选择本草稿中存在的工作模式", incomplete=True)
    else:
        _pattern(selected, f"$.patterns.{pattern_name}", local_errors)
    output = {"contractVersion": CONTRACT, "factSource": "pure_draft_pattern_calculation",
              "inputAuthority": "DRAFT_FORM", "isEffectivePolicyProof": False, "patternOnly": True,
              "patternName": pattern_name, "productionDate": day.isoformat() if day else None,
              "timezone": checked["payload"].get("timezone"), "resourceIntervals": [], "processingIntervals": [],
              "naturalDays": {}, "productionDays": {}, "errors": errors, "warnings": [],
              "ready": False, "patternCalculationReady": False, "businessWriteCount": 0,
              "actualConflictCheck": "NOT_EXECUTED"}
    for item in local_errors:
        if item not in errors:
            errors.append(item)
    if local_errors or zone is None or day is None:
        return output
    rows = {}
    for component in ("processing", "resource"):
        rows[component] = _actual_arrangement(selected[component], day, zone,
            f"$.patterns.{pattern_name}.{component}", local_errors)
    natural, production = _rollups(rows["processing"], rows["resource"], zone, local_errors)
    for item in local_errors:
        if item not in errors:
            errors.append(item)
    if local_errors:
        return output
    output.update(resourceIntervals=_serialize(rows["resource"], zone),
                  processingIntervals=_serialize(rows["processing"], zone),
                  naturalDays=natural, productionDays=production,
                  patternCalculationReady=True, ready=not errors)
    return output


def resolve_time_window(shared, *, center=None, restrictions=(), start_date, end_date,
                        company_id, work_center_id, bookings=None):
    """Resolve configured processing/resource intervals without changing inputs."""
    checked = normalize_policy_payload("SHARED_ARRANGEMENT", shared, strict=True)
    errors, warnings = deepcopy(checked["errors"]), []
    start, end = _date(start_date, "$.startDate", errors), _date(end_date, "$.endDate", errors)
    if start and end and (end < start or (end - start).days > 366):
        _issue(errors, "INVALID_PREVIEW_WINDOW", "$.endDate", "预览窗口必须顺序有效且不超过367个自然日")
    if start and end and (start < date.min + timedelta(days=2) or end > date.max - timedelta(days=3)):
        _issue(errors, "INVALID_PREVIEW_WINDOW", "$.endDate", "预览窗口超出可安全表示跨日边界的日期范围")
    if type(company_id) is not int or company_id <= 0 or type(work_center_id) is not int or work_center_id <= 0:
        _issue(errors, "RESOURCE_SCOPE_REQUIRED", "$", "必须提供准确公司与工作中心范围")
    zone = _zone(checked["payload"].get("timezone"), "$.timezone", errors)
    center = deepcopy(center) if center is not None else None
    if center is not None:
        errors.extend(normalize_policy_payload("WC_APPLICATION", center, strict=True)["errors"])
    restrictions = deepcopy(list(restrictions))
    for restriction in restrictions:
        errors.extend(normalize_policy_payload("OPERATION_RESTRICTION", restriction, strict=True)["errors"])
    output = {"contractVersion": CONTRACT, "factSource": "pure_supplied_input_calculation",
              "companyId": company_id, "workCenterId": work_center_id,
              "timezone": checked["payload"].get("timezone"), "resourceIntervals": [],
              "processingIntervals": [], "naturalDays": {}, "productionDays": {},
              "errors": errors, "warnings": warnings, "ready": False, "businessWriteCount": 0,
              "configuredProductionDays": {}, "operationConstraints": {},
              "actualConflictCheck": "NOT_EXECUTED"}
    if errors:
        return output
    selected = checked["payload"]
    if center and center.get("mode") == "REPLACE_WORK_PATTERN":
        selected = {**selected, "patterns": center["patterns"], "weeklyPatterns": center["weeklyPatterns"]}
    expanded, hard_closures = _expand(selected, start, end, zone, errors, "$.shared")
    if center:
        for component in expanded:
            expanded[component], more_closures = _exceptions(expanded[component], center.get("exceptions", []),
                component, zone, errors, "$.center")
            hard_closures[component].extend(more_closures)
    for component in expanded:
        for lower, upper, label in hard_closures[component]:
            expanded[component] = ([row for row in expanded[component] if row[2] != label]
                if label is not None else _remove(expanded[component], [(lower, upper)]))
        _check_ownership(expanded[component], errors, f"$.{component}Intervals")
    processing = _intersect_rows(expanded["processing"], expanded["resource"])
    for index, restriction in enumerate(restrictions):
        if "weeklyPatterns" in restriction:
            allowed, _ = _expand(restriction, start, end, zone, errors, f"$.restrictions[{index}]")
            processing = _intersect_rows(processing, allowed["processing"])
        else:
            allowed, _ = _exceptions(expanded["processing"], restriction.get("exceptions", []), "processing", zone,
                                     errors, f"$.restrictions[{index}]")
            processing = _intersect_rows(processing, allowed)
        # A restriction is never permitted to open time outside either resource
        # availability or the original configured processing graph.
        processing = _intersect_rows(processing, expanded["processing"])
        processing = _intersect_rows(processing, expanded["resource"])
    lower = _local_instant(start, 0, zone, None, "$.startDate", errors)
    upper = _local_instant(end + timedelta(days=1), 0, zone, None, "$.endDate", errors)
    if lower is None or upper is None:
        return output
    resource = _clip(expanded["resource"], lower, upper)
    processing = _clip(processing, lower, upper)
    _, configured_days = _rollups(processing, resource, zone, errors)
    operation_constraints = {"interruptible": None, "minimumContinuousMinutes": "0"}
    for restriction in restrictions:
        if restriction.get("interruptible") is False:
            operation_constraints["interruptible"] = False
        minimum = Decimal(str(restriction.get("minimumContinuousMinutes", "0")))
        operation_constraints["minimumContinuousMinutes"] = str(max(minimum,
            Decimal(operation_constraints["minimumContinuousMinutes"])))
    occupied = _read_bookings(bookings, company_id, work_center_id, errors)
    resource = _remove(resource, [(a, b) for a, b, *_ in occupied])
    processing = _remove(processing, [(a, b) for a, b, *_ in occupied])
    natural, production = _rollups(processing, resource, zone, errors)
    output.update(resourceIntervals=_serialize(resource, zone), processingIntervals=_serialize(processing, zone),
                  naturalDays=natural, productionDays=production, configuredProductionDays=configured_days,
                  operationConstraints=operation_constraints, ready=not errors)
    return output


def _instant(value, path, errors):
    try:
        result = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(UTC)
    except (TypeError, ValueError):
        _issue(errors, "AWARE_DATETIME_REQUIRED", path, "必须提供带业务时区偏移的准确时刻")
        return None


def _read_intervals(rows, path, errors):
    result = []
    if not isinstance(rows, list):
        _issue(errors, "LIST_REQUIRED", path, "时段必须为列表")
        return result
    for index, row in enumerate(rows):
        point = f"{path}[{index}]"
        if not isinstance(row, dict):
            _issue(errors, "OBJECT_REQUIRED", point, "时段必须为对象")
            continue
        start, end = _instant(row.get("start"), point + ".start", errors), _instant(row.get("end"), point + ".end", errors)
        if start and end and start < end:
            result.append((start, end, row.get("productionDate", start.date().isoformat()), tuple(row.get("sourcePaths", [point]))))
        elif start and end:
            _issue(errors, "INVALID_INTERVAL", point, "结束必须晚于开始")
    _check_ownership(result, errors, path)
    return result


def _read_bookings(bookings, company_id, work_center_id, errors):
    if bookings is None:
        return []
    if not isinstance(bookings, dict):
        _issue(errors, "INVALID_BOOKINGS", "$.bookings", "请求内占用必须为按公司和实际工作中心分区的对象")
        return []
    return _read_intervals(bookings.get(f"{company_id}:{work_center_id}", []), "$.bookings", errors)


def convert_capacity_time(*, demand_quantity, capacity_quantity, basis, standard_day_minutes=None):
    """Convert only an explicit qualified basis; retain theoretical DAY demand."""
    checked = normalize_policy_payload("CAPACITY_TIME_BASIS", basis, strict=True)
    errors = deepcopy(checked["errors"])
    demand = _number(demand_quantity, "$.demandQuantity", errors, positive=True)
    capacity = _number(capacity_quantity, "$.capacityQuantity", errors, positive=True)
    minutes = _number(standard_day_minutes, "$.standardDayMinutes", errors, positive=True)
    days = demand / capacity if demand is not None and capacity is not None else None
    return {"contractVersion": CONTRACT, "ready": not errors, "errors": errors,
            "productionStandardDays": str(days) if days is not None else None,
            "processingMinutes": str(days * minutes) if not errors else None,
            "preparation": deepcopy(checked["facts"].get("preparation")),
            "transfer": deepcopy(checked["facts"].get("transfer")), "businessWriteCount": 0}


def _duration_delta(minutes):
    microseconds = (minutes * Decimal(60000000)).to_integral_value(rounding=ROUND_CEILING)
    return timedelta(microseconds=int(microseconds))


def _consume(rows, duration, earliest, interruptible, *, minimum=Decimal(0)):
    remaining, allocations = duration, []
    if duration == 0:
        return allocations, earliest
    if minimum > duration:
        return None, None
    for start, end, label, paths in sorted(rows):
        start = max(start, earliest)
        if start >= end:
            continue
        available = _minutes(start, end)
        if not interruptible and available < remaining or available < min(minimum, remaining):
            continue
        amount = min(available, remaining)
        if minimum > 0 and amount < minimum:
            continue
        stop = min(end, start + _duration_delta(amount))
        allocations.append((start, stop, label, paths))
        remaining -= amount
        if remaining <= 0:
            return allocations, stop
    return None, None


def preview_operation_time(window, *, demand_quantity, capacity_quantity, basis, standard_day_minutes,
                           not_before, company_id, work_center_id, bookings=None):
    """Stage a single-step sequential preview; publish no partial occupancy.

    A successful caller may pass the returned bookings to its next step.  The
    original bookings and all input payloads remain untouched on success/failure.
    """
    converted = convert_capacity_time(demand_quantity=demand_quantity, capacity_quantity=capacity_quantity,
                                      basis=basis, standard_day_minutes=standard_day_minutes)
    errors = deepcopy(converted["errors"])
    original_bookings = deepcopy(bookings) if isinstance(bookings, dict) else {}
    output = {**converted, "ready": False, "phases": [], "start": None, "end": None,
              "bookings": original_bookings, "actualConflictCheck": "NOT_EXECUTED", "businessWriteCount": 0}
    if (type(company_id) is not int or type(work_center_id) is not int
            or type(window.get("companyId")) is not int or type(window.get("workCenterId")) is not int
            or window.get("companyId") != company_id or window.get("workCenterId") != work_center_id):
        _issue(errors, "RESOURCE_SCOPE_MISMATCH", "$", "计算窗口与当前公司/实际工作中心不一致")
    if window.get("ready") is not True:
        errors.extend(deepcopy(window.get("errors", [])))
        _issue(errors, "TIME_WINDOW_NOT_READY", "$", "实际资源及加工窗口尚未完整证明", incomplete=True)
    earliest = _instant(not_before, "$.notBefore", errors)
    zone = _zone(window.get("timezone"), "$.timezone", errors)
    resource = _read_intervals(window.get("resourceIntervals", []), "$.resourceIntervals", errors)
    processing = _read_intervals(window.get("processingIntervals", []), "$.processingIntervals", errors)
    occupied = _read_bookings(bookings, company_id, work_center_id, errors)
    if errors:
        output["errors"] = errors
        return output
    for row in window.get("configuredProductionDays", window.get("productionDays", {})).values():
        actual = Decimal(row["processingMinutes"])
        settings = basis.get("processing", {})
        if actual > Decimal(str(standard_day_minutes)) and settings.get("overtimeAllowed") is not True:
            _issue(errors, "OVERTIME_CAPACITY_NOT_APPROVED", "$.processing.overtimeAllowed", "增加的可用时间没有本项产能的加班适用依据，不能自动增产")
        if actual > 0 and any((name == "minDailyMinutes" and actual < Decimal(settings[name])) or
                (name == "maxDailyMinutes" and actual > Decimal(settings[name]))
                for name in ("minDailyMinutes", "maxDailyMinutes") if name in settings):
            _issue(errors, "DAILY_TIME_OUTSIDE_APPROVED_RANGE", "$.processing", "实际加工日时间超出明确适用范围")
    if errors:
        output["errors"] = errors
        return output
    current, staged, phases = earliest, list(occupied), []
    specs = (("preparation", converted["preparation"], basis["preparation"]),
             ("processing", {"minutes": converted["processingMinutes"], "clock": "RESOURCE_WORK_TIME", "occupancy": "WORK_CENTER"}, basis["processing"]),
             ("transfer", converted["transfer"], basis["transfer"]))
    for name, phase, settings in specs:
        duration = Decimal(phase["minutes"])
        previous = current
        if phase["occupancy"] == "WAIT_ONLY":
            if phase["clock"] != "ELAPSED_TIME":
                _issue(errors, "WAIT_REQUIRES_ELAPSED_TIME", f"$.{name}", "仅等待必须有明确连续经过时间依据")
                break
            allocations, current = [], current + _duration_delta(duration)
        else:
            available = processing if name == "processing" else resource
            if phase["occupancy"] != "WORK_TIME_ONLY":
                available = _remove(available, [(a, b) for a, b, *_ in staged])
            minimum = Decimal(settings.get("minimumContinuousMinutes", "0"))
            can_interrupt = settings["interruptible"]
            if name == "processing":
                constraints = window.get("operationConstraints", {})
                can_interrupt = can_interrupt and constraints.get("interruptible") is not False
                minimum = max(minimum, Decimal(constraints.get("minimumContinuousMinutes", "0")))
            allocations, current = _consume(available, duration, current,
                phase.get("clock") != "ELAPSED_TIME" and can_interrupt, minimum=minimum)
            if allocations is None:
                _issue(errors, "INSUFFICIENT_LEGAL_TIME_WINDOW", f"$.{name}", "合法资源窗口不足或无法满足连续作业，不延长开放时间")
                break
            if phase["occupancy"] != "WORK_TIME_ONLY":
                staged.extend(allocations)
        phases.append({"phase": name, **phase, "start": (allocations[0][0] if allocations else previous).astimezone(zone).isoformat(),
                       "end": current.astimezone(zone).isoformat(), "allocations": _serialize(allocations, zone),
                       "roundingMinutes": str((sum((_minutes(a, b) for a, b, *_ in allocations), Decimal(0))
                           if allocations else _minutes(previous, current)) - duration),
                       "countPolicy": "ONCE_PER_STEP"})
    if errors:
        output.update(errors=errors, phases=[], ready=False)
        return output
    committed = deepcopy(original_bookings)
    committed[f"{company_id}:{work_center_id}"] = _serialize(staged, zone)
    first_start = min((_instant(phase["start"], "$", []) for phase in phases if Decimal(phase["minutes"]) > 0), default=earliest)
    output.update(ready=True, errors=[], phases=phases, start=first_start.astimezone(zone).isoformat(),
                  end=current.astimezone(zone).isoformat(), bookings=committed)
    return output
