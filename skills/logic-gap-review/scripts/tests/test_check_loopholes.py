"""Tests for check_loopholes.py. Run: python3 -I -m unittest discover -s <scripts>/tests -t <scripts>/tests"""
import copy
import json
import unittest

from helpers import TempTree, load, run

C = load('check_loopholes')

GOOD = [
    {'id': 'L1', 'status': 'loophole', 'severity': 'high', 'category': 'C3', 'location': 'calc.js:14',
     'node': 'reduce with +', 'missing_case': 'amount is a string', 'trigger': '[{"amount":"10"},{"amount":"2"}]',
     'outcome': 'returns "0102" instead of 12', 'evidence': 'reproduced', 'reproduction': 'node -e "..."',
     'also_at': ['calc.js:30']},
    {'id': 'L2', 'status': 'loophole', 'severity': 'low', 'category': 'C3', 'location': 'label.js:3',
     'node': 'template literal', 'missing_case': 'name missing', 'trigger': '{}', 'outcome': 'shows "Item undefined"',
     'evidence': 'weak'},
    {'id': 'S1', 'status': 'suspected', 'severity': 'medium', 'category': 'C2', 'location': 'db.js:8',
     'node': 'query', 'missing_case': 'quote in name', 'trigger': "name = x'", 'outcome': 'query breaks',
     'to_confirm': 'read the caller in api.js'},
    {'id': 'D1', 'status': 'dismissed', 'location': 'band.py:7', 'node': 'if/elif', 'missing_case': 'size is 0',
     'trigger': 'size = 0', 'blocked_by': 'band.py:5', 'note': 'guard raises first'},
]


def fails(items):
    return C.check(items)


def with_change(index, **changes):
    items = copy.deepcopy(GOOD)
    for k, v in changes.items():
        if v is None:
            items[index].pop(k, None)
        else:
            items[index][k] = v
    return items


class Rules(unittest.TestCase):
    def test_good_list_passes(self):
        self.assertEqual(fails(GOOD), [])

    def test_shape_and_status(self):
        self.assertIn('must be an object', fails(['x'])[0])
        self.assertIn('status must be', fails(with_change(0, status='maybe'))[0])
        self.assertIn('duplicate id', ' '.join(fails(GOOD + [dict(GOOD[1])])))

    def test_required_fields_per_status(self):
        self.assertIn('"outcome"', ' '.join(fails(with_change(0, outcome=None))))
        self.assertIn('"to_confirm"', ' '.join(fails(with_change(2, to_confirm=' '))))
        self.assertIn('"blocked_by"', ' '.join(fails(with_change(3, blocked_by=None))))
        self.assertIn('item 2:', ' '.join(fails(with_change(1, id=None))))

    def test_locations(self):
        self.assertIn('file:line', ' '.join(fails(with_change(0, location='calc.js'))))
        self.assertIn('also_at', ' '.join(fails(with_change(0, also_at=['nowhere']))))
        self.assertIn('must be a list', ' '.join(fails(with_change(0, also_at='calc.js:1'))))
        self.assertEqual(fails(with_change(0, location='src/a b.js:10-12')), [])

    def test_trigger_must_be_concrete(self):
        self.assertIn('concrete value', ' '.join(fails(with_change(1, trigger='some bad input'))))
        self.assertEqual(fails(with_change(1, trigger='NaN')), [])
        self.assertEqual(fails(with_change(1, trigger='empty list')), [])

    def test_enums(self):
        self.assertIn('C1-C10', ' '.join(fails(with_change(0, category='C11'))))
        self.assertIn('severity must be', ' '.join(fails(with_change(0, severity='severe'))))
        self.assertIn('evidence must be', ' '.join(fails(with_change(0, evidence='sure'))))

    def test_evidence_rules(self):
        self.assertIn('mark it "suspected"', ' '.join(fails(with_change(1, evidence='guess'))))
        self.assertIn('needs reproduced or strong', ' '.join(fails(with_change(0, evidence='weak'))))
        self.assertIn('"reproduction" command', ' '.join(fails(with_change(0, reproduction=None))))
        self.assertIn('medium at most', ' '.join(fails(with_change(2, severity='high'))))

    def test_order(self):
        items = copy.deepcopy(GOOD)
        items[0], items[1] = items[1], items[0]
        self.assertIn('must be ordered', ' '.join(fails(items)))

    def test_secret_shapes(self):
        for value in ('-----BEGIN RSA PRIVATE KEY-----', 'AKIAABCDEFGHIJKLMNOP',
                      'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop', 'password=hunter22secret'):
            self.assertIn('cite the location instead', ' '.join(fails(with_change(1, trigger=value))), value)
        self.assertEqual(fails(with_change(1, trigger='token=<redacted>')), [])


class Markdown(unittest.TestCase):
    def test_tables(self):
        md = C.markdown(GOOD)
        self.assertIn('## Loopholes', md)
        self.assertIn('| L1 | High | C3 Wrong result | `calc.js:14`, `calc.js:30` |', md)
        self.assertIn('Reproduced: `node -e "..."`', md)
        self.assertIn('| L2 | Low | C3 Wrong result | `label.js:3` | template literal | name missing | `{}` '
                      '| shows "Item undefined" | Weak |', md)
        self.assertIn('| S1 | C2 Injection |', md)
        self.assertIn('| D1 | `band.py:7` | size is 0 | `size = 0` | `band.py:5` | guard raises first |', md)

    def test_empty_sections_and_escaping(self):
        md = C.markdown([dict(GOOD[0], node='a|b')])
        self.assertIn('a\\|b', md)
        self.assertIn('## Suspected\n\nNone.', md)
        self.assertIn('## Dismissed\n\nNone.', md)
        self.assertIn('## Loopholes\n\nNone found.', C.markdown([]))


class Cli(TempTree):
    def check(self, data, *args):
        path = self.path('list.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return run('check_loopholes', path, *args)

    def test_ok_and_markdown(self):
        code, out, _ = self.check({'items': GOOD}, '--markdown')
        self.assertEqual(code, 0)
        self.assertIn('OK: 2 loopholes, 1 suspected, 1 dismissed', out)
        self.assertIn('## Dismissed', out)

    def test_failures(self):
        code, out, _ = self.check(with_change(0, evidence='weak'), '--markdown')
        self.assertEqual(code, 1)
        self.assertIn('FAIL item L1', out)
        self.assertNotIn('## Loopholes', out)

    def test_bad_files(self):
        self.assertIn('cannot read', self.check('{not json')[1])
        self.assertIn('array of items', self.check({'nope': 1})[1])
        code, out, _ = run('check_loopholes', self.path('missing.json'))
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
