import json
from django.core.management.base import BaseCommand, CommandError
from system.auth_state_continuation import preserve, AuthenticationContinuationError


class Command(BaseCommand):
    help = 'Preserve an explicitly authorized same-account encoded authentication state without secret output.'

    def add_arguments(self, parser):
        for name in ('actor-id', 'source-database', 'expected-source-snapshot', 'username', 'idempotency-key', 'reason'):
            parser.add_argument('--' + name, required=True, type=int if name == 'actor-id' else str)

    def handle(self, **options):
        args = {key: options[key] for key in ('actor_id', 'source_database', 'expected_source_snapshot', 'username', 'idempotency_key', 'reason')}
        try:
            result = preserve(**args)
        except AuthenticationContinuationError as error:
            raise CommandError(str(error)) from None
        except Exception:
            # Do not render traceback/local variables from credential handling.
            raise CommandError('AUTHENTICATION_STATE_PRESERVATION_FAILED') from None
        self.stdout.write(json.dumps(result, ensure_ascii=False))
