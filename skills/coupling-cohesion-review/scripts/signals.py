#!/usr/bin/env python3
"""Collect coupling and cohesion signals from a source tree.

Read-only. Python 3.8+ standard library only. Every result is a *signal*
(weak evidence) that tells the reviewer where to read code; it is never a
verdict on its own.

Supported languages (import graph): JavaScript / TypeScript, Python, Java,
Kotlin, Go. Other files are counted for size and history only.

Usage:
  python3 -I signals.py ROOT [options]

Options:
  --unit file|dir       Graph node: one file (default) or one directory.
                        Use "dir" for Go, or to see cycles between folders.
  --layers A>B>C        Optional folder order, high to low (e.g. "ui>domain>data").
                        Imports from a lower folder to a higher one are reported.
  --folder-depth N      Which path level counts as a "folder" for folder-level
                        results (0 = top level). Default: one level below the
                        directory that holds most of the files (e.g. src/).
  --exclude GLOB        Extra path glob to skip (repeatable).
  --include-tests       Also scan test files (skipped by default).
  --commits N           How many recent commits to read for history (default 500).
  --max-commit-files N  Skip commits touching more than N files when pairing
                        co-changes (default 20; large commits are usually sweeps).
  --top N               Rows per section in the printed summary (default 25).
  --only a,b            Print only these sections.
  --json PATH           Also write every result to PATH as JSON.
"""
import argparse
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
    '.ts': 'js', '.tsx': 'js', '.mts': 'js', '.cts': 'js', '.js': 'js', '.jsx': 'js', '.mjs': 'js', '.cjs': 'js',
    '.py': 'py', '.java': 'java', '.kt': 'kotlin', '.kts': 'kotlin', '.go': 'go',
}
JS_EXTS = ['.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs']
TEST_PATTERNS = [
    '*/__tests__/*', '*/__mocks__/*', '*/test/*', '*/tests/*', '*/testing/*', '*/spec/*',
    '*.test.*', '*.spec.*', '*_test.go', '*/test_*.py', '*_test.py', '*/conftest.py',
    '*/src/test/*', '*/androidTest/*', '*Test.java', '*Test.kt', '*Tests.java', '*Tests.kt',
]
ENTRY_STEMS = {'main', 'index', 'app', '__main__', '__init__', 'setup', 'manage', 'cli', 'server', 'conftest', 'wsgi', 'asgi'}
GRAB_BAG = re.compile(r'(?:^|[_\-.]|(?<=[a-z]))(?:utils?|utilities|helpers?|misc|common|shared|managers?|stuff)$'
                      r'|^(?:base|general|tools?)$', re.I)


# ── file discovery ──────────────────────────────────────────────────────────

def discover(root, excludes, include_tests):
    files = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
        for n in names:
            p = os.path.join(d, n)
            ext = os.path.splitext(n)[1]
            if ext not in LANG_BY_EXT or n.endswith('.d.ts'):
                continue
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            probe = '/' + rel
            if any(fnmatch.fnmatch(probe, g) or fnmatch.fnmatch(rel, g) for g in excludes):
                continue
            if not include_tests and any(fnmatch.fnmatch(probe, g) for g in TEST_PATTERNS):
                continue
            files.append(p)
    return sorted(files)


def read(p):
    try:
        with open(p, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def strip_comments(text, lang):
    """Remove comments (string-aware) so commented-out or example imports are
    not counted. Line breaks are kept, so line numbers stay correct. Python
    docstrings are blanked too, since they often hold example code."""
    py = lang == 'py'
    quotes = ('"""', "'''", '"', "'") if py else ('"', "'", '`')
    out, i, n = [], 0, len(text)
    while i < n:
        if py and text.startswith('#', i) or not py and text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        if not py and text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append('\n' * text.count('\n', i, j))
            i = j
            continue
        q = next((q for q in quotes if text.startswith(q, i)), None)
        if q:
            j = i + len(q)
            while j < n and not text.startswith(q, j):
                if text[j] == '\\':
                    j += 1
                elif text[j] == '\n' and len(q) == 1 and q != '`':
                    break  # unterminated single-line string: stop at the line end
                j += 1
            j = min(n, j + len(q))
            chunk = text[i:j]
            out.append('\n' * chunk.count('\n') if py and len(q) == 3 else chunk)
            i = j
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


# ── import extraction and resolution ────────────────────────────────────────

JS_IMPORT = re.compile(
    r"""(?P<kw>import|export)\s+(?P<type>type\s+)?(?P<what>[^'";]*?)\s*from\s*['"](?P<a>[^'"]+)['"]"""
    r"""|import\s*['"](?P<b>[^'"]+)['"]"""
    r"""|import\(\s*['"](?P<c>[^'"]+)['"]\s*\)"""
    r"""|require\(\s*['"](?P<d>[^'"]+)['"]\s*\)"""
    r"""|new\s+URL\(\s*['"](?P<e>\.[^'"]+)['"]\s*,\s*import\.meta\.url""",
    re.S)


def js_imports(code):
    out = []
    for m in JS_IMPORT.finditer(code):
        spec = m.group('a') or m.group('b') or m.group('c') or m.group('d') or m.group('e')
        type_only = False
        if m.group('a'):
            what = m.group('what') or ''
            names = re.findall(r'[\w$]+(?:\s+as\s+[\w$]+)?|type\s+[\w$]+', what.strip('{} \n'))
            inner = re.search(r'\{([^}]*)\}', what)
            all_typed = bool(inner) and not re.sub(r'\{[^}]*\}', '', what).strip(' ,') and all(
                s.strip().startswith('type ') for s in inner.group(1).split(',') if s.strip())
            type_only = bool(m.group('type')) or (all_typed and bool(names))
        out.append((spec, type_only))
    return out


def load_js_aliases(root):
    """Read compilerOptions.paths from every tsconfig/jsconfig under ROOT."""
    aliases = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
        for n in names:
            if not re.match(r'^(tsconfig|jsconfig)(\.[\w-]+)?\.json$', n):
                continue
            raw = strip_comments(read(os.path.join(d, n)), 'js')
            raw = re.sub(r',(\s*[}\]])', r'\1', raw)
            try:
                opts = json.loads(raw).get('compilerOptions', {})
            except ValueError:
                continue
            base = os.path.normpath(os.path.join(d, opts.get('baseUrl', '.')))
            for pat, targets in (opts.get('paths') or {}).items():
                for t in targets:
                    aliases.append((pat, os.path.normpath(os.path.join(base, t))))
    aliases.sort(key=lambda a: -len(a[0]))
    return aliases


def resolve_js(frm, spec, fileset, aliases):
    cands = []
    if spec.startswith('.'):
        cands.append(os.path.normpath(os.path.join(os.path.dirname(frm), spec)))
    else:
        for pat, target in aliases:
            if pat.endswith('*') and spec.startswith(pat[:-1]):
                cands.append(target.replace('*', spec[len(pat) - 1:]))
            elif pat == spec:
                cands.append(target)
    for base in cands:
        stem = re.sub(r'\.(m?js|cjs|jsx)$', '', base)
        for c in [base] + [stem + e for e in JS_EXTS] + [os.path.join(base, 'index' + e) for e in JS_EXTS]:
            if c in fileset:
                return c
    return None


PY_IMPORT = re.compile(r'(?m)^[ \t]*(?:from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[\w*, \t]+)|import[ \t]+([\w., \t]+))')


def py_index(files, root):
    index = collections.defaultdict(set)
    top = os.path.dirname(root)
    for f in files:
        if not f.endswith('.py'):
            continue
        parts = os.path.relpath(f, top).replace(os.sep, '/')[:-3].split('/')
        if parts[-1] == '__init__':
            parts = parts[:-1]
        for k in range(len(parts)):
            index['.'.join(parts[k:])].add(f)
    return index


def py_imports(code):
    out = []
    for m in PY_IMPORT.finditer(code):
        if m.group(4):
            out += [(0, n.split()[0], None) for n in m.group(4).split(',') if n.strip()]
        else:
            names = [n.split()[0] for n in m.group(3).replace('(', ' ').replace(')', ' ').split(',') if n.strip()]
            out.append((len(m.group(1)), m.group(2), names))
    return out


def resolve_py(frm, item, index, root):
    dots, mod, names = item

    def uniq(name):
        hit = index.get(name)
        return next(iter(hit)) if hit and len(hit) == 1 else None

    if dots:
        pkg = os.path.relpath(os.path.dirname(frm), os.path.dirname(root)).replace(os.sep, '/').split('/')
        pkg = pkg[:len(pkg) - (dots - 1)] if dots > 1 else pkg
        mod = '.'.join(pkg + ([mod] if mod else []))
    res = []
    for n in names or [None]:
        target = (uniq(mod + '.' + n) if n and n != '*' else None) or uniq(mod)
        if target:
            res.append(target)
    return res


JAVA_PKG = re.compile(r'(?m)^\s*package\s+([\w.]+)')
JAVA_IMPORT = re.compile(r'(?m)^[ \t]*import[ \t]+(?:static[ \t]+)?(\w+(?:\.\w+)*)(\.\*)?')


def jvm_index(files, texts):
    by_fq, by_pkg = {}, collections.defaultdict(set)
    for f in files:
        if LANG_BY_EXT.get(os.path.splitext(f)[1]) not in ('java', 'kotlin'):
            continue
        m = JAVA_PKG.search(texts[f])
        pkg = m.group(1) if m else ''
        stem = os.path.splitext(os.path.basename(f))[0]
        by_fq[(pkg + '.' if pkg else '') + stem] = f
        by_pkg[pkg].add(f)
    return by_fq, by_pkg


def resolve_jvm(name, wildcard, by_fq, by_pkg):
    if wildcard:
        return sorted(by_pkg.get(name, ()))
    parts = name.split('.')
    for k in range(len(parts), 0, -1):  # a.b.Outer.Inner or a.b.Cls.staticMember
        hit = by_fq.get('.'.join(parts[:k]))
        if hit:
            return [hit]
    return []


GO_IMPORT_BLOCK = re.compile(r'import\s*\(([\s\S]*?)\)')
GO_IMPORT_ONE = re.compile(r'(?m)^\s*import\s+(?:[\w.]+\s+)?"([^"]+)"')


def go_module(root):
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        if 'go.mod' in names:
            m = re.search(r'(?m)^module\s+(\S+)', read(os.path.join(d, 'go.mod')))
            if m:
                return m.group(1), d
    return None, None


def go_imports(code):
    specs = re.findall(r'"([^"]+)"', ' '.join(GO_IMPORT_BLOCK.findall(code)))
    return specs + GO_IMPORT_ONE.findall(code)


# ── per-file heuristics ─────────────────────────────────────────────────────

MUTABLE = {
    'js': re.compile(r'(?m)^(?:export\s+)?(?:let|var)\s+[\w$]+.*$'),
    # `global` statements, plus module-level containers whose name is not ALL_CAPS or __dunder__
    'py': re.compile(r'(?m)^[ \t]+global[ \t]+\w+.*$'
                     r'|^(?!__)(?![A-Z0-9_]+\b)[A-Za-z_]\w*[ \t]*(?::[^=\n]+)?=[ \t]*(?:\[|\{|set\(|dict\(|list\(|defaultdict\().*$'),
    'java': re.compile(r'(?m)^\s+(?:(?:public|protected|private)\s+)?static\s+(?!final\b)(?!class\b|interface\b|enum\b|record\b)[\w<>\[\],.? ]+\s+\w+\s*(?:=[^;]*)?;.*$'),
    'kotlin': re.compile(r'(?m)^(?:(?:private|internal|public)\s+)?var\s+\w+.*$'),
    'go': re.compile(r'(?m)^var\s+\w+.*$|^var\s*\('),
}
FLAG_PARAM = {
    'js': re.compile(r'(?:function\s*[\w$]*|[\w$]+\s*=\s*(?:async\s*)?)\(([^()]*?\b[\w$]+\??\s*:\s*boolean\b[^()]*)\)'),
    'py': re.compile(r'def\s+\w+\s*\(([^)]*(?::\s*bool\b|=\s*(?:True|False)\b)[^)]*)\)'),
    'java': re.compile(r'\b\w+\s*\(([^()]*\bboolean\s+\w+[^()]*)\)\s*(?:throws[\w\s,.]+)?\{'),
    'kotlin': re.compile(r'fun\s+[\w.<>]+\s*\(([^()]*:\s*Boolean\b[^()]*)\)'),
    'go': re.compile(r'func\s+(?:\([^)]*\)\s*)?\w+\s*\(([^()]*\bbool\b[^()]*)\)'),
}
TOP_DECL = {
    'js': re.compile(r'(?m)^export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class|let|var|type|interface|enum)\b'),
    'py': re.compile(r'(?m)^(?:async\s+def|def|class)\s+[A-Za-z]\w*'),
    'java': re.compile(r'(?m)^\s+public\s+(?!class\b)[^=;(]*\('),
    'kotlin': re.compile(r'(?m)^(?:public\s+|internal\s+)?(?:fun|class|object|interface|val|var)\s'),
    'go': re.compile(r'(?m)^(?:func\s+(?:\([^)]*\)\s*)?[A-Z]\w*|type\s+[A-Z]\w*)'),
}


# ── graph algorithms ────────────────────────────────────────────────────────

def sccs(graph, nodes):
    """Tarjan, iterative. Returns components with more than one node."""
    index, low, on, stack, out, counter = {}, {}, set(), [], [], [0]
    for start in nodes:
        if start in index:
            continue
        work = [(start, iter(sorted(graph.get(start, ()))))]
        index[start] = low[start] = counter[0]; counter[0] += 1
        stack.append(start); on.add(start)
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter[0]; counter[0] += 1
                    stack.append(w); on.add(w)
                    work.append((w, iter(sorted(graph.get(w, ())))))
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop(); on.discard(w); comp.append(w)
                        if w == v:
                            break
                    if len(comp) > 1:
                        out.append(sorted(comp))
    return sorted(out, key=len, reverse=True)


# ── history ─────────────────────────────────────────────────────────────────

def history(root, known, commits, max_files):
    churn, pairs = collections.Counter(), collections.Counter()
    try:
        top = subprocess.run(['git', '-C', root, 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, check=True).stdout.strip()
        log = subprocess.run(['git', '-C', root, 'log', '-n', str(commits), '--no-merges', '--name-only',
                              '--pretty=format:%x00'], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None, None, 0
    real = {os.path.realpath(k): k for k in known}
    n = 0
    for chunk in log.split('\x00'):
        fs = sorted({real[p] for x in chunk.split('\n') if x.strip()
                     if (p := os.path.realpath(os.path.join(top, x))) in real})
        if not fs:
            continue
        n += 1
        for f in fs:
            churn[f] += 1
        if 2 <= len(fs) <= max_files:
            for i in range(len(fs)):
                for j in range(i + 1, len(fs)):
                    pairs[(fs[i], fs[j])] += 1
    return churn, pairs, n


# ── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('root')
    ap.add_argument('--unit', choices=['file', 'dir'], default='file')
    ap.add_argument('--layers', default='')
    ap.add_argument('--folder-depth', type=int, default=-1)
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--include-tests', action='store_true')
    ap.add_argument('--commits', type=int, default=500)
    ap.add_argument('--max-commit-files', type=int, default=20)
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--only', default='')
    ap.add_argument('--json', default='')
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    files = discover(root, a.exclude, a.include_tests)
    fileset = set(files)
    texts = {f: read(f) for f in files}
    lang = {f: LANG_BY_EXT[os.path.splitext(f)[1]] for f in files}
    rel = lambda p: os.path.relpath(p, root).replace(os.sep, '/')

    aliases = load_js_aliases(root) if 'js' in lang.values() else []
    pyidx = py_index(files, root) if 'py' in lang.values() else {}
    by_fq, by_pkg = jvm_index(files, texts) if {'java', 'kotlin'} & set(lang.values()) else ({}, {})
    gomod, godir = go_module(root) if 'go' in lang.values() else (None, None)
    go_by_dir = collections.defaultdict(list)
    for f in files:
        if lang[f] == 'go':
            go_by_dir[os.path.dirname(f)].append(f)

    edges = collections.defaultdict(dict)  # src -> {dst: type_only}
    external = collections.defaultdict(set)

    def add(src, dst, type_only=False):
        if dst and dst != src:
            edges[src][dst] = edges[src].get(dst, True) and type_only

    for f in files:
        code = strip_comments(texts[f], lang[f])
        L = lang[f]
        if L == 'js':
            for spec, t in js_imports(code):
                r = resolve_js(f, spec, fileset, aliases)
                if r:
                    add(f, r, t)
                elif not spec.startswith('.'):
                    external[spec.split('/')[0] if not spec.startswith('@') else '/'.join(spec.split('/')[:2])].add(f)
        elif L == 'py':
            for item in py_imports(code):
                hits = resolve_py(f, item, pyidx, root)
                for h in hits:
                    add(f, h)
                if not hits and not item[0]:
                    external[item[1].split('.')[0]].add(f)
        elif L in ('java', 'kotlin'):
            for name, wild in JAVA_IMPORT.findall(code):
                hits = resolve_jvm(name, bool(wild), by_fq, by_pkg)
                for h in hits:
                    add(f, h)
                if not hits:
                    external['.'.join(name.split('.')[:2])].add(f)
        elif L == 'go':
            for spec in go_imports(code):
                if gomod and (spec == gomod or spec.startswith(gomod + '/')):
                    d = os.path.normpath(os.path.join(godir, spec[len(gomod):].lstrip('/')))
                    for h in go_by_dir.get(d, []):
                        add(f, h)
                else:
                    external[spec].add(f)

    # optional collapse to directories
    if a.unit == 'dir':
        node = lambda f: os.path.dirname(f)
        g2 = collections.defaultdict(dict)
        for s, ds in edges.items():
            for d, t in ds.items():
                if node(s) != node(d):
                    g2[node(s)][node(d)] = g2[node(s)].get(node(d), True) and t
        graph, nodes = g2, sorted({node(f) for f in files})
    else:
        graph, nodes = edges, files

    runtime = {s: {d for d, t in ds.items() if not t} for s, ds in graph.items()}
    allg = {s: set(ds) for s, ds in graph.items()}
    fanin = collections.Counter(d for ds in allg.values() for d in ds)
    cyc_runtime = sccs(runtime, nodes)
    in_runtime = {n for c in cyc_runtime for n in c}
    cyc_typeonly = [c for c in sccs(allg, nodes) if not set(c) <= in_runtime]

    # folders: the path part just below the main source directory. "Main" is
    # the deepest directory that holds at least 80% of the files (e.g. src/),
    # unless --folder-depth sets it.
    parts = [rel(f).split('/') for f in files]
    common = a.folder_depth if a.folder_depth >= 0 else 0
    while a.folder_depth < 0 and parts:
        heads = collections.Counter(tuple(p[:common + 1]) for p in parts if len(p) > common + 1)
        if not heads or heads.most_common(1)[0][1] < 0.8 * len(parts):
            break
        common += 1
    main_prefix = collections.Counter(tuple(p[:common]) for p in parts).most_common(1)[0][0] if parts else ()

    def folder(f):
        p = rel(f).split('/')
        if tuple(p[:common]) != main_prefix:
            return '/'.join(p[:1]) + '/ (outside main source dir)'
        return p[common] if len(p) > common + 1 else '(files at top)'
    fpair = collections.Counter()
    for s, ds in edges.items():
        for d in ds:
            if folder(s) != folder(d):
                fpair[(folder(s), folder(d))] += 1
    both_ways = []
    for (x, y), n in fpair.items():
        m = fpair.get((y, x))
        if m is None or x > y:
            continue  # one direction only, or the pair was already seen from the other side
        (hi, hi_n), (lo, lo_n) = sorted([((x, y), n), ((y, x), m)], key=lambda e: -e[1])
        both_ways.append({'minority': f'{lo[0]} -> {lo[1]}', 'minority_count': lo_n,
                          'majority': f'{hi[0]} -> {hi[1]}', 'majority_count': hi_n})
    both_ways.sort(key=lambda r: (r['minority_count'] / r['majority_count'], -r['majority_count']))
    upward = []
    if a.layers:
        order = {name.strip(): i for i, name in enumerate(a.layers.split('>'))}
        for s, ds in edges.items():
            for d in ds:
                fs, fd = folder(s), folder(d)
                if fs in order and fd in order and order[fs] > order[fd]:
                    upward.append(f'{rel(s)} -> {rel(d)}')

    # unused files: no importer, not an obvious entry point
    importers = {d for ds in edges.values() for d in ds}
    mention_pool = {f: texts[f] for f in files}
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
        for n in names:
            if re.search(r'\.(json|ya?ml|toml|xml|html|cfg|ini|gradle|properties)$', n) and 'lock' not in n:
                p = os.path.join(d, n)
                if os.path.getsize(p) < 2_000_000:
                    mention_pool[p] = read(p)
    unused = []
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0].split('.')[0]
        if f in importers or stem.lower() in ENTRY_STEMS or re.search(r'\.config\.', f):
            continue
        if lang[f] in ('java', 'kotlin', 'go'):
            continue  # same-package references need no import; unused detection is unreliable here
        rx = re.compile(r'\b' + re.escape(stem) + r'\b') if len(stem) >= 4 else None
        mentioned = [rel(p) for p, t in mention_pool.items() if p != f and rx and rx.search(t)][:3]
        unused.append({'file': rel(f), 'lines': texts[f].count('\n') + 1, 'name_mentioned_in': mentioned})

    def hits(rx_map, limit_per_file=5):
        out = []
        for f in files:
            rx = rx_map[lang[f]]  # every supported language has a rule
            code = strip_comments(texts[f], lang[f])
            for m in list(rx.finditer(code))[:limit_per_file]:
                out.append({'file': rel(f), 'line': code[:m.start()].count('\n') + 1,
                            'text': re.sub(r'\s+', ' ', m.group(0)).strip()[:140]})
        return out

    mutable = hits(MUTABLE)
    flags = hits(FLAG_PARAM, 3)
    flag_count = collections.Counter(h['file'] for h in flags)
    decls = {f: len(TOP_DECL[lang[f]].findall(texts[f])) for f in files}

    churn, pairs, ncommits = history(root, fileset, a.commits, a.max_commit_files)
    cochange = []
    if pairs:
        for (x, y), n in pairs.most_common():
            if n < 3:
                break
            if y in allg.get(x, ()) or x in allg.get(y, ()):
                continue
            cochange.append({'a': rel(x), 'b': rel(y), 'together': n,
                             'share': round(n / max(1, min(churn[x], churn[y])), 2)})

    show = rel
    R =collections.OrderedDict()
    R['summary'] = {
        'root': root, 'unit': a.unit, 'files': len(files),
        'lines': sum(t.count('\n') + 1 for t in texts.values()),
        'by_language': dict(collections.Counter(lang.values())),
        'internal_edges': sum(len(v) for v in edges.values()),
        'commits_read': ncommits,
    }
    R['largest'] = sorted(({'file': rel(f), 'lines': texts[f].count('\n') + 1, 'top_level_decls': decls[f]} for f in files),
                          key=lambda x: -x['lines'])
    R['fan_in'] = [{'unit': show(n), 'importers': c} for n, c in fanin.most_common()]
    R['fan_out'] = sorted(({'unit': show(n), 'imports': len(ds)} for n, ds in allg.items()), key=lambda x: -x['imports'])
    R['cycles_runtime'] = [[show(n) for n in c] for c in cyc_runtime]
    R['cycles_type_only'] = [[show(n) for n in c] for c in cyc_typeonly]
    R['folder_edges'] = [{'from': x, 'to': y, 'imports': n} for (x, y), n in fpair.most_common()]
    R['folders_both_ways'] = both_ways
    R['upward_imports'] = sorted(upward)
    R['unused_candidates'] = sorted(unused, key=lambda x: -x['lines'])
    R['module_mutable_state'] = mutable
    R['flag_parameters'] = [{'file': f, 'functions': n} for f, n in flag_count.most_common()]
    R['flag_parameter_examples'] = flags
    R['grab_bag_names'] = [{'file': rel(f), 'lines': texts[f].count('\n') + 1, 'top_level_decls': decls[f]}
                           for f in files if GRAB_BAG.search(os.path.splitext(os.path.basename(f))[0].split('.')[0])]
    R['most_declarations'] = sorted(({'file': rel(f), 'top_level_decls': n} for f, n in decls.items()), key=lambda x: -x['top_level_decls'])
    R['external_spread'] = sorted(({'dependency': k, 'files': len(v)} for k, v in external.items()), key=lambda x: -x['files'])
    R['churn'] = [{'file': rel(f), 'commits': n} for f, n in churn.most_common()] if churn is not None else 'no git history'
    R['cochange_without_import'] = cochange

    if a.json:
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump(R, fh, indent=1)
    only = set(filter(None, a.only.split(',')))
    print('# Signals are weak evidence. Read the code before you classify anything.')
    for k, v in R.items():
        if only and k not in only:
            continue
        print(f'\n== {k}')
        if isinstance(v, list):
            for row in v[:a.top]:
                print('  ', json.dumps(row, ensure_ascii=False))
            if len(v) > a.top:
                print(f'   … {len(v) - a.top} more')
        else:
            print('  ', json.dumps(v, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
