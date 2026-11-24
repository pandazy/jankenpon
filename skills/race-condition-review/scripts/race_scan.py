#!/usr/bin/env python3
"""List race-condition candidates in source code, as a reading list.

Read-only. Python 3.8+ standard library only. Every row is a lead to read,
never a finding on its own (weak evidence at best).

Usage:
  python3 -I race_scan.py PATH [--window N] [--kind a,b] [--json OUT]
                               [--exclude GLOB]... [--include-tests] [--needs-wait]

PATH is a file or a folder. Output: one row per candidate,
  file:line  kind  pattern  detail
followed by a per-file count, highest first, to pick where to read.

Kinds and the race pattern (R1-R11 in SKILL.md) each one hints at:
  check-then-act      R1  a check on shared state, then an action that relies on it
  read-modify-write   R2  a value read, changed, then written back
  select-then-update  R2  an SQL SELECT then UPDATE/INSERT/DELETE nearby
  stale-async-write   R4  state set from an async result with no staleness check
  at-least-once       R6  a retry or message consumer with no visible dedup key
  lifecycle           R9  a timer, listener, subscription or task with no teardown
  lock-across-wait    R10 a lock held across I/O, sleep or await
  nested-locks        R10 a second lock taken while one is held (lock order)
  shared-mutable      R10 module-level or static mutable state
  cache-aside         R11 cache miss -> compute -> set, with no request coalescing
  spawn               --  a place that starts concurrent work (actor inventory)

A row says "guard seen: X" when a protection keyword appears near it. That
does not make the code safe: check that the guard covers the whole window
(a transaction at the default isolation level often does not).
"""
import argparse
import fnmatch
import json
import os
import re
import sys

EXTS = {'.py', '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.java', '.kt', '.go', '.rb', '.php', '.cs', '.rs',
        '.scala', '.swift'}
SKIP_DIRS = {'.git', 'node_modules', 'build', 'dist', 'vendor', '__pycache__', 'venv', '.venv', 'target', 'out',
             'coverage', '.next', '.tox'}
TEST_HINT = re.compile(r'(^|[/\\])(tests?|__tests__|spec|specs)([/\\]|$)|([._-](test|spec)\.\w+$)|(^|[/\\])test_[^/\\]*$')
COMMENT = re.compile(r'^\s*(//|#(?!include)|\*|/\*|--)')
FUNC_START = re.compile(r'^\s*(async\s+def |def |func |function\b|(export\s+)?(default\s+)?(async\s+)?function\b|'
                        r'(public|private|protected|internal|static|override|suspend)\s[^=;]*\(|fun |fn )')

CASE = re.compile(r'^\s*(case\b.*:|default\s*:)')

PATTERN = {
    'check-then-act': 'R1', 'read-modify-write': 'R2', 'select-then-update': 'R2', 'stale-async-write': 'R4',
    'at-least-once': 'R6', 'lifecycle': 'R9', 'lock-across-wait': 'R10', 'nested-locks': 'R10',
    'shared-mutable': 'R10', 'cache-aside': 'R11', 'spawn': '--',
}

GUARD = re.compile(
    r'(?i)\b(lock|mutex|synchronized|acquire|for\s+update|for\s+share|serializable|repeatable\s+read|transaction|'
    r'atomic(ally)?|@transactional|begin|compareandset|compare_and_swap|cas|version|etag|if-match|'
    r'conditionexpression|conditional|upsert|on\s+conflict|insert\s+ignore|unique|setnx|nx|incr(by)?|'
    r'findoneandupdate|findandmodify|select_for_update|with_lock|optimistic|o_excl|exclusive|singleflight)\b'
    r'|\$inc\b|[\'"]x[\'"]')
YIELD = re.compile(r'\b(await|yield)\b|\.then\(|\b(sleep|Sleep|setTimeout|time\.sleep|Thread\.sleep|delay)\s*\(|'
                   r'<-\s*\w|\b(fetch|axios|requests?|http\w*|urlopen|query|execute|exec|send|recv)\s*\(')
# A ternary `cond ? a : b`, but not optional chaining (`a?.b`), `??` or a TypeScript optional (`x?: T`).
IF = re.compile(r'^\s*(}\s*)?(else\s+)?(if|unless|elif|guard)\b|\s\?\s[^:]+\s:\s|\bif\s*\(')
CHECK = re.compile(r'(?i)\b(exists?|isfile|isdir|access|has|hasKey|contains(Key)?|includes|count|find(One|_by\w*|By\w*|_one|First)?|'
                   r'get|lookup|is_?(used|redeemed|taken|available|valid|active)|select)\b\s*\(?|\bin\s+\w|'
                   r'\bselect\b.+\bfrom\b|\b(balance|stock|quota|limit|remaining|count|used|status|state)\b')
ACT = re.compile(r'(?i)\b\w*?(insert|create|save|put|set|write|mkdir|makedirs|rename|move|update|delete|remove|'
                 r'send|charge|credit|debit|grant|redeem|apply|increment|decrement|withdraw|transfer|reserve|book|'
                 r'claim|consume|commit|persist|store|add|push|append|mark|issue|allocate|assign|register|enrol|'
                 r'vote)\w*\s*\(|\bopen\s*\(.*[\'"][wax]|'
                 r'\b(insert\s+into|update\s+\w+\s+set|delete\s+from)\b')
READ_ASSIGN = re.compile(r'^\s*(?:(?:const|let|var|val|auto|final)\s+)?(?:[\w<>\[\],.?]+\s+)?([A-Za-z_]\w*)\s*'
                         r'(?::=|=(?!=))\s*(?:await\s+|yield\s+)?[\w.$\[\]()]*\b(get\w*|find\w*|load\w*|read\w*|'
                         r'fetch\w*|select\w*|query\w*|lookup\w*|retrieve\w*)\s*\(')
SQL_SELECT = re.compile(r'(?i)\bselect\b.+\bfrom\b')
SQL_FOR_UPDATE = re.compile(r'(?i)\bfor\s+(update|share|no\s+key\s+update)\b')
SQL_WRITE = re.compile(r'(?i)\b(update\s+\w+\s+set|insert\s+into|delete\s+from)\b')
ASYNC_CALL = re.compile(r'\bawait\b.*\b(fetch|axios|http\w*|request\w*|get\w*|post\w*|query\w*|load\w*|call\w*)\b|'
                        r'\.then\s*\(')
STATE_SET = re.compile(r'\bset[A-Z]\w*\s*\(|\bthis\.setState\s*\(|\bthis\.\w+\s*=(?!=)|\bstate\.\w+\s*=(?!=)|'
                       r'\.value\s*=(?!=)|\b(commit|dispatch)\s*\(|\bself\.\w+\s*=(?!=)')
STALE_GUARD = re.compile(r'(?i)\b(abort\w*|signal|cancel\w*|request_?id|latest|is_?mounted|mounted|ignore|'
                         r'current|seq\w*|generation|stale|unsubscribed|disposed|alive)\b')
SPAWN = re.compile(r'\bPromise\.(all|allSettled|race|any)\s*\(|\basyncio\.(gather|create_task|ensure_future)\s*\(|'
                   r'\bcreate_task\s*\(|\bThread\s*\(|\bthreading\.Thread\b|\bExecutor\w*|\.submit\s*\(|'
                   r'^\s*go\s+(func\b|\w+[\w.]*\()|\bnew\s+Worker\s*\(|\bsetInterval\s*\(|\bparallelStream\s*\(|'
                   r'\bCompletableFuture\.\w+Async\s*\(|@Async\b|\b(tokio|thread|std::thread)::spawn\b|'
                   r'\blaunch\s*\{|\basync\s*\{|\bProcess(Pool)?\w*\s*\(|\bmultiprocessing\b')
LOCK_ON = re.compile(r'\.(lock|Lock|acquire|RLock|tryLock|lockInterruptibly)\s*\(|\bsynchronized\s*\(|'
                     r'^\s*(async\s+)?with\s+[\w.]*(lock|mutex|sem\w*)\b|\bLock\(\)\s*$')
LOCK_OFF = re.compile(r'\.(unlock|Unlock|release|RUnlock)\s*\(')
LOCK_NAME = re.compile(r'([\w.]+)\.(?:lock|Lock|acquire|RLock|tryLock|lockInterruptibly)\s*\(|'
                       r'synchronized\s*\(\s*([\w.]+)|with\s+([\w.]+)')
WAIT = re.compile(r'\b(await|sleep|Sleep|time\.sleep|Thread\.sleep|fetch|axios|requests?\.\w+|http\w*|urlopen|'
                  r'query|execute|send|recv|read|write|join|wait|get)\s*\(|\bawait\b|<-\s*\w')
CACHE_GET = re.compile(r'(?i)\b(\w*cache\w*|redis|memcache\w*|kv|store)\.(get|fetch|read|hget|mget)\s*\(|'
                       r'\bget_?from_?cache\s*\(|\bcache\s*\[')
CACHE_SET = re.compile(r'(?i)\b(\w*cache\w*|redis|memcache\w*|kv|store)\.(set|put|setex|add|write|hset|mset)\s*\(|'
                       r'\bcache\s*\[[^\]]+\]\s*=(?!=)')
COALESCE = re.compile(r'(?i)\b(singleflight|lock|mutex|in_?flight|pending|dogpile|stale.while|setnx|nx|'
                      r'coalesc\w*|dedupe?\w*|once)\b')
CONSUMER = re.compile(r'(?i)\b(on_?message|handle_?message|consume\w*|subscriber|listener|@\w*Listener|webhook|'
                      r'retry\w*|max_?retries|backoff|redeliver\w*|ack|nack|receive_?message\w*|process_?event)\b')
IDEMPOTENT = re.compile(r'(?i)(idempoten\w*|dedup\w*|message_?id|event_?id|request_?id|delivery_?id|unique|'
                        r'on\s+conflict|upsert|already_?processed|processed_?ids?|seen_?ids?|setnx)')
PAIRS = [  # (start, stop, what) for per-file teardown checks
    (re.compile(r'\bsetInterval\s*\('), re.compile(r'\bclearInterval\s*\('), 'setInterval with no clearInterval'),
    (re.compile(r'\.addEventListener\s*\('), re.compile(r'\.removeEventListener\s*\('),
     'addEventListener with no removeEventListener'),
    (re.compile(r'\.subscribe\s*\('), re.compile(r'\b(unsubscribe|takeUntil|take|first|dispose)\b'),
     'subscribe with no unsubscribe'),
    (re.compile(r'\.on\s*\(\s*[\'"]'), re.compile(r'\.(off|removeListener|removeAllListeners|once)\s*\('),
     'event handler .on() with no .off()'),
    (re.compile(r'^\s*go\s+(func\b|\w+[\w.]*\()'), re.compile(r'\b(ctx|context|Done\(\)|WaitGroup|errgroup|quit|stop)\b'),
     'goroutine with no context, WaitGroup or stop signal in the file'),
    (re.compile(r'\b(asyncio\.)?create_task\s*\(|\bensure_future\s*\('),
     re.compile(r'\b(cancel|gather|wait|TaskGroup|await\s+\w+_?task)\b'), 'background task never cancelled or awaited'),
]
SHARED = [
    (re.compile(r'^\s+global\s+\w+'), 'py', 'a function writes a module global'),
    (re.compile(r'^\s*(?:(?:public|private|protected|internal)\s+)?static\s+(?!final\b)(?!class\b)(?!readonly\b)'
                r'(?!void\b)[\w<>\[\],.? ]+\s+\w+\s*(=[^=]|;)'), 'java', 'a non-final static field'),
    (re.compile(r'^var\s+\w+\s*(=\s*(map|make\(map|\[\]|&)|\s+(map|\[\]|sync\.Map))'), 'go', 'a package-level mutable var'),
    (re.compile(r'^(let|var)\s+\w+\s*=\s*(\{|\[|new\s+(Map|Set|WeakMap)\b|0\b|null\b)'), 'js',
     'a module-level mutable binding'),
]
LANG = {'.py': 'py', '.java': 'java', '.kt': 'java', '.cs': 'java', '.scala': 'java', '.go': 'go', '.js': 'js',
        '.jsx': 'js', '.mjs': 'js', '.cjs': 'js', '.ts': 'js', '.tsx': 'js'}


def guard_note(lines, a, b):
    """Guard keywords seen in lines[a-3 .. b], as a short note."""
    seen = []
    for ln in lines[max(0, a - 3):b + 1]:
        for m in GUARD.finditer(ln):
            w = m.group(0).strip().lower()
            if w not in seen:
                seen.append(w)
    return f'; guard seen: {", ".join(seen[:3])} (check it covers the window)' if seen else '; no guard seen'


def lock_name(line):
    m = LOCK_NAME.search(line)
    return next((g for g in m.groups() if g), 'lock') if m else 'lock'


def window(lines, i, size):
    """Indexes after line i up to `size` lines, stopping at the next function start or switch case."""
    out = []
    for j in range(i + 1, min(len(lines), i + 1 + size)):
        if FUNC_START.match(lines[j]) or CASE.match(lines[j]):
            break
        out.append(j)
    return out


def code(line):
    return '' if COMMENT.match(line) else line


def scan_text(text, ext, size=30):
    """Return (line, kind, detail) rows for one file's text."""
    raw = text.splitlines()
    lines = [code(x) for x in raw]
    rows, seen = [], set()

    def add(i, kind, detail):
        if (i, kind) not in seen:
            seen.add((i, kind))
            rows.append((i + 1, kind, detail))

    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        win = window(lines, i, size)
        if SPAWN.search(ln):
            add(i, 'spawn', 'starts concurrent work: list it as an actor')
        if IF.search(ln) and CHECK.search(ln):
            for j in win:
                if ACT.search(lines[j]) and not IF.search(lines[j]):
                    gap = 'spans a wait' if any(YIELD.search(lines[k]) for k in range(i, j + 1)) else 'no wait seen'
                    add(i, 'check-then-act', f'check at {i + 1}, act at {j + 1}; {gap}{guard_note(lines, i, j)}')
                    break
        m = READ_ASSIGN.match(ln)
        if m:
            var = re.escape(m.group(1))
            changed = re.compile(r'\b' + var + r'(\.\w+|\[[^\]]*\])*\s*([+\-*/%|&]?=(?!=)|\+\+|--)|\b' + var +
                                 r'\.(push|append|add|remove|pop|insert|update|set\w*)\s*\(')
            written = re.compile(r'(?i)\b(save|update|put|set|write|store|persist|commit|replace|upsert|insert)\w*'
                                 r'\s*\([^)]*\b' + var + r'\b|\b' + var + r'\.(save|update|put|persist|commit)\w*\s*\(')
            mod = None
            for j in win:
                if mod is None and changed.search(lines[j]):
                    mod = j
                if mod is not None and written.search(lines[j]):
                    gap = 'spans a wait' if any(YIELD.search(lines[k]) for k in range(i + 1, j + 1)) else 'no wait seen'
                    add(i, 'read-modify-write', f'read {m.group(1)} at {i + 1}, change at {mod + 1}, write at {j + 1}; '
                                                f'{gap}{guard_note(lines, i, j)}')
                    break
        if SQL_SELECT.search(ln) and not SQL_FOR_UPDATE.search(ln):
            for j in win:
                if SQL_WRITE.search(lines[j]):
                    add(i, 'select-then-update', f'SELECT at {i + 1} with no FOR UPDATE, write at {j + 1}'
                                                 f'{guard_note(lines, i, j)}')
                    break
        if ASYNC_CALL.search(ln):
            for j in [i] + win:
                after = lines[j].split('await', 1)[-1] if j == i else lines[j]
                if j > i and ASYNC_CALL.search(lines[j]) and not STATE_SET.search(lines[j]):
                    continue
                if STATE_SET.search(after) and (j > i or '.then' in ln):
                    span = lines[max(0, i - 5):j + 1]
                    if not any(STALE_GUARD.search(x) for x in span):
                        add(i, 'stale-async-write', f'async result at {i + 1} sets state at {j + 1} with no '
                                                    f'cancel or latest-request check')
                    break
        if LOCK_ON.search(ln):
            held = lock_name(ln)
            for j in win:
                if LOCK_OFF.search(lines[j]):
                    break
                if LOCK_ON.search(lines[j]):
                    other = lock_name(lines[j])
                    if other != held:
                        add(i, 'nested-locks', f'{held} at {i + 1}, then {other} at {j + 1}: check every path '
                                               f'takes them in the same order')
                elif WAIT.search(lines[j]):
                    add(i, 'lock-across-wait', f'{held} at {i + 1} still held at {j + 1}: '
                                               f'{lines[j].strip()[:60]}')
                    break
        if CACHE_GET.search(ln):
            for j in win:
                if CACHE_SET.search(lines[j]):
                    if not any(COALESCE.search(lines[k]) for k in range(max(0, i - 3), j + 1)):
                        add(i, 'cache-aside', f'cache read at {i + 1}, set at {j + 1}: concurrent misses all '
                                              f'recompute (no coalescing seen)')
                    break
    lang = LANG.get(ext)
    for pat, which, what in SHARED:
        if which == lang:
            for i, ln in enumerate(lines):
                if pat.match(ln):
                    add(i, 'shared-mutable', what)
    joined = '\n'.join(lines)
    for start, stop, what in PAIRS:
        if not stop.search(joined):
            for i, ln in enumerate(lines):
                if start.search(ln):
                    add(i, 'lifecycle', what)
                    break
    if not IDEMPOTENT.search(joined):
        for i, ln in enumerate(lines):
            if CONSUMER.search(ln):
                add(i, 'at-least-once', 'retry or message handling with no dedup or idempotency key in the file')
                break
    return sorted(rows)


def files(path, excludes, include_tests):
    if os.path.isfile(path):
        yield path
        return
    for root, dirs, names in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.'))
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, path)
            if os.path.splitext(n)[1] not in EXTS:
                continue
            if any(fnmatch.fnmatch(rel, g) for g in excludes):
                continue
            if not include_tests and TEST_HINT.search(rel):
                continue
            yield p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path')
    ap.add_argument('--window', type=int, default=30, help='Lines to look ahead from a read or check (default 30).')
    ap.add_argument('--kind', default='', help='Only these kinds, comma-separated.')
    ap.add_argument('--json', dest='json_out', help='Also write every row to this JSON file.')
    ap.add_argument('--exclude', action='append', default=[], help='Glob of files to skip (repeatable).')
    ap.add_argument('--include-tests', action='store_true', help='Also scan test files.')
    ap.add_argument('--needs-wait', action='store_true',
                    help='Drop windows with no wait inside (they matter only with threads or other processes).')
    a = ap.parse_args(argv)
    if not os.path.exists(a.path):
        print(f'no such path: {a.path}', file=sys.stderr)
        return 2
    kinds = {k.strip() for k in a.kind.split(',') if k.strip()}
    bad = kinds - set(PATTERN)
    if bad:
        print(f'unknown kind: {", ".join(sorted(bad))}; known: {", ".join(PATTERN)}', file=sys.stderr)
        return 2
    base = a.path if os.path.isdir(a.path) else os.path.dirname(a.path) or '.'
    out, per_file = [], {}
    for p in files(a.path, a.exclude, a.include_tests):
        try:
            with open(p, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except OSError as e:
            print(f'skip {p}: {e}', file=sys.stderr)
            continue
        rel = os.path.relpath(p, base)
        for line, kind, detail in scan_text(text, os.path.splitext(p)[1], a.window):
            if kinds and kind not in kinds:
                continue
            if a.needs_wait and 'no wait seen' in detail:
                continue
            out.append({'location': f'{rel}:{line}', 'kind': kind, 'pattern': PATTERN[kind], 'detail': detail})
            if kind != 'spawn':
                per_file[rel] = per_file.get(rel, 0) + 1
    for r in out:
        print(f"{r['location']}  {r['kind']}  {r['pattern']}  {r['detail']}")
    if per_file:
        print('\ncandidates per file (read the top ones first):')
        for rel, n in sorted(per_file.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f'  {n:>4}  {rel}')
    print(f'\n{len(out)} rows. Each row is a lead (weak evidence), not a finding.')
    if a.json_out:
        with open(a.json_out, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
