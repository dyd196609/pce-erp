"""Explicit package loading; default is a zero-write package inspection."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from system.models import User
from pde.manufacturing_configuration_service import ManufacturingConfigurationService


class Command(BaseCommand):
    help = '读取/发布正式制造模式与工序规则配置包，并按明确来源核算生成EOR'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--actor', type=int)
        parser.add_argument('--reason', default='')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--generate-calculation', type=int, action='append', default=[])
        parser.add_argument('--request-key', default='')

    def handle(self, *args, **options):
        package = json.loads(Path(options['file']).read_text(encoding='utf-8-sig'))
        if not options['apply']:
            result = {'mode': 'ZERO_WRITE_PACKAGE_INSPECTION', 'contractVersion': package.get('contractVersion'),
                'modes': len(package.get('modes', [])), 'rules': len(package.get('rules', [])),
                'pendingRules': package.get('pendingRules', []), 'businessWriteCount': 0}
        else:
            if not options['actor'] or not options['reason'].strip():
                raise CommandError('正式配置写入需要actor与reason')
            if options['generate_calculation'] and not options['request_key'].strip():
                raise CommandError('生成EOR需要非空request-key')
            user = User.objects.get(pk=options['actor'], is_active=True)
            result = ManufacturingConfigurationService.configure(user=user, package=package, reason=options['reason'])
            result['generations'] = [ManufacturingConfigurationService.generate_for_calculation(user=user,
                source_calculation_id=key, request_key=options['request_key'], reason=options['reason'])
                for key in options['generate_calculation']]
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
