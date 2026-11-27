"""Date projection after native MES validation; never part of proof snapshots."""
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .mes_test_source_bridge import execution_timezone
from .workshop_task_time import task_datetime_label


def task_date_facts(task, start, *, report_dates=None, completion=None):
    """Keep the frozen plan, occurrence and recording times distinct.

    This receives already verified objects. It performs no qualification and
    supplies no substitute date when a historical fact is absent. Completion's
    existing completedAtLabel is review effectiveness, not physical work end.
    """
    operation = task.source_snapshot.get('operation', {})
    zone = execution_timezone(task)
    facts = {
        'contractVersion': 'PCE-MES-TASK-DATE-FACTS-V1',
        'taskId': task.pk, 'workOrderId': task.work_order_id,
        'businessTimezone': zone,
        'plannedStartAt': operation.get('start'),
        'plannedCompletionAt': operation.get('end'),
        'planSource': 'task.source_snapshot.operation',
        'actualStartAt': start.started_at.isoformat() if start else None,
        'actualStartAtLabel': task_datetime_label(start.started_at, zone) if start else None,
        'startRecordedAt': start.created_at.isoformat() if start else None,
        'startRecordedAtLabel': task_datetime_label(start.created_at, zone) if start else None,
        'completionReviewEffectiveAtLabel': (
            completion.get('completedAtLabel') if completion and completion.get('statusCode') == 'completed' else None),
        'completionTimeMeaning': '原独立审核生效时点；不代表另行采集的现场物理完工时间',
        'physicalCompletionTimeSupported': False,
        'physicalCompletionAt': None,
    }
    if report_dates is not None:
        facts['reportEvents'] = [{
            'reportId': row['reportId'],
            'reportedAt': row['reportedAt'].isoformat(),
            'reportedAtLabel': task_datetime_label(row['reportedAt'], zone),
            'recordedAt': row['recordedAt'].isoformat(),
            'recordedAtLabel': task_datetime_label(row['recordedAt'], zone),
        } for row in report_dates]
    return facts


def _instant(value, *, stored=False):
    if not isinstance(value, str) or not value:
        return None
    try:
        instant = parse_datetime(value)
    except ValueError:
        return None
    if instant is None:
        return None
    if timezone.is_naive(instant):
        return timezone.make_aware(instant, timezone.get_default_timezone()) if stored else None
    return instant


def compare_task_start(dates, *, now=None):
    """Compare the frozen planned start only to the verified actual start."""
    expected = _instant(dates.get('plannedStartAt'))
    actual = _instant(dates.get('actualStartAt'), stored=True)
    result = {
        'plannedAt': dates.get('plannedStartAt'), 'actualAt': dates.get('actualStartAtLabel'),
        'planSourceLabel': '工序冻结排程', 'actualSourceLabel': '原正式开工记录',
        'isLate': False,
    }
    if expected is None:
        return dict(result, statusLabel='开工延期待核', reason='缺少带明确时区的冻结计划开工时间。')
    if actual is None:
        reference = now or timezone.now()
        if timezone.is_naive(reference):
            reference = timezone.make_aware(reference, timezone.get_default_timezone())
        passed = expected < reference
        message = '计划开工时间已过，缺少已核实的实际开工记录。' if passed else '缺少已核实的实际开工记录。'
        return dict(result, statusLabel='开工延期待核', reason=message)
    late = actual > expected
    return dict(result, isLate=late, statusLabel='开工延期' if late else '按时开工',
                reason='实际开工晚于冻结计划开工时间。' if late else '实际开工未晚于冻结计划开工时间。')


def task_timing_facts(dates, *, now=None):
    """An effective review or a warehouse receipt does not supply physical finish time."""
    planned = _instant(dates.get('plannedCompletionAt'))
    actual = _instant(dates.get('physicalCompletionAt'), stored=True)
    missing = []
    if planned is None:
        missing.append('带明确时区的冻结计划完成时间')
    if actual is None:
        missing.append('现场实际完工时间')
    result = {'plannedAt': dates.get('plannedCompletionAt'), 'actualAt': dates.get('physicalCompletionAt'),
              'planSourceLabel': '工序冻结排程', 'actualSourceLabel': '现场实际完工记录', 'isLate': False}
    if missing:
        result.update(statusLabel='完工延期待核', reason='缺少' + '、'.join(missing) + '。')
    else:
        late = actual > planned
        result.update(isLate=late, statusLabel='完工延期' if late else '按时完工',
                      reason='现场实际完工晚于冻结计划完成时间。' if late else '现场实际完工未晚于冻结计划完成时间。')
    return {'start': compare_task_start(dates, now=now), 'completion': result}
