"""Harness execution (NOT end-to-end) of calibre's OPDS navcatalog handler.

What is REAL (unmodified source from the checkout under test):
  * opds_navcatalog / opds_category / opds_categorygroup: function bodies are
    extracted verbatim from src/calibre/srv/opds.py with ast and exec'd
    (only the @endpoint decorator is dropped, since routes.py can't be imported
    without calibre's compiled extensions).
  * parse_request_uri / parse_uri + quoted_slash from src/calibre/srv/http_request.py
    (same ast extraction), used to show which URLs can reach the handler.
  * polyglot.binary.from_hex_unicode / as_hex_unicode, polyglot.urllib.unquote,
    calibre.srv.errors.HTTPNotFound / HTTPSimpleResponse (real imports; the
    top-level `calibre` package is replaced by a bare namespace module so that
    calibre/__init__.py, which needs compiled extensions, is not executed).

What is STUBBED:
  * RequestContext (library/db lookup): url_for returns a string, get_categories
    returns {}, db.field_metadata is {}.
  * get_all_books / get_navcatalog (feed builders): return a sentinel string.
  * ctx / rd: rd only provides .query (a dict).

The server-level consequence (non-HTTPSimpleResponse exception -> reraise in
http_response.job_done -> loop logs traceback -> report_unhandled_exception ->
500) is established by source reading, not executed here.
"""
import ast, sys, types, traceback

SRC = sys.argv[1] if len(sys.argv) > 1 else '/tmp/calibre/src'
sys.path.insert(0, SRC)
pkg = types.ModuleType('calibre'); pkg.__path__ = [SRC + '/calibre']; sys.modules['calibre'] = pkg

from polyglot.binary import from_hex_unicode, as_hex_unicode
from polyglot.urllib import unquote
from calibre.srv.errors import HTTPNotFound, HTTPSimpleResponse


def extract(path, names, extra_ns):
    tree = ast.parse(open(path).read())
    ns = dict(extra_ns)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            exec(compile(ast.Module([node], []), path, 'exec'), ns)
        elif isinstance(node, ast.Assign) and any(getattr(t, 'id', None) in names for t in node.targets):
            exec(compile(ast.Module([node], []), path, 'exec'), ns)
    return ns


class FakeDB:
    field_metadata = {}

class RequestContext:  # STUB
    def __init__(self, ctx, rd):
        self.ctx, self.rd, self.db = ctx, rd, FakeDB()
    def url_for(self, route, **kw):
        return route + '/' + '/'.join(map(str, kw.values()))
    def get_categories(self):
        return {}

def get_all_books(rc, which, page_url, up_url, offset=0):   # STUB
    return f'SENTINEL get_all_books({which!r})'

def get_navcatalog(rc, which, page_url, up_url, offset=0):  # STUB
    return f'SENTINEL get_navcatalog({which!r})'

class RD:
    query = {}

import re
opds = extract(SRC + '/calibre/srv/opds.py', {'opds_navcatalog', 'opds_category', 'opds_categorygroup'}, dict(
    from_hex_unicode=from_hex_unicode, as_hex_unicode=as_hex_unicode, HTTPNotFound=HTTPNotFound,
    RequestContext=RequestContext, get_all_books=get_all_books, get_navcatalog=get_navcatalog,
    default_feed_title='calibre', _=lambda x: x))
http = extract(SRC + '/calibre/srv/http_request.py', {'parse_request_uri', 'parse_uri', 'quoted_slash'}, dict(
    re=re, unquote=unquote, HTTPSimpleResponse=HTTPSimpleResponse, http=__import__('http.client'),
    as_unicode=str))

def call(fn, *args):
    try:
        r = fn(None, RD(), *args)
        return 'OK', repr(r)
    except HTTPNotFound as e:
        return 'HTTP404', f'HTTPNotFound({e})'
    except Exception as e:
        return 'UNHANDLED', f'{type(e).__module__}.{type(e).__qualname__}: {e}'

print('python', sys.version.split()[0], '| source', SRC)
print('\n== Reachability: real parse_uri() path components (route is /opds/navcatalog/{which}, 3 components) ==')
for uri in [b'/opds/navcatalog/', b'/opds/navcatalog//', b'/opds/navcatalog/zz', b'/opds/navcatalog/4', b'/opds/navcatalog/ff', b'/opds/navcatalog/4e74616773']:
    print(f'  {uri.decode():32} -> path={http["parse_uri"](uri, parse_query=False)[1]}')

cases = [
    ('empty (direct call only; not reachable via URL)', ''),
    ('non-hex chars', 'zz'),
    ('odd-length hex', '4'),
    ('valid hex, invalid UTF-8', 'ff'),
    ('control: valid N+tags', as_hex_unicode('Ntags')),
    ('control: valid O+title', as_hex_unicode('Otitle')),
    ('control: valid hex, unknown type X', as_hex_unicode('Xfoo')),
]
fails = 0
print('\n== opds_navcatalog(which) ==')
for label, w in cases:
    st, msg = call(opds['opds_navcatalog'], w)
    bad = st == 'UNHANDLED'
    fails += bad
    print(f'  [{"FAIL" if bad else "pass"}] {label:45} which={w!r:22} -> {st}: {msg}')

print('\n== siblings, same malformed input (informational, not counted) ==')
for fn, args in [('opds_category', (as_hex_unicode('tags'), 'zz')), ('opds_category', ('zz', as_hex_unicode('Itag:tags'))),
                 ('opds_categorygroup', ('zz', as_hex_unicode('A'))), ('opds_categorygroup', (as_hex_unicode('tags'), 'ff'))]:
    st, msg = call(opds[fn], *args)
    print(f'  {fn}{args!r:45} -> {st}: {msg}')

print(f'\nnavcatalog malformed-input cases raising non-HTTP exceptions (-> HTTP 500 in server): {fails}')
print('RESULT:', 'RED' if fails else 'GREEN')
sys.exit(1 if fails else 0)
