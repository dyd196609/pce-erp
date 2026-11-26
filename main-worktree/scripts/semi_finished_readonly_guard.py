"""Evidence/runtime harness only: classify each SQL; transactions never confer write access.

No dependency from business services. Read-only SQLite URI/query_only are an
independent engine boundary. Unknown PRAGMAs/statements fail closed.
"""
import re
import sqlparse
from sqlparse import tokens as T


class ReadOnlyViolation(RuntimeError):
    pass


READ_PRAGMAS = frozenset({
    'table_info', 'table_xinfo', 'index_list', 'index_info', 'index_xinfo',
    'foreign_key_list', 'foreign_key_check', 'integrity_check', 'quick_check',
    'database_list', 'compile_options', 'collation_list', 'function_list',
    'module_list', 'query_only', 'journal_mode', 'foreign_keys', 'schema_version',
    'user_version', 'encoding', 'page_count', 'freelist_count',
})
ARGUMENT_PRAGMAS = frozenset({'table_info', 'table_xinfo', 'index_list', 'index_info',
    'index_xinfo', 'foreign_key_list', 'foreign_key_check', 'integrity_check', 'quick_check'})


def classify(sql):
    statements = [s for s in sqlparse.parse(sql) if str(s).strip()]
    if len(statements) != 1:
        raise ReadOnlyViolation('READ_GUARD_MULTI_OR_EMPTY_STATEMENT')
    stmt = statements[0]
    tokens = [t for t in stmt.flatten() if not t.is_whitespace and t.ttype not in T.Comment]
    if not tokens:
        raise ReadOnlyViolation('READ_GUARD_EMPTY_STATEMENT')
    first = tokens[0].value.upper()
    significant = ' '.join(t.value for t in tokens).rstrip(' ;')
    if first in {'BEGIN', 'SAVEPOINT', 'RELEASE', 'ROLLBACK', 'COMMIT', 'END'}:
        # Accept only a complete transaction grammar; never arbitrary trailing SQL.
        ident = r'(?:[A-Za-z_][A-Za-z0-9_]*|"[^"\r\n]+")'
        grammar = (r'BEGIN(?: (?:DEFERRED|IMMEDIATE|EXCLUSIVE))?(?: TRANSACTION)?'
            r'|(?:COMMIT|END)(?: TRANSACTION)?|ROLLBACK(?: TRANSACTION)?'
            r'|ROLLBACK(?: TRANSACTION)? TO(?: SAVEPOINT)? ' + ident +
            r'|SAVEPOINT ' + ident + r'|RELEASE(?: SAVEPOINT)? ' + ident)
        if re.fullmatch(grammar, significant, re.I):
            return 'TRANSACTION_CONTROL'
        raise ReadOnlyViolation('READ_GUARD_INVALID_TRANSACTION')
    if first == 'PRAGMA':
        # Read introspection arguments allowed; assignments and stateful pragmas denied.
        m = re.fullmatch(r'PRAGMA\s+(?:(?:main|temp)\s*\.\s*)?(\w+)\s*(?:\(([^;]*)\))?', significant, re.I)
        if m and m[1].lower() in READ_PRAGMAS:
            if m[2] is None or m[1].lower() in ARGUMENT_PRAGMAS:
                return 'SCHEMA_INTROSPECTION_READ'
        raise ReadOnlyViolation('READ_GUARD_MUTATING_OR_UNKNOWN_PRAGMA')
    if first == 'EXPLAIN':
        inner = re.sub(r'^EXPLAIN\s+(?:QUERY\s+PLAN\s+)?', '', significant, flags=re.I)
        if classify(inner) == 'READ':
            return 'READ'
        raise ReadOnlyViolation('READ_GUARD_NONREAD_EXPLAIN')
    if stmt.get_type() != 'SELECT':
        raise ReadOnlyViolation('READ_GUARD_' + first)
    # Protect CTE bodies, SELECT INTO, extension functions and SQL write helpers.
    for token in tokens:
        if token.ttype in T.Literal.String:
            continue
        word = token.value.upper().strip('"`[]')
        if word in {'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'CREATE', 'ALTER',
                    'DROP', 'ATTACH', 'DETACH', 'VACUUM', 'REINDEX', 'INTO',
                    'LOAD_EXTENSION', 'WRITEFILE'}:
            raise ReadOnlyViolation('READ_GUARD_EMBEDDED_' + word)
    return 'READ'


class ReadOnlyGuard:
    def __init__(self):
        self.events = []

    def __call__(self, execute, sql, params, many, context):
        try:
            category = classify(sql)
        except ReadOnlyViolation as error:
            self.events.append({'category': 'BLOCKED', 'reason': str(error)})
            raise
        self.events.append({'category': category, 'sql': sql})
        return execute(sql, params, many, context)


class ReadOnlyEvidenceMiddleware:
    """Injected only by the controlled localhost harness, not normal settings."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.db import connection
        import json, os
        guard = ReadOnlyGuard()
        with connection.execute_wrapper(guard):
            response = self.get_response(request)
        response['X-PCE-Readonly-Guard'] = 'read-transaction-v1'
        response['X-PCE-Schema-Stage'] = os.environ['PCE_RETRY_STAGE']
        if request.path.startswith('/api/pde/a1-engineering/calculations/readiness'):
            path = os.environ['PCE_RETRY_HTTP_LOG']
            item = {'path': request.path, 'query': request.GET.dict(), 'status': response.status_code,
                    'events': guard.events, 'stage': os.environ['PCE_RETRY_STAGE']}
            if response.status_code == 200:
                item['data'] = json.loads(response.content)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + '\n')
        return response
