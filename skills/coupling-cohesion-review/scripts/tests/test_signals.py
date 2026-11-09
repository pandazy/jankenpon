"""Tests for signals.py. Run: python3 -I -m unittest discover -s <scripts>/tests -t <scripts>/tests"""
import os
import unittest

from helpers import TempTree, has_git, load, run

S = load('signals')


def files_of(rows, key='file'):
    return {r[key] for r in rows}


def cycle_sets(cycles):
    return [set(c) for c in cycles]


# ── pure functions ──────────────────────────────────────────────────────────

class StripComments(unittest.TestCase):
    def test_c_like_comments_removed_strings_kept(self):
        src = "a // gone\n/* gone\n gone */ b\nc = 'http://x/*y*/'\nd = `t // kept`\n"
        out = S.strip_comments(src, 'js')
        self.assertNotIn('gone', out)
        self.assertIn("'http://x/*y*/'", out)
        self.assertIn('`t // kept`', out)

    def test_line_numbers_preserved(self):
        src = "/* a\nb\nc */\nimport x from './x'\n"
        out = S.strip_comments(src, 'js')
        self.assertEqual(out.count('\n'), src.count('\n'))
        self.assertEqual(out.split('\n')[3], "import x from './x'")

    def test_glob_in_string_is_not_a_comment(self):
        # Regression: "src/**/x" in a config string once opened a fake block comment.
        src = '{"paths": {"@/*": ["./src/*"]}, "exclude": ["src/**/__tests__/**"]}'
        self.assertEqual(S.strip_comments(src, 'js'), src)

    def test_escaped_quote_and_unterminated_string(self):
        src = "a = 'it\\'s // kept'\nb = 'open\nimport x from './x' // gone\n"
        out = S.strip_comments(src, 'js')
        self.assertIn("'it\\'s // kept'", out)
        self.assertIn("import x from './x'", out)  # an unterminated string ends at the line end
        self.assertNotIn('gone', out)

    def test_python_comments_and_docstrings(self):
        src = '"""doc import os"""\nx = "# kept"  # gone\n'
        out = S.strip_comments(src, 'py')
        self.assertNotIn('import os', out)
        self.assertNotIn('gone', out)
        self.assertIn('"# kept"', out)
        self.assertEqual(out.count('\n'), src.count('\n'))


class JsImports(unittest.TestCase):
    def parse(self, code):
        return dict(S.js_imports(code))

    def test_forms(self):
        got = self.parse(
            "import a from './a'\nimport './side'\nexport { b } from './b'\n"
            "const c = await import('./c')\nconst d = require('./d')\n"
            "new Worker(new URL('./w.ts', import.meta.url))\n")
        self.assertEqual(set(got), {'./a', './side', './b', './c', './d', './w.ts'})
        self.assertFalse(any(got.values()))

    def test_type_only(self):
        got = self.parse(
            "import type { A } from './t1'\nimport { type B, type C } from './t2'\n"
            "import { type D, E } from './mixed'\nexport type { F } from './t3'\n")
        self.assertTrue(got['./t1'])
        self.assertTrue(got['./t2'])
        self.assertFalse(got['./mixed'])
        self.assertTrue(got['./t3'])


class ResolveJs(unittest.TestCase):
    def test_alias_forms_and_misses(self):
        fileset = {'/r/src/a.ts', '/r/lib/index.js'}
        aliases = [('@/*', '/r/src/*'), ('lib', '/r/lib')]
        self.assertEqual(S.resolve_js('/r/x.ts', '@/a', fileset, aliases), '/r/src/a.ts')
        self.assertEqual(S.resolve_js('/r/x.ts', '@/a.js', fileset, aliases), '/r/src/a.ts')  # ESM-style extension
        self.assertEqual(S.resolve_js('/r/x.ts', 'lib', fileset, aliases), '/r/lib/index.js')  # exact alias, index file
        self.assertIsNone(S.resolve_js('/r/x.ts', './missing', fileset, aliases))
        self.assertIsNone(S.resolve_js('/r/x.ts', 'react', fileset, aliases))


class LoadAliases(TempTree):
    def test_invalid_config_is_skipped(self):
        self.write({'bad/tsconfig.json': '{ not json',
                    'jsconfig.json': '{"compilerOptions": {"paths": {"~/*": ["src/*"]}}}'})
        self.assertEqual(S.load_js_aliases(self.root), [('~/*', f'{self.root}/src/*')])


class Read(TempTree):
    def test_unreadable_path_gives_empty_text(self):
        self.assertEqual(S.read(self.root), '')  # a directory raises OSError


class PyImports(unittest.TestCase):
    def test_forms(self):
        got = S.py_imports("import os, sys\nfrom .a import (b,\n  c)\nfrom ..pkg import d as e\nfrom x.y import *\n")
        self.assertIn((0, 'os', None), got)
        self.assertIn((0, 'sys', None), got)
        self.assertIn((1, 'a', ['b', 'c']), got)
        self.assertIn((2, 'pkg', ['d']), got)
        self.assertIn((0, 'x.y', ['*']), got)

    def test_does_not_swallow_next_line(self):
        # Regression: an import list once ran on into the following lines.
        got = S.py_imports("import re\nfrom email import utils\n")
        self.assertEqual(got, [(0, 're', None), (0, 'email', ['utils'])])


class Sccs(unittest.TestCase):
    def test_finds_only_real_cycles(self):
        g = {'a': {'b'}, 'b': {'c'}, 'c': {'a'}, 'd': {'e'}, 'e': set(), 'x': {'y'}, 'y': {'x'}}
        self.assertEqual(cycle_sets(S.sccs(g, sorted(set(g) | {'e'}))), [{'a', 'b', 'c'}, {'x', 'y'}])

    def test_deep_chain_does_not_recurse(self):
        n = 5000
        g = {i: {i + 1} for i in range(n)}
        g[n] = {0}
        self.assertEqual(len(S.sccs(g, list(range(n + 1)))[0]), n + 1)


class GrabBag(unittest.TestCase):
    def test_names(self):
        for yes in ['utils', 'wizardUtils', 'string_helpers', 'date-helper', 'misc', 'base', 'commonUtilities']:
            self.assertTrue(S.GRAB_BAG.search(yes), yes)
        for no in ['baseline', 'utilsx', 'database', 'userService', 'toolbar']:
            self.assertFalse(S.GRAB_BAG.search(no), no)


# ── end to end, per language ────────────────────────────────────────────────

class JavaScriptProject(TempTree):
    def setUp(self):
        super().setUp()
        self.write({
            'tsconfig.json': '{\n  // comment\n  "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}},\n'
                             '  "exclude": ["src/**/__tests__/**"],\n}\n',
            'src/main.ts': "import { page } from '@/ui/page'\nimport '@/core/store'\n"
                           "import React from 'react'\nimport { x } from '@scope/pkg/sub'\n",
            'src/ui/page.tsx': "import { helper } from '../core/helper'\nexport const page = helper\n",
            'src/ui/panel.tsx': "import { helper } from '@/core/helper'\nimport { cache } from '@/core/store'\n",
            'src/core/helper.ts': "import { page } from '@/ui/page'\n// import { gone } from './unusedByComment'\n"
                                  "export function helper(a: number, verbose: boolean) { return page }\n",
            'src/core/store.ts': "import type { T } from './types'\nexport let cache = 0\n"
                                 "export const w = new Worker(new URL('./worker.ts', import.meta.url))\n",
            'src/core/types.ts': "import type { S } from './store'\nexport type T = number\n",
            'src/core/worker.ts': 'export {}\n',
            'src/core/unusedByComment.ts': 'export const gone = 1\n',
            'src/core/utils.ts': "import { page } from '@/ui/page'\nexport const u = page\n",
            'src/core/__tests__/helper.test.ts': "import { helper } from '../helper'\n",
            'node_modules/lib/index.js': "import x from './y'\n",
        })
        self.r = self.signals('--layers', 'ui>core')

    def test_alias_and_relative_imports_resolve(self):
        fan_in = {r['unit']: r['importers'] for r in self.r['fan_in']}
        self.assertEqual(fan_in['src/ui/page.tsx'], 3)
        self.assertEqual(fan_in['src/core/helper.ts'], 2)

    def test_runtime_and_type_only_cycles_are_separate(self):
        self.assertIn({'src/ui/page.tsx', 'src/core/helper.ts'}, cycle_sets(self.r['cycles_runtime']))
        self.assertEqual(cycle_sets(self.r['cycles_type_only']), [{'src/core/store.ts', 'src/core/types.ts'}])

    def test_unused_candidates(self):
        unused = files_of(self.r['unused_candidates'])
        self.assertIn('src/core/unusedByComment.ts', unused)       # commented import does not count
        self.assertNotIn('src/core/worker.ts', unused)              # new URL(...) counts as an import
        self.assertNotIn('src/main.ts', unused)                      # entry point
        self.assertIn('src/core/utils.ts', unused)

    def test_tests_and_vendor_skipped(self):
        self.assertEqual(self.r['summary']['files'], 9)

    def test_folder_direction(self):
        both = self.r['folders_both_ways']
        self.assertEqual(len(both), 1)
        self.assertEqual(both[0]['minority'], 'core -> ui')
        self.assertEqual(both[0]['minority_count'], 2)
        self.assertEqual(sorted(self.r['upward_imports']),
                         ['src/core/helper.ts -> src/ui/page.tsx', 'src/core/utils.ts -> src/ui/page.tsx'])

    def test_heuristics(self):
        self.assertIn('src/core/store.ts', files_of(self.r['module_mutable_state']))
        self.assertIn('src/core/helper.ts', files_of(self.r['flag_parameters']))
        self.assertEqual(files_of(self.r['grab_bag_names']), {'src/core/utils.ts', 'src/core/helper.ts'})
        spread = {x['dependency']: x['files'] for x in self.r['external_spread']}
        self.assertEqual(spread, {'react': 1, '@scope/pkg': 1})  # scoped packages keep their scope

    def test_include_tests_and_exclude(self):
        self.assertEqual(self.signals('--include-tests')['summary']['files'], 10)
        r = self.signals('--exclude', 'src/core/utils.ts')
        self.assertNotIn('src/core/utils.ts', files_of(r['largest']))

    def test_dir_unit_collapses_to_folders(self):
        r = self.signals('--unit', 'dir')
        self.assertIn({'src/ui', 'src/core'}, cycle_sets(r['cycles_runtime']))

    def test_only_limits_printed_sections(self):
        code, out, _ = run('signals', self.root, '--only', 'summary')
        self.assertEqual(code, 0)
        self.assertIn('== summary', out)
        self.assertNotIn('== fan_in', out)
        code, out, _ = run('signals', self.root, '--only', 'fan_in', '--top', '1')
        self.assertEqual(code, 0)
        self.assertRegex(out, r'… \d+ more')

    def test_no_git_history(self):
        self.assertEqual(self.r['churn'], 'no git history')
        self.assertEqual(self.r['cochange_without_import'], [])


class PythonProject(TempTree):
    def test_imports_cycles_and_state(self):
        self.write({
            'pkg/__init__.py': '',
            'pkg/a.py': 'from . import b\nfrom .sub import c\nimport json\n',
            'pkg/b.py': 'from pkg.a import thing\n"""\nimport pkg.unused\n"""\n',
            'pkg/sub/__init__.py': '',
            'pkg/sub/c.py': 'registry = {}\nLIMITS = {}\ndef f(x, strict=False):\n    global registry\n',
            'pkg/unused.py': 'x = 1\n',
        })
        r = self.signals()
        self.assertIn({'pkg/a.py', 'pkg/b.py'}, cycle_sets(r['cycles_runtime']))
        fan_in = {x['unit']: x['importers'] for x in r['fan_in']}
        self.assertEqual(fan_in.get('pkg/sub/c.py'), 1)
        self.assertIn('pkg/unused.py', files_of(r['unused_candidates']))  # docstring import does not count
        state = [x['text'] for x in r['module_mutable_state']]
        self.assertTrue(any(t.startswith('registry') for t in state))
        self.assertTrue(any(t.startswith('global registry') for t in state))
        self.assertFalse(any(t.startswith('LIMITS') for t in state))     # ALL_CAPS treated as a constant
        self.assertIn('pkg/sub/c.py', files_of(r['flag_parameters']))
        self.assertIn('json', {x['dependency'] for x in r['external_spread']})


class JvmProject(TempTree):
    def test_java_and_kotlin(self):
        self.write({
            'src/main/java/com/ex/a/Alpha.java': 'package com.ex.a;\nimport com.ex.b.Beta;\n// import com.ex.c.Gamma;\n'
                                                 'public class Alpha {\n  static int count = 0;\n  static final int MAX = 1;\n'
                                                 '  public void run(boolean fast) {\n  }\n}\n',
            'src/main/java/com/ex/b/Beta.java': 'package com.ex.b;\nimport com.ex.a.Alpha;\nimport java.util.List;\npublic class Beta {}\n',
            'src/main/java/com/ex/c/Gamma.java': 'package com.ex.c;\npublic class Gamma {}\n',
            'src/main/kotlin/com/ex/k/Kay.kt': 'package com.ex.k\nimport com.ex.c.*\nvar shared = 0\nfun go(flag: Boolean) {}\n',
        })
        r = self.signals()
        self.assertIn({'src/main/java/com/ex/a/Alpha.java', 'src/main/java/com/ex/b/Beta.java'}, cycle_sets(r['cycles_runtime']))
        fan_in = {x['unit']: x['importers'] for x in r['fan_in']}
        self.assertEqual(fan_in['src/main/java/com/ex/c/Gamma.java'], 1)  # wildcard import, not the comment
        state = [x['text'] for x in r['module_mutable_state']]
        self.assertEqual(len([t for t in state if 'count' in t or 'shared' in t]), 2)
        self.assertFalse(any('MAX' in t for t in state))
        self.assertEqual(files_of(r['flag_parameters']),
                         {'src/main/java/com/ex/a/Alpha.java', 'src/main/kotlin/com/ex/k/Kay.kt'})
        self.assertEqual(r['unused_candidates'], [])  # unreliable for JVM, so not reported


class GoProject(TempTree):
    def test_packages_as_units(self):
        self.write({
            'go.mod': 'module example.com/demo\n\ngo 1.21\n',
            'cmd/app/main.go': 'package main\nimport (\n  "fmt"\n  "example.com/demo/internal/store"\n)\nfunc main() {}\n',
            'internal/store/store.go': 'package store\nimport "example.com/demo/internal/util"\nvar cache = map[string]int{}\n',
            'internal/util/util.go': 'package util\nimport "example.com/demo/internal/store"\nfunc X(on bool) int { return 1 }\n',
        })
        r = self.signals('--unit', 'dir')
        self.assertEqual(cycle_sets(r['cycles_runtime']), [{'internal/store', 'internal/util'}])
        self.assertIn('internal/store/store.go', files_of(r['module_mutable_state']))
        self.assertIn('internal/util/util.go', files_of(r['flag_parameters']))
        self.assertIn('fmt', {x['dependency'] for x in r['external_spread']})


class GoWithoutModule(TempTree):
    def test_imports_count_as_external(self):
        self.write({'a/a.go': 'package a\nimport "example.com/x/b"\n'})
        r = self.signals()
        self.assertEqual(r['summary']['internal_edges'], 0)
        self.assertEqual(r['external_spread'], [{'dependency': 'example.com/x/b', 'files': 1}])


class MixedProject(TempTree):
    def setUp(self):
        super().setUp()
        files = {f'src/m/f{i}.ts': 'export const v = 1\n' for i in range(12)}
        files.update({'tools/gen.ts': "import { v } from '../src/m/f0'\n",
                      'tools/gen.py': 'import os\n',
                      'tools/Gen.java': 'package tools;\npublic class Gen {}\n'})
        self.write(files)

    def test_languages_and_folders(self):
        r = self.signals()
        self.assertEqual(r['summary']['by_language'], {'js': 13, 'py': 1, 'java': 1})
        # 12 of 15 files share src/m, so that is the main source dir; tools/ sits outside it.
        self.assertEqual(r['folder_edges'], [{'from': 'tools/ (outside main source dir)', 'to': '(files at top)', 'imports': 1}])
        r = self.signals('--folder-depth', '0')
        self.assertEqual(r['folder_edges'], [{'from': 'tools', 'to': 'src', 'imports': 1}])


@unittest.skipUnless(has_git(), 'git not installed')
class History(TempTree):
    def test_churn_and_cochange(self):
        self.write({'a.py': 'x = 0\n', 'b.py': 'y = 0\n', 'c.py': 'import a\n'})
        self.git('init', '-q')
        for i in range(3):  # a and b change together three times, with no import between them
            self.write({'a.py': f'x = {i + 1}\n', 'b.py': f'y = {i + 1}\n'})
            self.git('add', '-A')
            self.git('commit', '-qm', f'pair {i}')
        for i in range(3):  # a and c also change together three times, but c imports a: not a hidden link
            self.write({'a.py': f'x = {i + 10}\n', 'c.py': f'import a\nz = {i}\n'})
            self.git('add', '-A')
            self.git('commit', '-qm', f'linked {i}')
        r = self.signals()
        churn = {x['file']: x['commits'] for x in r['churn']}
        self.assertEqual(churn, {'a.py': 6, 'b.py': 3, 'c.py': 4})
        pairs = {(x['a'], x['b']): x['together'] for x in r['cochange_without_import']}
        self.assertEqual(pairs, {('a.py', 'b.py'): 3})

    def test_large_commits_do_not_pair(self):
        self.write({f'f{i}.py': '' for i in range(5)})
        self.git('init', '-q')
        for i in range(3):
            self.write({f'f{j}.py': f'v = {i}\n' for j in range(5)})
            self.git('add', '-A')
            self.git('commit', '-qm', f'sweep {i}')
        self.assertEqual(self.signals('--max-commit-files', '4')['cochange_without_import'], [])
        self.assertEqual(len(self.signals('--max-commit-files', '5')['cochange_without_import']), 10)


if __name__ == '__main__':
    unittest.main()
