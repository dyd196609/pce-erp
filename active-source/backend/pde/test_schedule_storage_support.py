"""Inspect persisted scheduling contracts, never infer absence from ORM loading."""
from django.db import connection

def inspect_storage(company_id):
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        table = 'planning_formal_production_schedule'
        if table not in tables:
            columns = {}
        else:
            columns = {x.name:x for x in connection.introspection.get_table_description(cursor,table)}
        blockers = []
        if not columns:
            blockers.append('数据库缺少原排程主表，不能保存。')
        else:
            if 'usage_purpose' not in columns:
                blockers.append('原排程主表没有持久用途字段，不能可靠区分测试与正式排程。')
            if 'execution_arrangement_id' not in columns:
                blockers.append('原排程主表没有订单安排来源关联，不能约束安排修订及有效结果唯一性。')
            if 'production_plan_id' in columns and not columns['production_plan_id'].null_ok:
                blockers.append('production_plan_id为非空正式生产计划外键；本单测试安排不能冒用正式计划。')
        counts = {}
        for name in ('planning_formal_production_schedule','planning_processing_reservation'):
            if name not in tables:
                counts[name] = None
            else:
                cursor.execute('SELECT COUNT(*) FROM '+name+' WHERE company_id=%s', [company_id])
                counts[name] = cursor.fetchone()[0]
    return {'contractVersion':'PCE-TEST-SCHEDULE-STORAGE-SUPPORT-V2','factSource':'server',
        'structureReady':not blockers,'blockers':blockers,
        'existingScheduleCount':counts['planning_formal_production_schedule'],
        'existingReservationCount':counts['planning_processing_reservation'],
        'databaseBusinessWriteCount':0,
        'statusLabel':'测试用途与安排来源结构已就绪；动作权限由测试排程服务独立核验' if not blockers else '测试保存结构缺项'}
