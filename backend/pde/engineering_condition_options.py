"""Shared governed semantics for engineering surface conditions.

These are a server-owned option provider, not a second master-data table.  The
stable codes are shared by product design and engineering calculation while
the Chinese value remains the calculation input snapshot.
"""

VISIBLE_CONDITION_OPTIONS = (
    {"id": "VISIBLE-SINGLE", "code": "SINGLE_FACE", "name": "单", "statusLabel": "单面见光"},
    {"id": "VISIBLE-DOUBLE", "code": "DOUBLE_FACE", "name": "双", "statusLabel": "双面见光"},
    {"id": "VISIBLE-UNFINISHED", "code": "UNFINISHED", "name": "白坯", "statusLabel": "白坯，不计见光面"},
    {"id": "VISIBLE-NONE", "code": "EXPLICIT_NONE", "name": "明确无", "statusLabel": "已明确无见光要求"},
    {"id": "VISIBLE-NA", "code": "NOT_APPLICABLE", "name": "不适用", "statusLabel": "本结构不适用"},
    {"id": "VISIBLE-UNKNOWN", "code": "UNKNOWN", "name": "未知", "statusLabel": "尚未确认"},
)

VISIBLE_CONDITION_BY_CODE = {row["code"]: row for row in VISIBLE_CONDITION_OPTIONS}
VISIBLE_CONDITION_BY_NAME = {row["name"]: row for row in VISIBLE_CONDITION_OPTIONS}


def visible_condition_options():
    return [dict(row) for row in VISIBLE_CONDITION_OPTIONS]


def normalize_visible_condition(*, code=None, value=None, allow_blank=True):
    text_code = str(code or "").strip()
    text_value = str(value or "").strip()
    if not text_code and not text_value and allow_blank:
        return None
    option = VISIBLE_CONDITION_BY_CODE.get(text_code) or VISIBLE_CONDITION_BY_NAME.get(text_value)
    if not option:
        raise ValueError("VISIBLE_CONDITION_INVALID")
    return dict(option)


def visible_condition_multiplier(value):
    option = VISIBLE_CONDITION_BY_NAME.get(str(value or "").strip())
    if not option:
        return None
    return {"SINGLE_FACE": 1, "DOUBLE_FACE": 2, "UNFINISHED": 0}.get(option["code"])
