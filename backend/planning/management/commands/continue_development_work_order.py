"""Append a qualified correction plan without rewriting frozen business rows."""
import json
from django.core.management.base import BaseCommand,CommandError
from system.models import User
from planning.work_order_models import ProductionWorkOrder
from planning.operation_continuation_service import record_route_plan

class Command(BaseCommand):
    help='Append audited continuation for an explicitly development-excluded frozen route; no task dispatch or historical replay.'
    def add_arguments(self,parser):
        for key in ('work-order','actor','expected-snapshot-hash','idempotency-key','reason'):
            parser.add_argument('--'+key,required=True)
    def handle(self,*args,**options):
        try:
            actor=User.objects.get(username=options['actor'],is_active=True)
            order=ProductionWorkOrder.objects.get(company_id=actor.company_id,no=options['work_order'])
            if order.snapshot_hash!=options['expected_snapshot_hash']:
                raise CommandError('Work-order snapshot changed; read current facts before correction.')
            result,created=record_route_plan(user=actor,work_order=order,payload={
                'idempotencyKey':options['idempotency_key'],'reason':options['reason']})
        except CommandError:raise
        except Exception as exc:raise CommandError(str(getattr(exc,'code','ERROR'))+': '+str(exc)) from exc
        self.stdout.write(json.dumps({'created':created,'result':result},ensure_ascii=False,default=str))
