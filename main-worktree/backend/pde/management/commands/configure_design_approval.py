"""Explicit, reviewable deployment configuration. Default operation is read-only."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from pde.design_approval_configuration import configuration_plan,configure

class Command(BaseCommand):
    help='Plan design approval responsibilities; apply only against an exact reviewed target and plan hash.'
    def add_arguments(self,parser):
        parser.add_argument('--bindings',required=True)
        parser.add_argument('--apply',action='store_true')
        parser.add_argument('--expected-database')
        parser.add_argument('--plan-hash')
    def handle(self,*args,**options):
        try:
            config=json.loads(Path(options['bindings']).read_text(encoding='utf-8-sig'))
            plan=configuration_plan(company_id=config['companyId'],bindings=config['bindings'])
            if options['apply']:
                if not options['expected_database'] or not options['plan_hash']:
                    raise RuntimeError('Apply requires --expected-database and --plan-hash from the reviewed read-only plan.')
                configure(company_id=config['companyId'],bindings=config['bindings'],expected_database=options['expected_database'],expected_plan_hash=options['plan_hash'])
            self.stdout.write(json.dumps({'applied':options['apply'],'plan':plan},ensure_ascii=True,indent=2))
        except Exception as error:
            raise CommandError(str(error)) from error
