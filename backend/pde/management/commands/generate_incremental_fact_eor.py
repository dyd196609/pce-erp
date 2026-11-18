"""Atomic package-driven incremental facts then sole formal EOR generator."""
from copy import deepcopy
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from system.models import User
from pde.models import EngineeringRuleDefinition
from pde.engineering_fact_extension_service import EngineeringFactExtensionService
from pde.manufacturing_configuration_service import ManufacturingConfigurationService


class Command(BaseCommand):
    help = '发布增量事实与制造规则配置，按固定原核算生成正式事实与EOR'

    def add_arguments(self, parser):
        parser.add_argument('--fact-file', required=True)
        parser.add_argument('--manufacturing-file', required=True)
        parser.add_argument('--actor', type=int)
        parser.add_argument('--reason', default='')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--source-calculation', type=int, action='append', default=[])
        parser.add_argument('--request-key', default='')

    @transaction.atomic
    def handle(self, *args, **options):
        package = json.loads(Path(options['fact_file']).read_text(encoding='utf-8-sig'))
        manufacturing = json.loads(Path(options['manufacturing_file']).read_text(encoding='utf-8-sig'))
        if not options['apply']:
            result = {'mode': 'ZERO_WRITE_PACKAGE_INSPECTION', 'factRuleCount': len(package['rules']),
                'manufacturingRuleCount': len(manufacturing['rules']), 'businessWriteCount': 0}
        else:
            if not options['actor'] or not options['reason'].strip() or not options['request_key'].strip():
                raise CommandError('正式写入必须指定actor、reason、request-key')
            if not options['source_calculation']:
                raise CommandError('必须明确指定原正式工程核算ID')
            user = User.objects.get(pk=options['actor'], is_active=True)
            configured = EngineeringFactExtensionService.configure(user=user, package=package, reason=options['reason'])
            manufacturing = deepcopy(manufacturing)
            for row in manufacturing['rules']:
                selector = row['specification']['manufacturing']['sourceSelector']
                code = selector.pop('producerRuleCode', None)
                if code:
                    producer = EngineeringRuleDefinition.objects.get(company_id=user.company_id,
                        rule_code=code, version=selector['producerRuleVersion'], status='released')
                    selector['producerRuleId'] = producer.pk
            resources = ManufacturingConfigurationService.configure(user=user, package=manufacturing, reason=options['reason'])
            runs = []
            for pk in options['source_calculation']:
                derived = EngineeringFactExtensionService.derive(user=user, source_calculation_id=pk,
                    rule_ids=configured['ruleIds'], idempotency_key=f"{options['request_key']}:{pk}", reason=options['reason'])
                generated = ManufacturingConfigurationService.generate_for_calculation(user=user,
                    source_calculation_id=derived['calculationId'], request_key=options['request_key'],
                    reason=options['reason'], rule_ids=[row['id'] for row in resources['rules']])
                if generated['blockers']:
                    raise CommandError(json.dumps(generated['blockers'], ensure_ascii=False))
                runs.append({'baseEngineeringCalculationId': pk, 'derivation': derived, 'generation': generated})
            result = {'factConfiguration': configured, 'manufacturingConfiguration': resources, 'runs': runs,
                'factSource': 'server', 'productionPlanWriteCount': 0}
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
