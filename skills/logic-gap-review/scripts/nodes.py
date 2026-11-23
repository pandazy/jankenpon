#!/usr/bin/env python3
"""Map logic nodes and rank review candidates (logic-gap-review skill).

Read-only. Python 3.8+ standard library only. Every row is a *signal*: a place
to read, never a finding on its own.

Python files are parsed exactly (ast module). JavaScript/TypeScript, Java,
Kotlin and Go are scanned with patterns, so expect some misses and some false
alarms there; those results are marked "approx". Code outside any function
(module top level) is not listed.

Commands:
  rank PATH    Rank functions as review candidates, highest score first.
               score = (v(G) - 1) + 3 x sinks + 2 x sources
                       + 0.5 x min(commits, 10) + fix commits
  nodes PATH   List every logic node per function, with v(G).

Usage:
  python3 -I nodes.py rank  PATH [--top N] [--commits N] [--no-history] [common options]
  python3 -I nodes.py nodes PATH [--function NAME] [--family a,b] [common options]

Common options:
  --json OUT         Also write every result to OUT as JSON.
  --exclude GLOB     Extra path glob to skip (repeatable).
  --include-tests    Also scan test files (skipped by default).
"""
import argparse
import ast
import bisect
import collections
import fnmatch
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {
    '.git', '.hg', '.svn', 'node_modules', 'bower_components', 'vendor', 'third_party',
    'build', 'dist', 'out', 'target', 'bin', 'obj', 'coverage', '.next', '.nuxt',
    '__pycache__', '.venv', 'venv', 'env', '.tox', '.mypy_cache', '.pytest_cache',
    '.gradle', '.idea', '.vscode', 'site-packages',
}
LANG_BY_EXT = {
    '.py': 'py', '.js': 'js', '.jsx': 'js', '.mjs': 'js', '.cjs': 'js', '.ts': 'js', '.tsx': 'js',
    '.mts': 'js', '.cts': 'js', '.java': 'java', '.kt': 'kotlin', '.kts': 'kotlin', '.go': 'go',
}
TEST_PATTERNS = [
    '*/__tests__/*', '*/__mocks__/*', '*/test/*', '*/tests/*', '*/testing/*', '*/spec/*',
    '*.test.*', '*.spec.*', '*_test.go', '*/test_*.py', '*_test.py', '*/conftest.py',
    '*/src/test/*', '*Test.java', '*Test.kt', '*Tests.java', '*Tests.kt',
]
FAMILIES = ('decision', 'hidden', 'coercion', 'data-flow', 'boundary', 'resource', 'error-path')
FIX_WORDS = re.compile(r'\b(?:fix(?:es|ed)?|bug|hotfix|patch|regression)\b', re.I)


def mk(line, family, kind, detail=''):
    return {'line': line, 'family': family, 'kind': kind, 'detail': detail}


def finish(nodes):
    """Drop duplicates and sort by line, then family order, then kind."""
    seen, out = set(), []
    for n in nodes:
        key = (n['line'], n['family'], n['kind'], n['detail'])
        if key not in seen:
            seen.add(key)
            out.append(n)
    return sorted(out, key=lambda n: (n['line'], FAMILIES.index(n['family']), n['kind'], n['detail']))


# ── Python (exact, via ast) ─────────────────────────────────────────────────

DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
MATCH = getattr(ast, 'Match', None)
MATCH_CASE = getattr(ast, 'match_case', None)
PY_SOURCE = re.compile(
    r'^(?:(?:self\.)?request|req)\.(?:args|form|json|values|data|files|params|query_params|query'
    r'|GET|POST|body|headers|cookies|get_json)\b|^sys\.(?:argv|stdin)\b|^os\.(?:environ|getenv)\b')
PY_NET = re.compile(r'^(?:requests|httpx)\.(?:get|post|put|patch|delete|head|request)$'
                    r'|^(?:urllib\.request\.)?urlopen$')
PY_PARSE = {
    'int', 'float', 'complex', 'Decimal', 'decimal.Decimal', 'json.loads', 'json.load',
    'datetime.strptime', 'datetime.datetime.strptime', 'datetime.fromisoformat',
    'datetime.datetime.fromisoformat', 'date.fromisoformat', 'uuid.UUID', 'UUID', 'bytes.fromhex',
    'base64.b64decode', 'ast.literal_eval', 'ipaddress.ip_address',
}
PY_FILE = {'open', 'io.open', 'os.remove', 'os.unlink', 'os.rmdir', 'shutil.rmtree', 'send_file',
           'send_from_directory', 'Path', 'pathlib.Path'}
PY_DESERIALIZE = {'pickle.load', 'pickle.loads', 'marshal.load', 'marshal.loads', 'shelve.open',
                  'yaml.unsafe_load'}
PY_RE = {'compile', 'match', 'search', 'fullmatch', 'findall', 'finditer', 'sub', 'split'}
LOG_FUNC = re.compile(r'^(?:print|logging\.\w+|warnings\.warn|(?:self\.|cls\.)?_?(?:log|logger|LOG|LOGGER)\.\w+)$')


def walk_own(root):
    """Yield root and its descendants without entering nested functions or classes."""
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        if n is not root and isinstance(n, DEFS):
            continue
        stack.extend(ast.iter_child_nodes(n))


def dotted(e):
    parts = []
    while isinstance(e, ast.Attribute):
        parts.append(e.attr)
        e = e.value
    if isinstance(e, ast.Name):
        parts.append(e.id)
    elif isinstance(e, ast.Call):
        inner = dotted(e.func)
        parts.append(inner + '()' if inner else '?')
    else:
        return ''
    return '.'.join(reversed(parts))


def is_literal(e):
    if isinstance(e, ast.Constant):
        return True
    return isinstance(e, ast.JoinedStr) and not any(isinstance(v, ast.FormattedValue) for v in e.values)


def is_built_string(e):
    if isinstance(e, ast.JoinedStr):
        return not is_literal(e)
    if isinstance(e, ast.BinOp) and isinstance(e.op, (ast.Add, ast.Mod)):
        return True
    return isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == 'format'


def is_default_value(v):
    if v is None:
        return True
    if isinstance(v, ast.Constant) and v.value is not True and v.value in (None, False, 0, '', b''):
        return True
    if isinstance(v, (ast.List, ast.Tuple, ast.Set)) and not v.elts:
        return True
    if isinstance(v, ast.Dict) and not v.keys:
        return True
    return (isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.USub)
            and isinstance(v.operand, ast.Constant) and v.operand.value == 1)


def except_kind(handler):
    """'catch-swallows' or 'catch-returns-default' when the handler hides the error."""
    rest = [s for s in handler.body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                    and LOG_FUNC.match(dotted(s.value.func)))
            and not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    if all(isinstance(s, (ast.Pass, ast.Continue)) for s in rest):
        return 'catch-swallows'
    if len(rest) == 1 and isinstance(rest[0], ast.Return) and is_default_value(rest[0].value):
        return 'catch-returns-default'
    return None


def stored_names(stmts):
    names = set()
    for s in stmts:
        for n in walk_own(s):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.add(n.id)
            elif isinstance(n, DEFS):
                names.add(n.name)
    return names


def used_names(stmts):
    names = set()
    for s in stmts:
        for n in walk_own(s):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                names.add(n.id)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                names.add(n.target.id)
    return names


def terminates(body):
    return bool(body) and isinstance(body[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break))


def unassigned_nodes(fn):
    """Names assigned on some paths through an if chain but used later on all paths."""
    out = []
    a = fn.args
    params = {x.arg for x in getattr(a, 'posonlyargs', []) + a.args + a.kwonlyargs}
    params |= {x.arg for x in (a.vararg, a.kwarg) if x}

    def scan(block, before):
        assigned = set(before)
        for i, s in enumerate(block):
            if isinstance(s, ast.If):
                branches, cur = [], s
                while True:
                    branches.append(cur.body)
                    if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
                        cur = cur.orelse[0]
                        continue
                    branches.append(cur.orelse)  # [] is the implicit "no branch matched" path
                    break
                live = [b for b in branches if not terminates(b)]
                stored = [stored_names(b) for b in live]
                later = used_names(block[i + 1:])
                for name in sorted(set().union(*stored) - assigned if stored else set()):
                    if name in later and any(name not in st for st in stored):
                        out.append(mk(s.lineno, 'data-flow', 'maybe-unassigned',
                                      f'{name} is not assigned on every path, but is used later'))
            for field in ('body', 'orelse', 'finalbody'):
                sub = getattr(s, field, None)
                if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt) and not isinstance(s, DEFS):
                    scan(sub, assigned)
            for h in getattr(s, 'handlers', []):
                scan(h.body, assigned)
            assigned |= stored_names([s])

    scan(fn.body, params)
    return out


def py_call(call, name, fn_name, with_calls):
    out, line = [], call.lineno
    last = name.rsplit('.', 1)[-1]
    kw = {k.arg: k.value for k in call.keywords if k.arg}
    first = call.args[0] if call.args else None
    variable_first = first is not None and not is_literal(first)

    def sink(kind, detail=name):
        out.append(mk(line, 'boundary', 'sink:' + kind, detail))

    shell = kw.get('shell')
    loader = dotted(kw['Loader']) if 'Loader' in kw else ''
    if name in ('eval', 'exec'):
        sink('code')
    elif name in ('os.system', 'os.popen') or (
            name.startswith('subprocess.') and isinstance(shell, ast.Constant) and shell.value is True):
        sink('shell')
    elif last in ('execute', 'executemany', 'executescript', 'raw', 'text') and first is not None \
            and is_built_string(first):
        sink('sql', name + ' with a built string')
    elif name in PY_DESERIALIZE or (name == 'yaml.load' and not loader.endswith(('SafeLoader', 'BaseLoader'))):
        sink('deserialize')
    elif name in ('render_template_string', 'Markup', 'markupsafe.Markup', 'mark_safe') and variable_first:
        sink('html')
    elif name.startswith('re.') and last in PY_RE and variable_first:
        sink('regex', name + ' with a pattern from a variable')
    if name in PY_FILE and variable_first:
        sink('file')
    if PY_NET.match(name):
        out.append(mk(line, 'hidden', 'network-call' if 'timeout' in kw else 'network-no-timeout', name))
        if variable_first:
            sink('outbound-request')
    if name in PY_PARSE:
        out.append(mk(line, 'hidden', 'parse', name))
    if name == 'next' and len(call.args) < 2:
        out.append(mk(line, 'hidden', 'next-no-default', 'next() raises StopIteration when empty'))
    if name in ('open', 'io.open') and id(call) not in with_calls:
        out.append(mk(line, 'resource', 'acquire-no-release', 'open() outside a with block'))
    if name == 'input':
        out.append(mk(line, 'boundary', 'source', 'input'))
    if name in (fn_name, 'self.' + fn_name, 'cls.' + fn_name):
        out.append(mk(line, 'hidden', 'recursion', name))
    return out


def py_function(path, fn, qual):
    nodes, count = [], [0]

    def dec(line, kind, detail='', weight=1):
        count[0] += weight
        nodes.append(mk(line, 'decision', kind, detail))

    own = [n for n in walk_own(fn) if n is not fn and not isinstance(n, DEFS)]
    elifs = {id(n.orelse[0]) for n in own
             if isinstance(n, ast.If) and len(n.orelse) == 1 and isinstance(n.orelse[0], ast.If)}
    with_calls = {id(i.context_expr) for n in own if isinstance(n, (ast.With, ast.AsyncWith))
                  for i in n.items if isinstance(i.context_expr, ast.Call)}
    a = fn.args
    annotations = [x.annotation for x in getattr(a, 'posonlyargs', []) + a.args + a.kwonlyargs
                   + [a.vararg, a.kwarg] if x is not None and x.annotation is not None]
    annotations += [fn.returns] if fn.returns else []
    annotations += [n.annotation for n in own if isinstance(n, ast.AnnAssign)]
    in_annotation = {id(x) for ann in annotations for x in ast.walk(ann)}
    acquires, releases = [], False

    for n in own:
        if id(n) in in_annotation:
            continue
        if isinstance(n, ast.If):
            dec(n.lineno, 'if', 'elif' if id(n) in elifs else '')
            if id(n) not in elifs:
                branches, cur = 1, n
                while len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
                    cur, branches = cur.orelse[0], branches + 1
                if branches >= 2 and not cur.orelse:
                    nodes.append(mk(n.lineno, 'decision', 'if-chain-no-else', f'{branches} branches, no final else'))
        elif isinstance(n, ast.IfExp):
            dec(n.lineno, 'ternary')
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            dec(n.lineno, 'for')
        elif isinstance(n, ast.While):
            dec(n.lineno, 'while')
            exits = any(isinstance(x, (ast.Break, ast.Return, ast.Raise)) for s in n.body for x in walk_own(s))
            if isinstance(n.test, ast.Constant) and n.test.value and not exits:
                nodes.append(mk(n.lineno, 'hidden', 'loop-no-exit', 'while True with no break, return or raise'))
        elif isinstance(n, ast.ExceptHandler):
            dec(n.lineno, 'catch', 'except')
            if n.type is None:
                nodes.append(mk(n.lineno, 'error-path', 'bare-catch', 'bare except also catches exit and interrupt'))
            kind = except_kind(n)
            if kind:
                nodes.append(mk(n.lineno, 'error-path', kind))
        elif isinstance(n, ast.BoolOp):
            dec(n.lineno, 'and' if isinstance(n.op, ast.And) else 'or', '', len(n.values) - 1)
        elif isinstance(n, ast.comprehension):
            dec(n.target.lineno, 'comprehension', 'for')
            for c in n.ifs:
                dec(c.lineno, 'comprehension', 'if')
        elif MATCH_CASE is not None and isinstance(n, MATCH_CASE):
            dec(n.pattern.lineno, 'case')
        elif MATCH is not None and isinstance(n, MATCH):
            wildcard = any(type(c.pattern).__name__ == 'MatchAs' and c.pattern.pattern is None
                           and c.guard is None for c in n.cases)
            if not wildcard:
                nodes.append(mk(n.lineno, 'decision', 'switch-no-default', 'match with no case _'))
        elif isinstance(n, ast.Assert):
            dec(n.lineno, 'assert', 'skipped when Python runs with -O')
        elif isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            left = n.left if isinstance(n, ast.BinOp) else n.target
            if not (isinstance(n.op, ast.Mod) and isinstance(left, (ast.Constant, ast.JoinedStr))):
                nodes.append(mk(n.lineno, 'hidden', 'modulo' if isinstance(n.op, ast.Mod) else 'division'))
        elif isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load) and not isinstance(n.slice, ast.Slice):
            nodes.append(mk(n.lineno, 'hidden', 'index-or-key', dotted(n.value)))
        elif isinstance(n, ast.Attribute):
            m = PY_SOURCE.match(dotted(n))
            if m:
                nodes.append(mk(n.lineno, 'boundary', 'source', m.group(0)))
        elif isinstance(n, ast.Call):
            name = dotted(n.func)
            nodes.extend(py_call(n, name, fn.name, with_calls))
            if name.endswith('.acquire'):
                acquires.append(n.lineno)
            releases = releases or name.endswith('.release')

    for line in acquires if not releases else []:
        nodes.append(mk(line, 'resource', 'acquire-no-release', 'acquire() with no release() in this function'))
    positional = getattr(a, 'posonlyargs', []) + a.args
    pairs = list(zip(positional[len(positional) - len(a.defaults):], a.defaults)) + list(zip(a.kwonlyargs, a.kw_defaults))
    for arg, d in pairs:
        if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (
                isinstance(d, ast.Call) and dotted(d.func) in ('list', 'dict', 'set')):
            nodes.append(mk(d.lineno, 'data-flow', 'mutable-default', f'{arg.arg}: one default value is shared by every call'))
    nodes.extend(unassigned_nodes(fn))
    return {'file': path, 'name': qual, 'line': fn.lineno, 'lang': 'py', 'exact': True,
            'decisions': count[0], 'vg': count[0] + 1, 'nodes': finish(nodes)}


def analyze_py(path, src):
    try:
        tree = ast.parse(src, filename=path)
    except (SyntaxError, ValueError) as e:
        return [], f'{path}: cannot parse ({type(e).__name__})'
    fns = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fns.append(py_function(path, child, prefix + child.name))
                visit(child, prefix + child.name + '.')
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + '.')
            else:
                visit(child, prefix)

    visit(tree, '')
    return fns, None


# ── JavaScript / TypeScript, Java, Kotlin, Go (approximate, via patterns) ───

def strip(src, lang):
    """Blank comments and string contents, keeping quotes, newlines and offsets.

    Returns (text, interps): interps are offsets of '${' inside JS template
    literals and Kotlin strings. Code inside '${ }' is kept."""
    out, interps, n, i = list(src), [], len(src), 0
    tpl = []           # one [brace depth, string state] per open '${'
    state = None       # None = code; else (closing quote, has interpolation)
    regex_ok = True    # JS: a '/' here would start a regex literal

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != '\n':
                out[k] = ' '

    while i < n:
        c = src[i]
        if state is None:
            if src.startswith('//', i):
                j = src.find('\n', i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
                continue
            if src.startswith('/*', i):
                j = src.find('*/', i + 2)
                j = n if j < 0 else j + 2
                blank(i, j)
                i = j
                continue
            if lang == 'js' and c == '/' and regex_ok:
                close = regex_end(src, i)
                if close:
                    blank(i + 1, close)
                    i, regex_ok = close + 1, False
                    continue
            if lang in ('java', 'kotlin') and src.startswith('"""', i):
                state, i = ('"""', lang == 'kotlin'), i + 3
                continue
            if c in '"\'`':
                state, i = (c, (c == '`' and lang == 'js') or (c == '"' and lang == 'kotlin')), i + 1
                continue
            if tpl and c == '{':
                tpl[-1][0] += 1
            elif tpl and c == '}':
                if tpl[-1][0] == 0:
                    state, i = tpl.pop()[1], i + 1
                    continue
                tpl[-1][0] -= 1
            if c.isalnum() or c in '_$)]':
                regex_ok = False
            elif not c.isspace():
                regex_ok = True
            i += 1
            continue
        closer, interp = state
        if c == '\\' and not (closer == '`' and lang == 'go'):
            blank(i, i + 2)
            i += 2
            continue
        if src.startswith(closer, i):
            state, regex_ok, i = None, False, i + len(closer)
            continue
        if interp and src.startswith('${', i):
            interps.append(i)
            tpl.append([0, state])
            state, i = None, i + 2
            continue
        if c == '\n' and closer in ('"', "'"):
            state = None  # unterminated one-line string: recover
        else:
            blank(i, i + 1)
        i += 1
    return ''.join(out), interps


def regex_end(src, i):
    """Offset of the '/' that closes a JS regex literal opened at i, or 0."""
    j, in_class = i + 1, False
    while j < len(src):
        ch = src[j]
        if ch == '\\':
            j += 2
            continue
        if ch == '\n':
            return 0
        if in_class:
            in_class = ch != ']'
        elif ch == '[':
            in_class = True
        elif ch == '/':
            return j if j > i + 1 else 0
        j += 1
    return 0


def bracket_map(text):
    pairs, stacks = {}, {'(': [], '{': [], '[': []}
    closers = {')': '(', '}': '{', ']': '['}
    for i, ch in enumerate(text):
        if ch in stacks:
            stacks[ch].append(i)
        elif ch in closers and stacks[closers[ch]]:
            pairs[stacks[closers[ch]].pop()] = i
    return pairs


KEYWORDS = {
    'if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'with', 'else', 'do', 'try', 'new',
    'typeof', 'delete', 'await', 'yield', 'case', 'default', 'throw', 'synchronized', 'super', 'this',
    'when', 'fun', 'func', 'go', 'defer', 'select', 'sizeof', 'void',
}
JS_TAIL = re.compile(r'\s*(?::[^{;=]*)?\{')
ARROW_TAIL = re.compile(r'\s*(?::[^{;=]*?)?=>\s*\{')
JAVA_TAIL = re.compile(r'\s*(?:throws\s+[\w$.,\s]+)?\{')
LAMBDA_TAIL = re.compile(r'\s*->\s*\{')
KOTLIN_TAIL = re.compile(r'\s*(?::\s*[^{=]+?)?\{')
GO_TAIL = re.compile(r'\s*(?:\([^{}]*\)|[\w.*\[\]]+)?\s*\{')
FN_PATTERNS = {
    'js': [
        (re.compile(r'\bfunction\b\s*\*?\s*(?P<name>[A-Za-z_$][\w$]*)?\s*(?:<[^>(]*>)?\s*\('), JS_TAIL),
        (re.compile(r'^[ \t]*(?:(?:public|private|protected|static|async|override|readonly|abstract|get|set)\s+)*'
                    r'(?P<name>[A-Za-z_$][\w$]*)\s*(?:<[^>(]*>)?\s*\(', re.M), JS_TAIL),
        (re.compile(r'(?<![\w$.])(?:async\s*)?\('), ARROW_TAIL),
        (re.compile(r'(?<![\w$.])(?P<param>[A-Za-z_$][\w$]*)\s*=>\s*\{'), None),
    ],
    'java': [
        (re.compile(r'^[ \t]*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default'
                    r'|strictfp)\s+|@\w+(?:\([^)]*\))?\s+)*(?:<[^>]+>\s+)?(?P<type>[\w$.]+(?:<[^;{}()]*>)?'
                    r'(?:\[\])*\s+)?(?P<name>[A-Za-z_$][\w$]*)\s*\(', re.M), JAVA_TAIL),
        (re.compile(r'(?<![\w$.])\('), LAMBDA_TAIL),
        (re.compile(r'(?<![\w$.])(?P<param>[A-Za-z_$][\w$]*)\s*->\s*\{'), None),
    ],
    'kotlin': [
        (re.compile(r'\bfun\b\s*(?:<[^>]*>\s*)?(?:[\w$.]+\.)?(?P<name>[A-Za-z_$][\w$]*)\s*\('), KOTLIN_TAIL),
    ],
    'go': [
        (re.compile(r'^func\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*\(', re.M), GO_TAIL),
        (re.compile(r'\bfunc\s*\('), GO_TAIL),
    ],
}
ASSIGN_BEFORE = re.compile(r'([A-Za-z_$][\w$]*)\s*(?::=|=|:)\s*(?:async\s*)?$')
CALL_BEFORE = re.compile(r'([A-Za-z_$][\w$.]*)\s*\([^()]*$')


def anon_name(text, pos):
    before = text[max(0, pos - 200):pos]
    m = ASSIGN_BEFORE.search(before)
    if m:
        return m.group(1)
    m = CALL_BEFORE.search(before)
    return f'<callback in {m.group(1)}>' if m else '<anonymous>'


def find_functions(text, lang, pairs):
    found = {}
    for pat, tail in FN_PATTERNS[lang]:
        for m in pat.finditer(text):
            g = m.groupdict()
            name = g.get('name')
            if name in KEYWORDS or g.get('param') in KEYWORDS \
                    or (g.get('type') or '').strip() in ('new', 'return', 'throw', 'else'):
                continue
            if tail is None:
                if re.search(r'\bcase\b[^\n]*$', text[max(0, m.start() - 80):m.start()]):
                    continue  # Java switch arrow "case X -> {", not a lambda
                body = m.end() - 1
            else:
                close = pairs.get(m.end() - 1, -1)
                t = tail.match(text, close + 1) if close > 0 else None
                if not t:
                    continue
                body = t.end() - 1
            end = pairs.get(body, -1)
            if body in found or end < 0:
                continue
            found[body] = {'name': name or anon_name(text, m.start()), 'start': m.start(), 'body': body, 'end': end}
    return sorted(found.values(), key=lambda f: f['start'])


C_DECISIONS = [('if', r'\bif\b'), ('for', r'\bfor\b'), ('while', r'\bwhile\b'), ('case', r'\bcase\b'),
               ('catch', r'(?<!\.)\bcatch\b'), ('and', r'&&(?!=)'), ('or', r'\|\|(?!=)')]
TERNARY = ('ternary', r'(?<=\s)\?(?=\s)(?!\s*(?:extends|super)\b)')
DECISIONS = {
    'js': C_DECISIONS + [('nullish', r'\?\?(?!=)'), TERNARY],
    'java': C_DECISIONS + [TERNARY],
    'kotlin': [d for d in C_DECISIONS if d[0] != 'case'] + [
        ('elvis', r'\?:'), ('when-branch', r'(?m)^(?![^\n]*\{[^\n]*->)[^\n]*?->')],
    'go': [d for d in C_DECISIONS if d[0] != 'catch'],
}
SOURCES = {
    'js': r'\b(?:req|request|ctx\.request)\.(?:body|query|params|headers|cookies|files)\b|\bprocess\.(?:argv|env)\b'
          r'|\bevent\.(?:body|headers)\b|\blocation\.(?:search|hash|href|pathname)\b'
          r'|\bdocument\.(?:cookie|referrer)\b|\bwindow\.name\b|\bURLSearchParams\b|\blocalStorage\.getItem\b|\.searchParams\b',
    'java': r'\.(?:getParameter|getParameterValues|getParameterMap|getHeader|getHeaders|getQueryString|getInputStream'
            r'|getReader|getCookies|getPathInfo|getRequestURI)\s*\(|@(?:RequestParam|PathVariable|RequestBody|RequestHeader'
            r'|CookieValue|QueryParam|PathParam|FormParam)\b|\bSystem\.(?:getenv|getProperty)\s*\(|\bargs\s*\[',
    'go': r'\br\.(?:URL\.Query|FormValue|PostFormValue|Form|PostForm|Body|Header|Cookie|MultipartForm)\b'
          r'|\.(?:FormValue|PostFormValue|Param|QueryParam)\s*\(|\bos\.(?:Args|Getenv|LookupEnv|Stdin)\b'
          r'|\bc\.(?:Bind\w*|ShouldBind\w*)\s*\(',
}
SOURCES['kotlin'] = SOURCES['java'] + r'|\bcall\.(?:receive\w*|parameters|request)\b'
PARSE = {
    'js': r'\bJSON\.parse\s*\(|(?<![\w$.])(?:parseInt|parseFloat|Number|BigInt|atob|decodeURIComponent)\s*\('
          r'|\bnew\s+(?:Date|URL)\s*\(|\bDate\.parse\s*\(',
    'java': r'\b(?:Integer|Long|Short|Byte|Double|Float)\.(?:parse\w+|valueOf)\s*\(|\b(?:LocalDate|LocalDateTime|Instant'
            r'|ZonedDateTime|OffsetDateTime|Duration)\.parse\s*\(|\bUUID\.fromString\s*\(|\b(?:new\s+)?BigDecimal\s*\('
            r'|\.readValue\s*\(|\.fromJson\s*\(',
    'go': r'\bstrconv\.\w+\s*\(|\bjson\.(?:Unmarshal|NewDecoder)\s*\(|\btime\.Parse\w*\s*\(|\burl\.Parse\s*\('
          r'|\bbase64\.\w+\.DecodeString\s*\(',
}
PARSE['kotlin'] = PARSE['java'] + r'|\.to(?:Int|Long|Double|Float|Short|Byte|BigDecimal)\s*\(\s*\)'
NETWORK = {
    'js': r'(?<![\w$.])fetch\s*\(|\baxios(?:\.(?:get|post|put|delete|patch|request))?\s*\(|\bhttps?\.(?:get|request)\s*\(',
    'java': r'\.(?:getForObject|getForEntity|postForObject|postForEntity|exchange)\s*\(|\.openConnection\s*\(',
    'go': r'\bhttp\.(?:Get|Post|PostForm|Head)\s*\(|\b\w*[cC]lient\.Do\s*\(|\bnet\.Dial\w*\s*\(',
}
NETWORK['kotlin'] = NETWORK['java']
SINKS = {
    'js': [
        ('sql', r'\.(?:query|execute|raw|unsafe|\$queryRawUnsafe|\$executeRawUnsafe)\s*\(', 'built'),
        ('shell', r'(?:(?<![\w$.])|(?<=child_process\.))(?:exec|execSync|spawn|spawnSync|execFile|execFileSync)\s*\(', None),
        ('code', r'(?<![\w$.])eval\s*\(|\bnew\s+Function\s*\(|\b(?:setTimeout|setInterval)\s*\(\s*[\'"`]', None),
        ('html', r'\.(?:innerHTML|outerHTML)\s*\+?=|\binsertAdjacentHTML\s*\(|\bdocument\.write(?:ln)?\s*\('
                 r'|\bdangerouslySetInnerHTML\b', None),
        ('file', r'\bfs(?:\.promises)?\.(?:readFile|readFileSync|writeFile|writeFileSync|createReadStream|createWriteStream'
                 r'|unlink|unlinkSync|rm|rmSync|open|openSync|readdir|appendFile)\s*\(|\b(?:res|reply)\.(?:sendFile|download)\s*\(',
         'variable'),
        ('deserialize', r'\bunserialize\s*\(', None),
        ('object-merge', r'\bObject\.assign\s*\(|(?<![\w$])(?:_\.)?(?:merge|mergeWith|defaultsDeep|extend)\s*\(', None),
        ('regex', r'\bnew\s+RegExp\s*\(|(?<![\w$.])RegExp\s*\(', 'variable'),
    ],
    'java': [
        ('sql', r'\.(?:executeQuery|executeUpdate|executeLargeUpdate|execute|prepareStatement|prepareCall|createQuery'
                r'|createNativeQuery|addBatch|queryForList|queryForObject|update)\s*\(', 'built'),
        ('shell', r'\bRuntime\.getRuntime\s*\(\s*\)\s*\.exec\s*\(|\b(?:new\s+)?ProcessBuilder\s*\(', None),
        ('code', r'\bScriptEngine\b|\.eval\s*\(', None),
        ('html', r'\.getWriter\s*\(\s*\)\s*\.(?:print|println|write)\s*\(', 'built'),
        ('file', r'(?<![\w$.])(?:new\s+)?(?:File|FileInputStream|FileOutputStream|FileReader|FileWriter|RandomAccessFile)'
                 r'\s*\(|\b(?:Paths\.get|Path\.of)\s*\(', 'variable'),
        ('deserialize', r'\b(?:new\s+)?ObjectInputStream\s*\(|\.readObject\s*\(|\bXMLDecoder\b|\benableDefaultTyping\s*\('
                        r'|\b(?:new\s+)?Yaml\s*\(', None),
        ('regex', r'\bPattern\.compile\s*\(|\.matches\s*\(|\.replaceAll\s*\(', 'variable'),
    ],
    'go': [
        ('sql', r'\.(?:Query|QueryRow|QueryContext|QueryRowContext|Exec|ExecContext|Prepare|PrepareContext|Raw|Where)\s*\(',
         'built'),
        ('shell', r'\bexec\.Command(?:Context)?\s*\(', None),
        ('html', r'\btemplate\.(?:HTML|JS|URL|HTMLAttr)\s*\(', None),
        ('file', r'\bos\.(?:Open|OpenFile|Create|ReadFile|WriteFile|Remove|RemoveAll|ReadDir)\s*\(|\bioutil\.(?:ReadFile'
                 r'|WriteFile)\s*\(|\bhttp\.ServeFile\s*\(|\bfilepath\.Join\s*\(', 'variable'),
        ('deserialize', r'\bgob\.NewDecoder\s*\(', None),
    ],
}
SINKS['kotlin'] = SINKS['java']
ACQUIRE = {
    'js': (r'\.connect\s*\(|\bcreate(?:Read|Write)Stream\s*\(|\bfs(?:\.promises)?\.open(?:Sync)?\s*\(|\.acquire\s*\('
           r'|(?<![\w$.])setInterval\s*\(|\.addEventListener\s*\(',
           r'\.(?:end|close|release|destroy|disconnect)\s*\(|\bclearInterval\s*\(|\.removeEventListener\s*\(|\bfinally\b'
           r'|\bawait\s+using\b|\bpipeline\s*\(|\.pipe\s*\('),
    'java': (r'(?<![\w$.])(?:new\s+)?(?:FileInputStream|FileOutputStream|FileReader|FileWriter|BufferedReader|BufferedWriter'
             r'|RandomAccessFile|Socket|ServerSocket|ZipFile|Scanner)\s*\(|\.getConnection\s*\(|\.(?:lock|lockInterruptibly)'
             r'\s*\(\s*\)|\.openStream\s*\(',
             r'\.(?:close|unlock|release|disconnect)\s*\(|\btry\s*\(|\.use\s*\{|\bwithLock\b'),
    'go': (r'\bos\.(?:Open|OpenFile|Create)\s*\(|\.(?:Lock|RLock)\s*\(\s*\)|\bsql\.Open\s*\(|\.Begin(?:Tx)?\s*\('
           r'|\bhttp\.(?:Get|Post|PostForm|Head)\s*\(|\bnet\.Dial\w*\s*\(',
           r'\bdefer\b|\.(?:Close|Unlock|RUnlock|Rollback|Commit)\s*\('),
}
ACQUIRE['kotlin'] = ACQUIRE['java']
LOG_CALL = re.compile(r'(?:console\.\w+|(?:this\.)?_?(?:log|logger|LOG|LOGGER)\.\w+|System\.(?:out|err)\.print\w*'
                      r'|\w+\.printStackTrace|log\.Print\w*|fmt\.Print\w*|print(?:ln)?)\s*\(')
DEFAULT_RETURN = re.compile(r'return\s*(?:null|undefined|false|0|-1|\[\s*\]|\{\s*\}|nil|""|\'\'|)\s*;?')
TIMEOUT_WORDS = re.compile(r'timeout|signal|deadline|context\.With', re.I)


def variable_arg(arg):
    return bool(re.search(r'[A-Za-z_$]', arg))


def built_arg(arg):
    return '+' in arg or '${' in arg or bool(re.search(r'\b(?:Sprintf|format)\s*\(', arg))


class TextFile:
    def __init__(self, path, src, lang):
        self.path, self.lang = path, lang
        self.text, self.interps = strip(src, lang)
        self.nl = [i for i, c in enumerate(self.text) if c == '\n']
        self.pairs = bracket_map(self.text)
        self.fns = find_functions(self.text, lang, self.pairs)
        for f in self.fns:
            f.update(nodes=[], decisions=0)

    def line(self, pos):
        return bisect.bisect_left(self.nl, pos) + 1

    def arg(self, open_pos):
        close = self.pairs.get(open_pos, -1)
        return self.text[open_pos + 1:close] if close > 0 else ''

    def block(self, pos):
        """Text of the first {...} block at or after pos."""
        o = self.text.find('{', pos)
        close = self.pairs.get(o, -1) if o >= 0 else -1
        return self.text[o + 1:close] if close > 0 else None

    def owner(self, pos):
        best = None
        for f in self.fns:
            if f['start'] <= pos < f['end'] and (best is None or f['start'] > best['start']):
                best = f
        return best

    def add(self, pos, family, kind, detail='', weight=0):
        f = self.owner(pos)
        if f is not None:
            f['nodes'].append(mk(self.line(pos), family, kind, detail))
            f['decisions'] += weight

    def scan(self):
        t, lang = self.text, self.lang
        for kind, pat in DECISIONS[lang]:
            for m in re.finditer(pat, t):
                if kind == 'when-branch' and re.fullmatch(r'\s*else\s*->', m.group(0)):
                    continue
                self.add(m.start(), 'decision', kind, '', 1)
        for m in re.finditer(SOURCES[lang], t):
            self.add(m.start(), 'boundary', 'source', m.group(0).strip(' ('))
        for m in re.finditer(PARSE[lang], t):
            self.add(m.start(), 'hidden', 'parse', m.group(0).strip(' ('))
        for m in re.finditer(NETWORK[lang], t):
            f = self.owner(m.start())
            body = t[f['body']:f['end']] if f else ''
            name = m.group(0).strip(' (')
            self.add(m.start(), 'hidden', 'network-call' if TIMEOUT_WORDS.search(body) else 'network-no-timeout', name)
            if variable_arg(self.arg(m.end() - 1)):
                self.add(m.start(), 'boundary', 'sink:outbound-request', name)
        for kind, pat, check in SINKS[lang]:
            for m in re.finditer(pat, t):
                arg = self.arg(m.end() - 1) if m.group(0).endswith('(') else ''
                if (check == 'built' and not built_arg(arg)) or (check == 'variable' and not variable_arg(arg)):
                    continue
                self.add(m.start(), 'boundary', 'sink:' + kind, m.group(0).strip(' (=+'))
        self.scan_hidden()
        self.scan_gaps()
        self.scan_resources()

    def scan_hidden(self):
        t, lang = self.text, self.lang
        for kind, pat in (('division', r'(?<=[\w)\]])\s*/(?![/*=])(?=\s*[\w(])'),
                          ('modulo', r'(?<=[\w)\]])\s*%(?!=)(?=\s*[\w(])'),
                          ('index-or-key', r'(?<=[\w)\]])\[(?!\s*\])')):
            for m in re.finditer(pat, t):
                if kind == 'index-or-key' and re.search(r'\bmap$', t[max(0, m.start() - 3):m.start()]):
                    continue  # Go map type, not a lookup
                self.add(m.start(), 'hidden', kind)
        loops = {'js': r'\bwhile\s*\(\s*(?:true|1)\s*\)|\bfor\s*\(\s*;\s*;\s*\)', 'java': r'\bwhile\s*\(\s*true\s*\)'
                 r'|\bfor\s*\(\s*;\s*;\s*\)', 'kotlin': r'\bwhile\s*\(\s*true\s*\)', 'go': r'\bfor\s*\{'}[lang]
        for m in re.finditer(loops, t):
            body = self.block(m.end() - 1 if m.group(0).endswith('{') else m.end())
            if body is not None and not re.search(r'\b(?:break|return|throw|panic)\b', body):
                self.add(m.start(), 'hidden', 'loop-no-exit', 'endless loop with no break, return or throw')
        if lang == 'js':
            for kind, pat in (('loose-equality', r'(?<![=!<>])[=!]=(?!=)'), ('optional-chaining', r'\?\.(?!\d)')):
                for m in re.finditer(pat, t):
                    self.add(m.start(), 'coercion', kind)
            for m in re.finditer(r'(?<![\w$.])parseInt\s*\(', t):
                if ',' not in self.arg(m.end() - 1):
                    self.add(m.start(), 'coercion', 'parseInt-no-radix')
            for pos in self.interps:
                self.add(pos, 'coercion', 'template-interpolation', 'shows "undefined", "null" or "[object Object]"')
            for m in re.finditer(r'\.(?:find|findLast|at|pop|shift)\s*\(', t):
                self.add(m.start(), 'hidden', 'may-return-undefined', m.group(0).strip('.( '))
        if lang == 'kotlin':
            for m in re.finditer(r'!!', t):
                self.add(m.start(), 'hidden', 'not-null-assertion', 'throws when the value is null')
        if lang == 'go':
            for m in re.finditer(r'\.\(\s*(?!type\b)[\w.*\[\]]+\s*\)', t):
                start = t.rfind('\n', 0, m.start()) + 1
                if not re.search(r',\s*\w+\s*:?=[^=]*$', t[start:m.start()]):
                    self.add(m.start(), 'hidden', 'type-assertion', 'panics when the type does not match')
        for f in self.fns:
            name = re.escape(f['name'])
            if f['name'].isidentifier() and re.search(r'(?:(?<![\w$.])|(?<=this\.))' + name + r'\s*\(',
                                                      t[f['body']:f['end']]):
                self.add(f['body'], 'hidden', 'recursion', f['name'])

    def scan_gaps(self):
        t, lang = self.text, self.lang
        for m in re.finditer(r'\bif\b', t):
            if re.search(r'\belse\s*$', t[max(0, m.start() - 12):m.start()]):
                continue
            branches, has_else, pos = 0, False, m.end()
            while True:
                end = self.branch_end(pos)
                if end < 0:
                    branches = 0
                    break
                branches += 1
                j = self.skip_ws(end + 1)
                if re.match(r'else\b', t[j:j + 5]):
                    k = self.skip_ws(j + 4)
                    if re.match(r'if\b', t[k:k + 3]):
                        pos = k + 2
                        continue
                    has_else = True
                break
            if branches >= 2 and not has_else:
                self.add(m.start(), 'decision', 'if-chain-no-else', f'{branches} branches, no final else')
        switch = {'js': (r'\bswitch\s*\(', r'\bdefault\b'), 'java': (r'\bswitch\s*\(', r'\bdefault\b'),
                  'go': (r'\bswitch\b', r'\bdefault\s*:'), 'kotlin': (r'\bwhen\b', r'\belse\s*->')}[lang]
        for m in re.finditer(switch[0], t):
            pos = self.pairs.get(m.end() - 1, m.end()) if m.group(0).endswith('(') else m.end()
            body = self.block(pos)
            if body is not None and not re.search(switch[1], body):
                self.add(m.start(), 'decision', 'switch-no-default', 'no default branch')
        catch = r'\bif\s+err\s*!=\s*nil\s*\{' if lang == 'go' else r'\bcatch\b\s*(?:\([^)]*\))?\s*\{'
        for m in re.finditer(catch, t):
            kind = self.handler_kind(self.block(m.end() - 1))
            if kind:
                self.add(m.start(), 'error-path', kind)
        if lang == 'js':
            for m in re.finditer(r'\.catch\(\s*(?:\([^)]*\)|\w+)\s*=>\s*(?:\{\s*\}|null|undefined|\[\s*\]|void 0)\s*\)', t):
                self.add(m.start(), 'error-path', 'catch-swallows', 'promise rejection ignored')
        if lang == 'go':
            for m in re.finditer(r'(?m)^[ \t]*(?:[\w.]+\s*,\s*)*_\s*(?::=|=)\s*[\w.]+\s*\(', t):
                self.add(m.start() + len(m.group(0)) - len(m.group(0).lstrip()), 'error-path', 'error-ignored',
                         'a result is discarded with _')

    def handler_kind(self, body):
        if body is None:
            return None
        rest = body
        while True:
            m = LOG_CALL.search(rest)
            if not m:
                break
            close = bracket_map(rest).get(m.end() - 1, -1)
            if close < 0:
                break
            rest = rest[:m.start()] + rest[close + 1:]
        rest = re.sub(r'[\s;]+', ' ', rest).strip()
        if not rest:
            return 'catch-swallows'
        return 'catch-returns-default' if DEFAULT_RETURN.fullmatch(rest) else None

    def branch_end(self, pos):
        if self.lang == 'go':
            o = self.text.find('{', pos)
        else:
            j = self.skip_ws(pos)
            if self.text[j:j + 1] != '(':
                return -1
            o = self.skip_ws(self.pairs.get(j, len(self.text)) + 1)
            if self.text[o:o + 1] != '{':
                return -1
        return self.pairs.get(o, -1) if o >= 0 else -1

    def skip_ws(self, j):
        while j < len(self.text) and self.text[j].isspace():
            j += 1
        return j

    def scan_resources(self):
        acquire, release = ACQUIRE[self.lang]
        for f in self.fns:
            body = self.text[f['body']:f['end']]
            if re.search(release, body):
                continue
            for m in re.finditer(acquire, body):
                self.add(f['body'] + m.start(), 'resource', 'acquire-no-release', m.group(0).strip(' ('))


def analyze_text(path, src, lang):
    tf = TextFile(path, src, lang)
    tf.scan()
    out = []
    for f in tf.fns:
        out.append({'file': path, 'name': f['name'], 'line': tf.line(f['start']), 'lang': lang, 'exact': False,
                    'decisions': f['decisions'], 'vg': f['decisions'] + 1, 'nodes': finish(f['nodes'])})
    return out, None


# ── Files, history, output ──────────────────────────────────────────────────

def is_test(rel):
    return any(fnmatch.fnmatch(rel, p) for p in TEST_PATTERNS)


def iter_files(root, excludes, include_tests):
    if os.path.isfile(root):
        yield root
        return
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith('.'))
        for name in sorted(files):
            path = os.path.join(d, name)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            if os.path.splitext(name)[1] not in LANG_BY_EXT or name.endswith(('.d.ts', '.min.js')):
                continue
            if (not include_tests and is_test('/' + rel)) or any(fnmatch.fnmatch(rel, g) for g in excludes):
                continue
            yield path


def analyze_file(path):
    lang = LANG_BY_EXT.get(os.path.splitext(path)[1])
    if lang is None:
        return [], f'{path}: unsupported file type'
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            src = fh.read()
    except OSError as e:
        return [], f'{path}: cannot read ({e.strerror})'
    return analyze_py(path, src) if lang == 'py' else analyze_text(path, src, lang)


def collect(root, excludes, include_tests):
    fns, warnings = [], []
    for path in iter_files(root, excludes, include_tests):
        found, warn = analyze_file(path)
        fns.extend(found)
        if warn:
            warnings.append(warn)
    return fns, warnings


def git_history(root, commits):
    """(commits per file, fix commits per file), keyed by real path; None without git."""
    where = root if os.path.isdir(root) else os.path.dirname(os.path.abspath(root))
    try:
        top = subprocess.run(['git', '-C', where, 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, timeout=60)
        if top.returncode != 0:
            return None
        top = top.stdout.strip()
        log = subprocess.run(['git', '-C', top, 'log', '-n', str(commits), '--no-merges', '--format=%x00%s',
                              '--name-only'], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    churn, fixes = collections.Counter(), collections.Counter()
    for chunk in log.stdout.split('\0')[1:]:
        lines = chunk.split('\n')
        is_fix = bool(FIX_WORDS.search(lines[0]))
        for rel in filter(None, (x.strip() for x in lines[1:])):
            path = os.path.realpath(os.path.join(top, rel))
            churn[path] += 1
            fixes[path] += is_fix
    return churn, fixes


def display(path, root):
    if os.path.isfile(root):
        return path
    return os.path.relpath(path, root).replace(os.sep, '/')


def rank_rows(fns, root, history):
    churn, fixes = history or ({}, {})
    rows = []
    for f in fns:
        real = os.path.realpath(f['file'])
        sinks = sum(1 for n in f['nodes'] if n['kind'].startswith('sink:'))
        sources = sum(1 for n in f['nodes'] if n['kind'] == 'source')
        c, x = churn.get(real, 0), fixes.get(real, 0)
        score = (f['vg'] - 1) + 3 * sinks + 2 * sources + 0.5 * min(c, 10) + x
        rows.append({'location': f"{display(f['file'], root)}:{f['line']}", 'function': f['name'], 'lang': f['lang'],
                     'exact': f['exact'], 'vg': f['vg'], 'sources': sources, 'sinks': sinks, 'commits': c,
                     'fix_commits': x, 'score': score})
    return sorted(rows, key=lambda r: (-r['score'], r['location']))


def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2)
        fh.write('\n')


def cmd_rank(a):
    fns, warnings = collect(a.path, a.exclude, a.include_tests)
    history = None if a.no_history else git_history(a.path, a.commits)
    rows = rank_rows(fns, a.path, history)
    print(f'{"score":>6} {"v(G)":>5} {"src":>4} {"sink":>5} {"commits":>8} {"fixes":>6}  location  function')
    for r in rows[:a.top]:
        mark = '' if r['exact'] else '  (approx)'
        print(f"{r['score']:>6.1f} {r['vg']:>5} {r['sources']:>4} {r['sinks']:>5} {r['commits']:>8} "
              f"{r['fix_commits']:>6}  {r['location']}  {r['function']}{mark}")
    print(f'{len(rows)} functions ranked' + ('' if history else '; no git history used') + '.')
    for w in warnings:
        print('warning: ' + w, file=sys.stderr)
    if a.json:
        write_json(a.json, rows)
    return 0


def cmd_nodes(a):
    fns, warnings = collect(a.path, a.exclude, a.include_tests)
    families = set(a.family.split(',')) if a.family else None
    unknown = (families or set()) - set(FAMILIES)
    if unknown:
        print(f'error: unknown family {", ".join(sorted(unknown))}; use {", ".join(FAMILIES)}', file=sys.stderr)
        return 2
    keep = []
    for f in fns:
        if a.function and a.function not in (f['name'], f['name'].rsplit('.', 1)[-1]):
            continue
        f = dict(f, file=display(f['file'], a.path))
        f['nodes'] = [n for n in f['nodes'] if families is None or n['family'] in families]
        keep.append(f)
    total = 0
    for f in keep:
        print(f"{f['file']}:{f['line']}  {f['name']}  v(G)={f['vg']}  decisions={f['decisions']}  "
              f"{'exact' if f['exact'] else 'approx'}")
        for n in f['nodes']:
            print(f"  {n['line']:>5}  {n['family']:<10}  {n['kind']:<24}  {n['detail']}".rstrip())
        total += len(f['nodes'])
    print(f'{len(keep)} functions, {total} nodes. Each row is a place to read, not a finding.')
    for w in warnings:
        print('warning: ' + w, file=sys.stderr)
    if a.json:
        write_json(a.json, keep)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('rank', 'nodes'):
        p = sub.add_parser(name)
        p.add_argument('path')
        p.add_argument('--json', metavar='OUT')
        p.add_argument('--exclude', action='append', default=[], metavar='GLOB')
        p.add_argument('--include-tests', action='store_true')
        if name == 'rank':
            p.add_argument('--top', type=int, default=25)
            p.add_argument('--commits', type=int, default=500)
            p.add_argument('--no-history', action='store_true')
        else:
            p.add_argument('--function', metavar='NAME')
            p.add_argument('--family', metavar='a,b')
    a = ap.parse_args(argv)
    if not os.path.exists(a.path):
        print(f'error: {a.path} does not exist', file=sys.stderr)
        return 2
    return cmd_rank(a) if a.cmd == 'rank' else cmd_nodes(a)


if __name__ == '__main__':
    sys.exit(main())
