"""Tests for race_scan.py. Run: python3 -I -m unittest discover -s <scripts>/tests -t <scripts>/tests"""
import json
import unittest

from helpers import TempTree, load, run

S = load('race_scan')

PY = '''import threading
counter = 0


def redeem(db, user, code):
    if db.is_redeemed(code):
        return False
    db.credit(user, 10)
    db.mark_redeemed(code)


def bump():
    global counter
    counter += 1


def withdraw(repo, uid, amt):
    acct = repo.get_account(uid)
    acct.balance -= amt
    repo.save(acct)


def report(cur):
    cur.execute("SELECT qty FROM stock WHERE id = 1")
    cur.execute("UPDATE stock SET qty = qty - 1 WHERE id = 1")


def handler(lock, other):
    lock.acquire()
    other.acquire()
    requests.get("http://x")
    lock.release()


def on_message(msg):
    process(msg.body)
'''

TS = '''let cache = {};
export async function search(q) {
  const res = await fetch('/api?q=' + q);
  setResults(await res.json());
}
export function start() {
  setInterval(() => poll(), 1000);
  window.addEventListener('resize', onResize);
  bus.on('tick', onTick);
  store.subscribe(render);
}
export async function getUser(id) {
  const hit = cache.get(id);
  if (hit) return hit;
  const u = await load(id);
  cache.set(id, u);
  return u;
}
async function both() { await Promise.all([a(), b()]); }
'''


def kinds(text, ext):
    return [(line, kind) for line, kind, _ in S.scan_text(text, ext)]


def details(text, ext, kind):
    return [d for _, k, d in S.scan_text(text, ext) if k == kind]


class Python(unittest.TestCase):
    def test_finds_each_kind(self):
        got = kinds(PY, '.py')
        for want in [(6, 'check-then-act'), (13, 'shared-mutable'), (18, 'read-modify-write'),
                     (24, 'select-then-update'), (29, 'lock-across-wait'), (29, 'nested-locks'),
                     (35, 'at-least-once')]:
            self.assertIn(want, got)

    def test_details(self):
        self.assertIn('read acct at 18, change at 19, write at 20; no wait seen; no guard seen',
                      details(PY, '.py', 'read-modify-write')[0])
        self.assertIn('lock at 29, then other at 30', details(PY, '.py', 'nested-locks')[0])

    def test_guards_are_noted_not_trusted(self):
        src = ('def withdraw(repo, uid, amt):\n'
               '    with transaction():\n'
               '        acct = repo.get_account(uid)\n'
               '        acct.balance -= amt\n'
               '        await repo.save(acct)\n')
        d = details(src, '.py', 'read-modify-write')[0]
        self.assertIn('guard seen: transaction', d)
        self.assertIn('spans a wait', d)

    def test_for_update_is_not_flagged(self):
        src = 'def f(c):\n    c.execute("SELECT q FROM t FOR UPDATE")\n    c.execute("UPDATE t SET q = 1")\n'
        self.assertNotIn('select-then-update', [k for _, k in kinds(src, '.py')])

    def test_idempotency_key_silences_consumer(self):
        src = 'def on_message(msg):\n    if seen(msg.message_id):\n        return\n'
        self.assertNotIn('at-least-once', [k for _, k in kinds(src, '.py')])

    def test_comments_ignored_and_window_stops_at_function(self):
        src = '# if db.exists(x): db.create(x)\ndef a():\n    if db.exists(x):\n        pass\ndef b():\n    db.create(x)\n'
        self.assertEqual(kinds(src, '.py'), [])

    def test_task_without_cancel(self):
        self.assertIn((2, 'lifecycle'), kinds('async def f():\n    asyncio.create_task(job())\n', '.py'))


class JavaScript(unittest.TestCase):
    def test_finds_each_kind(self):
        got = kinds(TS, '.ts')
        for want in [(1, 'shared-mutable'), (3, 'stale-async-write'), (7, 'lifecycle'), (7, 'spawn'),
                     (8, 'lifecycle'), (9, 'lifecycle'), (10, 'lifecycle'), (13, 'cache-aside'), (19, 'spawn')]:
            self.assertIn(want, got)

    def test_cancel_check_silences_stale_write(self):
        src = ('async function s(q, signal) {\n  const r = await fetch(q, { signal });\n'
               '  setResults(await r.json());\n}\n')
        self.assertNotIn('stale-async-write', [k for _, k in kinds(src, '.js')])

    def test_then_on_same_line(self):
        src = 'function s(q) {\n  api.get(q).then(r => setResults(r));\n}\n'
        self.assertIn((2, 'stale-async-write'), kinds(src, '.js'))

    def test_intervening_async_call_is_skipped(self):
        src = 'async function s() {\n  const a = await fetch(x);\n  const b = await fetch(y);\n  setData(b);\n}\n'
        self.assertIn((2, 'stale-async-write'), kinds(src, '.js'))

    def test_optional_chaining_is_not_a_ternary(self):
        src = "function f() {\n  log?.warn('state', { code: 1 });\n  store.save(x);\n}\n"
        self.assertNotIn('check-then-act', [k for _, k in kinds(src, '.ts')])
        src = 'function f() {\n  const v = exists(k) ? a : b;\n  store.save(v);\n}\n'
        self.assertIn((2, 'check-then-act'), kinds(src, '.ts'))

    def test_coalescing_silences_cache_aside(self):
        src = 'async function g(k) {\n  const v = cache.get(k);\n  const p = inflight.get(k);\n  cache.set(k, v);\n}\n'
        self.assertNotIn('cache-aside', [k for _, k in kinds(src, '.js')])

    def test_teardown_present(self):
        src = 'setInterval(f, 1);\nclearInterval(t);\n'
        self.assertNotIn('lifecycle', [k for _, k in kinds(src, '.js')])


class OtherLanguages(unittest.TestCase):
    def test_java_static_and_synchronized(self):
        src = ('class A {\n  static int hits = 0;\n  static final int MAX = 3;\n'
               '  void f() {\n    synchronized (a) {\n      synchronized (b) {\n      }\n    }\n  }\n}\n')
        got = kinds(src, '.java')
        self.assertIn((2, 'shared-mutable'), got)
        self.assertNotIn((3, 'shared-mutable'), got)
        self.assertIn((5, 'nested-locks'), got)

    def test_go_package_map_and_goroutine(self):
        src = 'package x\nvar seen = map[string]bool{}\nfunc f() {\n\tgo work()\n}\n'
        got = kinds(src, '.go')
        self.assertIn((2, 'shared-mutable'), got)
        self.assertIn((4, 'lifecycle'), got)
        self.assertIn((4, 'spawn'), got)

    def test_with_lock_then_wait(self):
        src = 'def f():\n    with self.lock:\n        time.sleep(1)\n'
        self.assertIn('self.lock at 2 still held at 3', details(src, '.py', 'lock-across-wait')[0])


class Cli(TempTree):
    def test_folder_scan_json_and_ranking(self):
        root = self.write({'shop.py': PY, 'web/ui.ts': TS, 'tests/test_x.py': PY,
                           'node_modules/m.js': TS, 'README.md': 'if exists then create'})
        out_json = self.path('out.json')
        code, out, _ = run('race_scan', root, '--json', out_json)
        self.assertEqual(code, 0)
        self.assertIn('shop.py:6  check-then-act  R1', out)
        self.assertIn('candidates per file', out)
        self.assertNotIn('test_x.py', out)
        self.assertNotIn('node_modules', out)
        with open(out_json, encoding='utf-8') as fh:
            rows = json.load(fh)
        self.assertTrue(any(r['location'] == 'web/ui.ts:3' and r['pattern'] == 'R4' for r in rows))

    def test_filters(self):
        root = self.write({'shop.py': PY, 'tests/test_x.py': PY, 'gen/g.py': PY})
        code, out, _ = run('race_scan', root, '--kind', 'nested-locks', '--include-tests', '--exclude', 'gen/*')
        self.assertEqual(code, 0)
        self.assertIn('tests/test_x.py:29  nested-locks', out)
        self.assertNotIn('gen/', out)
        self.assertNotIn('check-then-act', out)

    def test_single_file_and_errors(self):
        self.write({'shop.py': PY})
        code, out, _ = run('race_scan', self.path('shop.py'))
        self.assertEqual(code, 0)
        self.assertIn('shop.py:18  read-modify-write', out)
        self.assertEqual(run('race_scan', self.path('nope'))[0], 2)
        code, _, err = run('race_scan', self.root, '--kind', 'bogus')
        self.assertEqual(code, 2)
        self.assertIn('unknown kind', err)

    def test_needs_wait(self):
        root = self.write({'shop.py': PY})
        out = run('race_scan', root, '--needs-wait')[1]
        self.assertNotIn('shop.py:6  check-then-act', out)
        self.assertIn('shop.py:29  lock-across-wait', out)

    def test_window_stops_at_switch_case(self):
        src = 'switch (k) {\n  case 1:\n    if (a.has(x)) log(1);\n    break;\n  case 2:\n    store.save(y);\n}\n'
        self.assertNotIn('check-then-act', [k for _, k in kinds(src, '.js')])

    def test_empty_folder(self):
        code, out, _ = run('race_scan', self.write({'a.txt': 'x'}))
        self.assertEqual(code, 0)
        self.assertIn('0 rows', out)


if __name__ == '__main__':
    unittest.main()
