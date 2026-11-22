"""Tests for nodes.py. Run: python3 -I -m unittest discover -s <scripts>/tests -t <scripts>/tests"""
import json
import os
import textwrap
import unittest

from helpers import TempTree, has_git, load, run

N = load('nodes')


def py(src):
    fns, warn = N.analyze_py('x.py', textwrap.dedent(src))
    assert warn is None, warn
    return {f['name']: f for f in fns}


def txt(src, lang):
    fns, _ = N.analyze_text('x', textwrap.dedent(src), lang)
    return {f['name']: f for f in fns}


def kinds(fn, family=None):
    return [n['kind'] for n in fn['nodes'] if family is None or n['family'] == family]


# ── Python ──────────────────────────────────────────────────────────────────

class PythonDecisions(unittest.TestCase):
    def test_vg_counts_every_decision_kind(self):
        f = py('''
            def f(a, b, xs):
                if a and b or a:
                    pass
                elif b:
                    pass
                y = 1 if a else 2
                for x in xs:
                    while x:
                        x -= 1
                try:
                    pass
                except ValueError:
                    raise
                assert a
                return [x for x in xs if x]
        ''')['f']
        # if, elif, and, or, ternary, for, while, except, assert, comprehension for + if
        self.assertEqual(f['decisions'], 11)
        self.assertEqual(f['vg'], 12)
        self.assertTrue(f['exact'])

    def test_worked_example_gap_and_data_flow(self):
        f = py('''
            def band_score(size, boost):
                if size <= 0:
                    raise ValueError("bad size")
                if size < 5:
                    score = 5
                elif size > 5:
                    score = 5 + (size - 5) * 2
                if boost:
                    score *= 2
                return score
        ''')['band_score']
        self.assertEqual(f['vg'], 5)
        self.assertIn('if-chain-no-else', kinds(f))
        flow = [n for n in f['nodes'] if n['kind'] == 'maybe-unassigned']
        self.assertEqual([n['line'] for n in flow], [5])
        self.assertIn('score', flow[0]['detail'])

    def test_assigned_on_every_path_is_not_flagged(self):
        f = py('''
            def f(a):
                if a:
                    v = 1
                elif not a:
                    return 0
                else:
                    v = 2
                for i in range(2):
                    if i:
                        w = 1
                    print(w)
                try:
                    pass
                except OSError:
                    if a:
                        z = 1
                    print(z)
                return v
        ''')['f']
        flagged = [n['detail'].split()[0] for n in f['nodes'] if n['kind'] == 'maybe-unassigned']
        self.assertEqual(sorted(flagged), ['w', 'z'])

    @unittest.skipUnless(N.MATCH is not None, 'match statements need Python 3.10+')
    def test_match_without_wildcard(self):
        f = py('''
            def f(x):
                match x:
                    case 1:
                        return 1
                    case 2:
                        return 2
            def g(x):
                match x:
                    case 1:
                        return 1
                    case _:
                        return 0
        ''')
        self.assertIn('switch-no-default', kinds(f['f']))
        self.assertNotIn('switch-no-default', kinds(g := f['g']))
        self.assertEqual(g['vg'], 3)

    def test_nested_functions_and_methods_are_separate(self):
        fns = py('''
            class C:
                def m(self, n):
                    if n:
                        return self.m(n - 1)
                    def inner():
                        if n:
                            pass
                    return inner
        ''')
        self.assertEqual(set(fns), {'C.m', 'C.m.inner'})
        self.assertEqual(fns['C.m']['vg'], 2)
        self.assertIn('recursion', kinds(fns['C.m']))


class PythonOtherNodes(unittest.TestCase):
    def test_hidden_branches(self):
        f = py('''
            import json
            def f(a, b, d: dict[str, int], it):
                x = a / b
                y = a % b
                s = "%s" % a
                z = d["k"]
                t = a[1:]
                n = int(a)
                j = json.loads(b)
                first = next(it)
                while True:
                    pass
                return x
        ''')['f']
        k = kinds(f, 'hidden')
        for want in ('division', 'modulo', 'index-or-key', 'parse', 'next-no-default', 'loop-no-exit'):
            self.assertIn(want, k)
        self.assertEqual(k.count('modulo'), 1)        # "%s" % a is formatting
        self.assertEqual(k.count('index-or-key'), 1)  # annotation and slice are skipped

    def test_while_true_with_break_is_not_endless(self):
        f = py('''
            def f():
                while True:
                    break
        ''')['f']
        self.assertNotIn('loop-no-exit', kinds(f))

    def test_sources_and_sinks(self):
        f = py('''
            import os, pickle, re, subprocess, requests, yaml
            def f(request, cur, name):
                q = request.args.get("q")
                e = os.environ["HOME"]
                v = input()
                cur.execute(f"SELECT {q}")
                cur.execute("SELECT 1")
                cur.execute("SELECT %s" % q)
                subprocess.run(q, shell=True)
                subprocess.run(["ls"])
                os.system(q)
                eval(q)
                pickle.loads(q)
                yaml.load(q)
                yaml.load(q, Loader=yaml.SafeLoader)
                re.compile(q)
                re.compile("x")
                open(name)
                with open(name) as fh:
                    pass
                requests.get(q)
                requests.get("http://x", timeout=3)
                render_template_string(q)
        ''')['f']
        sinks = [n['kind'] for n in f['nodes'] if n['kind'].startswith('sink:')]
        self.assertEqual(sinks.count('sink:sql'), 2)
        self.assertEqual(sinks.count('sink:shell'), 2)
        self.assertEqual(sinks.count('sink:deserialize'), 2)
        for want in ('sink:code', 'sink:regex', 'sink:file', 'sink:outbound-request', 'sink:html'):
            self.assertIn(want, sinks)
        self.assertEqual({n['detail'] for n in f['nodes'] if n['kind'] == 'source'},
                         {'request.args', 'os.environ', 'input'})
        self.assertEqual(kinds(f).count('network-no-timeout'), 1)
        self.assertEqual(kinds(f).count('network-call'), 1)
        self.assertEqual(kinds(f).count('acquire-no-release'), 1)

    def test_error_paths_with_other_defaults(self):
        f = py('''
            def f(make):
                try:
                    make().conn.execute("x" + make)
                except ValueError:
                    return
                try:
                    pass
                except KeyError:
                    return {}
                try:
                    pass
                except OSError:
                    return -1
        ''')['f']
        self.assertEqual(kinds(f, 'error-path').count('catch-returns-default'), 3)
        self.assertEqual([n['detail'] for n in f['nodes'] if n['kind'] == 'sink:sql'],
                         ['make().conn.execute with a built string'])

    def test_error_paths(self):
        f = py('''
            import logging
            def f():
                try:
                    pass
                except:
                    pass
                try:
                    pass
                except ValueError:
                    logging.warning("x")
                    return None
                try:
                    pass
                except KeyError:
                    return []
                try:
                    pass
                except OSError as e:
                    raise RuntimeError() from e
        ''')['f']
        k = kinds(f, 'error-path')
        self.assertEqual(k.count('bare-catch'), 1)
        self.assertEqual(k.count('catch-swallows'), 1)
        self.assertEqual(k.count('catch-returns-default'), 2)

    def test_locks_and_mutable_defaults(self):
        fns = py('''
            def f(lock, a=[], *, b={}, c=list(), d=None):
                lock.acquire()
            def g(lock):
                lock.acquire()
                lock.release()
        ''')
        self.assertEqual(kinds(fns['f']).count('mutable-default'), 3)
        self.assertIn('acquire-no-release', kinds(fns['f']))
        self.assertNotIn('acquire-no-release', kinds(fns['g']))

    def test_syntax_error_is_a_warning(self):
        fns, warn = N.analyze_py('bad.py', 'def f(:\n')
        self.assertEqual(fns, [])
        self.assertIn('cannot parse', warn)


# ── Pattern-based languages ─────────────────────────────────────────────────

class Strip(unittest.TestCase):
    def test_comments_strings_and_regex_are_blanked(self):
        src = "a // if (x) {\n/* if */ b = 'if (y) {'; c = /[\"']/g; d = `t ${e + 'q'} u`;\n"
        out, interps = N.strip(src, 'js')
        self.assertEqual(len(out), len(src))
        self.assertNotIn('if', out)
        self.assertIn('${e +', out)
        self.assertEqual(len(interps), 1)

    def test_language_string_forms(self):
        out, _ = N.strip('s := `raw \\ if` + "x\\"if"\n', 'go')
        self.assertNotIn('if', out)
        out, interps = N.strip('val s = """if ${a}""" + "b ${c} if"\n', 'kotlin')
        self.assertNotIn('if', out)
        self.assertEqual(len(interps), 2)
        out, _ = N.strip('String s = """\nif\n""";\nchar c = \'{\';\n', 'java')
        self.assertNotIn('if', out)
        self.assertEqual(out.count('\n'), 4)

    def test_nested_braces_in_template_and_regex_edges(self):
        out, interps = N.strip('a = `x ${ {k: 1}.k } if`; b = /a\\/if/; c = /if', 'js')
        self.assertIn('{k: 1}.k', out)
        self.assertEqual(out.count('if'), 1)  # only the unterminated "/if" at the end stays as code
        self.assertEqual(len(interps), 1)

    def test_unterminated_string_and_division_are_safe(self):
        out, _ = N.strip("a = 'open\nb = x / y / z;\nc = / unterminated\n", 'js')
        self.assertIn('x / y / z', out)
        self.assertIn('b =', out)


class JavaScript(unittest.TestCase):
    SRC = '''
        function sumValues(items) {
          return items.reduce((sum, i) => sum + i.amount, 0);
        }
        const label = (record) => {
          return `Item ${record.name}`;
        };
        class S {
          async load(id) {
            const r = await fetch(id);
            return r;
          }
        }
        const one = x => {
          return x;
        };
        app.get('/find', async (req, res) => {
          const q = req.query.q;
          if (q == null) {
            return res.send('none');
          } else if (q.length > 10) {
            return res.send('long');
          }
          try {
            const rows = await db.query(`SELECT * FROM t WHERE name = '${q}'`);
            await db.query('SELECT 1');
            res.send(rows.find((r) => r.ok));
          } catch (e) {
            console.log(e);
          }
          switch (q[0]) {
            case 'a':
              break;
          }
          const n = parseInt(q) / rows.length;
          const m = parseInt(q, 10) % 2;
          const v = q?.trim() ?? '';
          const t = q ? 1 : 2;
          el.innerHTML = q;
          exec(q);
          eval(q);
          fs.readFile(q);
          fs.readFile('fixed.txt');
          Object.assign({}, req.body);
          new RegExp(q);
          unserialize(q);
          p.catch(() => {});
          while (true) {
            n++;
          }
          setInterval(tick, 10);
        });
    '''

    def test_functions_are_found_and_named(self):
        fns = txt(self.SRC, 'js')
        self.assertEqual(set(fns), {'sumValues', 'label', 'load', 'one', '<callback in app.get>', '<callback in p.catch>'})
        self.assertFalse(fns['label']['exact'])

    def test_nodes_in_handler(self):
        f = txt(self.SRC, 'js')['<callback in app.get>']
        k = kinds(f)
        for want in ('source', 'sink:sql', 'sink:html', 'sink:shell', 'sink:code', 'sink:file', 'sink:object-merge',
                     'sink:regex', 'sink:deserialize', 'if-chain-no-else', 'switch-no-default', 'catch-swallows',
                     'loose-equality', 'parseInt-no-radix', 'optional-chaining', 'template-interpolation',
                     'may-return-undefined', 'division', 'modulo', 'index-or-key', 'parse', 'loop-no-exit',
                     'acquire-no-release', 'nullish', 'ternary'):
            self.assertIn(want, k, want)
        self.assertEqual(k.count('sink:sql'), 1)        # the constant query is not flagged
        self.assertEqual(k.count('sink:file'), 1)       # the literal path is not flagged
        self.assertEqual(k.count('parseInt-no-radix'), 1)
        self.assertEqual(k.count('catch-swallows'), 2)  # catch block + ignored promise rejection
        # if, else if, catch, case, ternary, nullish, while
        self.assertEqual(f['decisions'], 7)

    def test_network_timeout_and_recursion(self):
        fns = txt('''
            async function get(u) {
              return fetch(u, { signal: s });
            }
            function walk(n) {
              if (n) { return walk(n - 1); }
            }
        ''', 'js')
        self.assertIn('network-call', kinds(fns['get']))
        self.assertIn('sink:outbound-request', kinds(fns['get']))
        self.assertIn('recursion', kinds(fns['walk']))
        load = txt(self.SRC, 'js')['load']
        self.assertIn('network-no-timeout', kinds(load))

    def test_complete_and_single_statement_if_chains(self):
        fns = txt('''
            function full(a) {
              if (a > 0) { return 1; } else if (a < 0) { return -1; } else { return 0; }
            }
            function short(a) {
              if (a) x(); else if (b) y();
            }
        ''', 'js')
        self.assertNotIn('if-chain-no-else', kinds(fns['full']))
        self.assertNotIn('if-chain-no-else', kinds(fns['short']))

    def test_catch_that_rethrows_or_returns_default(self):
        fns = txt('''
            function a() {
              try { x(); } catch (e) { throw e; }
            }
            function b() {
              try { x(); } catch (e) { logger.warn(e); return null; }
            }
        ''', 'js')
        self.assertEqual(kinds(fns['a'], 'error-path'), [])
        self.assertEqual(kinds(fns['b'], 'error-path'), ['catch-returns-default'])


class Java(unittest.TestCase):
    def test_methods_lambdas_and_nodes(self):
        fns = txt('''
            public class C {
              @GetMapping
              public List<String> find(@RequestParam String q, Map<String, ? extends Number> m) throws IOException {
                if (q == null) {
                  return null;
                } else if (q.isEmpty()) {
                  return List.of();
                }
                Statement st = conn.createStatement();
                st.executeQuery("SELECT * FROM t WHERE n = '" + q + "'");
                st.executeQuery("SELECT 1");
                FileInputStream in = new FileInputStream(q);
                Runtime.getRuntime().exec(q);
                int n = Integer.parseInt(q) / m.size();
                String s = q.length() > 3 ? "a" : "b";
                switch (n) {
                  case 1 -> { s = "x"; }
                  case LIMIT -> { s = "z"; }
                  default -> { s = "y"; }
                }
                try { run(); } catch (Exception e) { e.printStackTrace(); }
                list.forEach(x -> {
                  if (x) { y(); }
                });
                return List.of(s);
              }
            }
        ''', 'java')
        self.assertEqual(set(fns), {'find', '<callback in list.forEach>'})
        k = kinds(fns['find'])
        for want in ('source', 'sink:sql', 'sink:file', 'sink:shell', 'parse', 'division', 'if-chain-no-else',
                     'catch-swallows', 'acquire-no-release', 'ternary'):
            self.assertIn(want, k, want)
        self.assertNotIn('switch-no-default', k)
        self.assertEqual(k.count('sink:sql'), 1)
        self.assertEqual(kinds(fns['<callback in list.forEach>']), ['if'])


class Kotlin(unittest.TestCase):
    def test_kotlin_nodes(self):
        fns = txt('''
            fun handle(call: Call, x: Int?): Int {
                val p = call.parameters["p"]
                val n = p!!.toInt()
                val s = "v=${p}"
                val r = when (n) {
                    1 -> 10
                    2 -> 20
                    else -> 0
                }
                val w = when (n) {
                    1 -> 1
                }
                return x ?: r
            }
        ''', 'kotlin')
        k = kinds(fns['handle'])
        for want in ('source', 'not-null-assertion', 'parse', 'elvis', 'when-branch', 'switch-no-default'):
            self.assertIn(want, k, want)
        self.assertEqual(k.count('when-branch'), 3)  # "else ->" is the default, not a decision
        self.assertEqual(k.count('switch-no-default'), 1)


class Go(unittest.TestCase):
    def test_go_nodes(self):
        fns = txt('''
            func (s *Server) Handle(w http.ResponseWriter, r *http.Request) (int, error) {
                q := r.FormValue("q")
                f, err := os.Open(q)
                if err != nil {
                }
                v := x.(string)
                u, ok := x.(int)
                switch q {
                case "a":
                    return 1, nil
                }
                m := map[string]int{}
                n, _ := strconv.Atoi(q)
                rows, _ := db.Query(fmt.Sprintf("SELECT %s", q))
                exec.Command(q)
                for {
                    n++
                }
                return m[q] / n, nil
            }
            func main() {
                http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
                    mu.Lock()
                    defer mu.Unlock()
                })
            }
        ''', 'go')
        self.assertEqual(set(fns), {'Handle', 'main', '<callback in http.HandleFunc>'})
        k = kinds(fns['Handle'])
        for want in ('source', 'sink:file', 'sink:sql', 'sink:shell', 'catch-swallows', 'type-assertion',
                     'switch-no-default', 'error-ignored', 'parse', 'loop-no-exit', 'acquire-no-release',
                     'division', 'index-or-key'):
            self.assertIn(want, k, want)
        self.assertEqual(k.count('type-assertion'), 1)  # the ", ok" form is safe
        self.assertEqual(k.count('index-or-key'), 1)    # map[string]int is a type
        self.assertNotIn('acquire-no-release', kinds(fns['<callback in http.HandleFunc>']))


# ── CLI ─────────────────────────────────────────────────────────────────────

class Cli(TempTree):
    FILES = {
        'src/a.py': 'import os\n\ndef risky(q):\n    if q:\n        os.system(q)\n\n\ndef plain():\n    return 1\n',
        'src/b.js': 'function f(a) {\n  if (a) { return 1; }\n}\n',
        'src/c.txt': 'not code\n',
        'tests/test_a.py': 'def test_x():\n    if 1:\n        pass\n',
        'gen/skip.py': 'def g():\n    pass\n',
    }

    def test_nodes_text_and_json(self):
        root = self.write(self.FILES)
        out_json = self.path('out.json')
        code, out, err = run('nodes', 'nodes', root, '--exclude', 'gen/*', '--json', out_json)
        self.assertEqual(code, 0, err)
        self.assertIn('src/a.py:3  risky  v(G)=2', out)
        self.assertIn('approx', out)
        self.assertNotIn('test_x', out)
        self.assertNotIn('skip.py', out)
        with open(out_json, encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertEqual({f['name'] for f in data}, {'risky', 'plain', 'f'})

    def test_nodes_filters(self):
        root = self.write(self.FILES)
        code, out, _ = run('nodes', 'nodes', root, '--function', 'risky', '--family', 'boundary', '--include-tests')
        self.assertEqual(code, 0)
        self.assertIn('sink:shell', out)
        self.assertNotIn('decision    if', out)
        self.assertIn('1 functions', out)
        code, _, err = run('nodes', 'nodes', root, '--family', 'nope')
        self.assertEqual(code, 2)
        self.assertIn('unknown family', err)

    def test_single_file_and_warnings(self):
        root = self.write({'bad.py': 'def f(:\n', 'ok.py': 'def g():\n    pass\n'})
        code, out, err = run('nodes', 'nodes', os.path.join(root, 'ok.py'))
        self.assertEqual(code, 0)
        self.assertIn('ok.py:1  g', out)
        code, out, err = run('nodes', 'nodes', root)
        self.assertIn('cannot parse', err)
        code, _, err = run('nodes', 'nodes', os.path.join(root, 'missing'))
        self.assertEqual(code, 2)

    def test_unsupported_and_unreadable_files(self):
        root = self.write({'x.txt': 'hi\n'})
        self.assertIn('unsupported', N.analyze_file(os.path.join(root, 'x.txt'))[1])
        self.assertIn('cannot read', N.analyze_file(os.path.join(root, 'nope.py'))[1])

    def test_rank_without_history(self):
        root = self.write(self.FILES)
        out_json = self.path('rank.json')
        code, out, err = run('nodes', 'rank', root, '--no-history', '--top', '1', '--json', out_json)
        self.assertEqual(code, 0, err)
        self.assertIn('risky', out)
        self.assertNotIn('plain', out)
        self.assertIn('no git history used', out)
        self.write({'src/bad.py': 'def f(:\n'})
        code, _, err = run('nodes', 'rank', root, '--no-history')
        self.assertIn('cannot parse', err)
        with open(out_json, encoding='utf-8') as fh:
            rows = json.load(fh)
        self.assertEqual(rows[0]['function'], 'risky')
        self.assertEqual(rows[0]['score'], 1 + 3)  # v(G) - 1, plus one sink

    @unittest.skipUnless(has_git(), 'git not installed')
    def test_rank_with_history(self):
        root = self.write(self.FILES)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'add files')
        with open(self.path('src/b.js'), 'a', encoding='utf-8') as fh:
            fh.write('// change\n')
        self.git('commit', '-q', '-am', 'fix bug in b')
        code, out, err = run('nodes', 'rank', root, '--json', self.path('r.json'))
        self.assertEqual(code, 0, err)
        with open(self.path('r.json'), encoding='utf-8') as fh:
            rows = {r['function']: r for r in json.load(fh)}
        self.assertEqual(rows['f']['commits'], 2)
        self.assertEqual(rows['f']['fix_commits'], 1)
        self.assertEqual(rows['f']['score'], 1 + 0.5 * 2 + 1)

    def test_history_outside_git(self):
        root = self.write({'a.py': 'def f():\n    pass\n'})
        self.assertIsNone(N.git_history(os.path.join(root, 'a.py'), 10))


if __name__ == '__main__':
    unittest.main()
