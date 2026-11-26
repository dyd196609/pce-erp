"""Read-only presentation of persisted calculation records, never eligibility."""

READBACK_CONTRACT = "PDE-FORMAL-CALCULATION-READBACK-V1"


def summarize_formal_calculations(*, company_id, lines, records):
    """Keep company/line/instance/source identities exact; do not infer from previews.

    Callers must supply a successful persisted query. None is not an empty result.
    Completion here says a record exists, not that a new execution is authorized.
    """
    if records is None:
        raise ValueError("Persisted calculation records must be read successfully")
    states = {}
    total_records = total_completed = saved_lines = 0
    for line in lines:
        matches = [row for row in records if (
            row["companyId"] == company_id
            and row["scope"] == "order_engineering"
            and row["salesOrderItemId"] == line["salesOrderItemId"]
            and line.get("orderEngineeringInstanceId") is not None
            and row["orderEngineeringInstanceId"] == line["orderEngineeringInstanceId"]
            and row["sourceRecordId"] == line.get("sourceRecordId")
        )]
        completed = sum(row["status"] == "completed" for row in matches)
        total_records += len(matches)
        total_completed += completed
        saved_lines += bool(completed)
        code = "SAVED" if completed else "RECORDS_PRESENT" if matches else "NOT_SAVED"
        label = (f"已保存正式核算（{completed}份已完成）" if completed else
                 "已有正式记录，尚无已完成结果" if matches else "正式核算尚未保存")
        states[line["salesOrderItemId"]] = {
            "contractVersion": READBACK_CONTRACT, "code": code, "label": label,
            "recordCount": len(matches), "completedRecordCount": completed,
            "records": matches, "factSource": "server", "isPrerequisiteBlocker": False,
            "explanation": "来自当前公司、订单行、实例及来源的正式持久化记录；不代表本次新执行已获批准。",
        }
    if saved_lines == len(lines) and lines:
        code, label = "SAVED", f"本订单{saved_lines}/{len(lines)}行已保存正式核算"
    elif saved_lines:
        code, label = "PARTIALLY_SAVED", f"本订单{saved_lines}/{len(lines)}行已保存正式核算"
    elif total_records:
        code, label = "RECORDS_PRESENT", "本订单已有正式记录，尚无已完成结果"
    else:
        code, label = "NOT_SAVED", "正式核算尚未保存"
    return states, {
        "contractVersion": READBACK_CONTRACT, "code": code, "label": label,
        "recordCount": total_records, "completedRecordCount": total_completed,
        "savedLineCount": saved_lines, "lineCount": len(lines),
        "factSource": "server", "isPrerequisiteBlocker": False,
        "explanation": "按本订单各行正式持久化记录汇总；预检通过、来源预览和实例状态均不代替已保存记录。",
    }
