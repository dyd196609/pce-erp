"""Atomic explicit resource correction, released rule package and EOR generation."""
from copy import deepcopy
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from system.models import User
from pde.models import StandardCapacity
from pde.manufacturing_resource_configuration_service import ManufacturingResourceConfigurationService
from pde.manufacturing_configuration_service import ManufacturingConfigurationService


class Command(BaseCommand):
    help = '根据正式配置修正工序计量、补产能、发布新版本并承接固定事实生成EOR'

    def add_arguments(self, parser):
        parser.add_argument('--resource-file', required=True)
        parser.add_argument('--rule-file', required=True)
        parser.add_argument('--actor', type=int)
        parser.add_argument('--reason', default='')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--source-calculation', type=int, action='append', default=[])
        parser.add_argument('--request-key', default='')

    @transaction.atomic
    def handle(self, *args, **options):
        resources = json.loads(Path(options['resource_file']).read_text(encoding='utf-8-sig'))
        rules = json.loads(Path(options['rule_file']).read_text(encoding='utf-8-sig'))
        if not options['apply']:
            result = {'mode': 'ZERO_WRITE_PACKAGE_INSPECTION',
                'operationCorrectionCount': len(resources.get('operationCorrections', [])),
                'capacityCount': len(resources.get('capacities', [])), 'ruleCount': len(rules.get('rules', [])),
                'businessWriteCount': 0, 'auditWriteCount': 0}
        else:
            if (not options['actor'] or not options['reason'].strip() or not options['request_key'].strip()
                or not options['source_calculation']):
                raise CommandError('正式办理必须提供actor、reason、request-key及原工程核算ID')
            user = User.objects.get(pk=options['actor'], is_active=True)
            resource_result = ManufacturingResourceConfigurationService.configure(user=user, package=resources, reason=options['reason'])
            rules = deepcopy(rules)
            for row in rules['rules']:
                config = row['specification']['manufacturing']
                code = config.pop('standardCapacityCode', None)
                if code:
                    config['standardCapacityId'] = StandardCapacity.objects.get(company_id=user.company_id, code=code).pk
            configured = ManufacturingConfigurationService.configure(user=user, package=rules, reason=options['reason'])
            ids = [r['id'] for r in configured['rules']]
            generations = []
            for pk in options['source_calculation']:
                generated = ManufacturingConfigurationService.generate_for_calculation(user=user,
                    source_calculation_id=pk, request_key=options['request_key'], reason=options['reason'], rule_ids=ids)
                if generated['blockers']:
                    raise CommandError(json.dumps(generated['blockers'], ensure_ascii=False))
                generations.append(generated)
            result = {'resources': resource_result, 'rules': configured, 'generations': generations,
                'factSource': 'server', 'productionPlanWriteCount': 0}
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
