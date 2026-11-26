"""Explicit package-driven classified facts and native EOR, with a partial gate."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from system.models import User
from pde.manufacturing_fact_batch_service import ManufacturingFactBatchService
from pde.operation_requirement_service import OperationRequirementError


class Command(BaseCommand):
    help = '按正式分类汇总配置承接既有事实与EOR，并回读分类投产数量'

    def add_arguments(self, parser):
        parser.add_argument('--fact-file', required=True)
        parser.add_argument('--manufacturing-file', required=True)
        parser.add_argument('--actor', type=int)
        parser.add_argument('--reason', default='')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--allow-partial', action='store_true')
        parser.add_argument('--source-calculation', type=int, action='append', default=[])
        parser.add_argument('--request-key', default='')

    def handle(self, *args, **options):
        facts = json.loads(Path(options['fact_file']).read_text(encoding='utf-8-sig'))
        manufacturing = json.loads(Path(options['manufacturing_file']).read_text(encoding='utf-8-sig'))
        if not options['apply']:
            result = {'mode': 'ZERO_WRITE_PACKAGE_INSPECTION', 'factRuleCount': len(facts['rules']),
                'manufacturingRuleCount': len(manufacturing['rules']), 'businessWriteCount': 0, 'auditWriteCount': 0}
        else:
            if (not options['actor'] or not options['reason'].strip() or not options['request_key'].strip()
                    or not options['source_calculation']):
                raise CommandError('正式承接必须提供actor、reason、request-key及原核算ID')
            user = User.objects.get(pk=options['actor'], is_active=True)
            try:
                result = ManufacturingFactBatchService.execute(user=user, fact_package=facts,
                    manufacturing_package=manufacturing, source_calculation_ids=options['source_calculation'],
                    request_key=options['request_key'], reason=options['reason'], allow_partial=options['allow_partial'])
            except OperationRequirementError as exc:
                raise CommandError(f'{exc.code}: {exc.message}') from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
