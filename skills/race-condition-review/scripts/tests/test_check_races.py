"""Tests for check_races.py. Run: python3 -I -m unittest discover -s <scripts>/tests -t <scripts>/tests"""
import copy
import json
import unittest

from helpers import TempTree, load, run

C = load('check_races')

GOOD = [
    {'id': 'R1', 'status': 'race', 'severity': 'critical', 'pattern': 'R1', 'impact': 'I1', 'trigger': 'outside',
     'location': 'redeem.py:12', 'shared_state': 'coupon row (code)', 'window': 'is_redeemed() at 12 .. mark at 15',
     'interleaving': ['A: is_redeemed -> false', 'B: is_redeemed -> false', 'A: credit 10', 'B: credit 10'],
     'invariant': 'a coupon credits once', 'outcome': 'two parallel requests credit 20',
     'evidence': 'reproduced', 'reproduction': 'python3 -I repro.py --parallel 2', 'also_at': ['gift.py:40']},
    {'id': 'R2', 'status': 'race', 'severity': 'medium', 'pattern': 'R4', 'impact': 'I3', 'trigger': 'normal',
     'location': 'search.ts:3-4', 'shared_state': 'results list', 'window': 'await fetch .. setResults',
     'interleaving': ['User: types "ab"', 'User: types "abc"', 'Net: "abc" reply', 'Net: "ab" reply'],
     'invariant': 'results match the latest query', 'outcome': 'shows results for "ab"', 'evidence': 'weak'},
    {'id': 'S1', 'status': 'suspected', 'severity': 'medium', 'pattern': 'R7', 'impact': 'I2',
     'location': 'design.md#failover', 'shared_state': 'leader lease', 'window': 'lease expiry .. write',
     'interleaving': ['Old leader: pauses', 'New leader: takes lease', 'Old leader: writes'],
     'invariant': 'one writer at a time', 'outcome': 'two writers', 'to_confirm': 'does storage check a fencing token?'},
    {'id': 'D1', 'status': 'dismissed', 'location': 'cart.py:20', 'shared_state': 'cart row',
     'window': 'read .. save', 'interleaving': ['A: read v1', 'B: read v1'], 'invariant': 'no lost item',
     'blocked_by': 'cart.py:25', 'note': 'save uses a version check'},
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
        self.assertIn('"invariant"', ' '.join(fails(with_change(3, invariant=None))))
        self.assertIn('item 2:', ' '.join(fails(with_change(1, id=None))))

    def test_interleaving(self):
        self.assertIn('at least 2 steps', ' '.join(fails(with_change(0, interleaving=['A: only']))))
        self.assertIn('at least 2 steps', ' '.join(fails(with_change(0, interleaving='A then B'))))
        self.assertIn('at least 2 steps', ' '.join(fails(with_change(0, interleaving=['A: x', ' ']))))
        self.assertIn('start with its actor', ' '.join(fails(with_change(0, interleaving=['A: x', 'then B']))))
        self.assertIn('2 different actors', ' '.join(fails(with_change(0, interleaving=['A: x', 'a: y']))))

    def test_locations(self):
        self.assertIn('file:line', ' '.join(fails(with_change(0, location='redeem.py'))))
        self.assertIn('also_at', ' '.join(fails(with_change(0, also_at=['nowhere']))))
        self.assertIn('must be a list', ' '.join(fails(with_change(0, also_at='a.py:1'))))
        self.assertEqual(fails(with_change(0, location='src/a b.py:10-12')), [])

    def test_enums(self):
        self.assertIn('R1-R11', ' '.join(fails(with_change(0, pattern='R12'))))
        self.assertIn('I1-I9', ' '.join(fails(with_change(0, impact='I10'))))
        self.assertIn('severity must be', ' '.join(fails(with_change(0, severity='severe'))))
        self.assertIn('evidence must be', ' '.join(fails(with_change(0, evidence='sure'))))
        self.assertIn('trigger must be', ' '.join(fails(with_change(0, trigger='often'))))

    def test_evidence_and_trigger_rules(self):
        self.assertIn('mark it "suspected"', ' '.join(fails(with_change(1, evidence='guess'))))
        self.assertIn('needs reproduced or strong', ' '.join(fails(with_change(0, evidence='weak'))))
        self.assertIn('"reproduction" command', ' '.join(fails(with_change(0, reproduction=None))))
        self.assertIn('medium at most', ' '.join(fails(with_change(2, severity='high'))))
        self.assertIn('rare trigger', ' '.join(fails(with_change(0, trigger='rare'))))

    def test_order(self):
        items = copy.deepcopy(GOOD)
        items[0], items[1] = items[1], items[0]
        self.assertIn('must be ordered', ' '.join(fails(items)))

    def test_secret_shapes(self):
        for value in ('-----BEGIN RSA PRIVATE KEY-----', 'Zq8vR2mXk4LpT7wN1yB5cF9hJ3dG6sQe0aUiOuY',
                      'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop', 'password=hunter22secret'):
            self.assertIn('cite the location instead', ' '.join(fails(with_change(1, outcome=value))), value)
        hidden = with_change(1, interleaving=['A: sends password=hunter22secret', 'B: reads'])
        self.assertIn('"interleaving" looks like', ' '.join(fails(hidden)))
        self.assertEqual(fails(with_change(1, outcome='token=<redacted>')), [])


class Markdown(unittest.TestCase):
    def test_tables(self):
        md = C.markdown(GOOD)
        self.assertIn('## Races', md)
        self.assertIn('| R1 | Critical | I1 Security or limit bypass | R1 Check-then-act | `redeem.py:12`, `gift.py:40` |',
                      md)
        self.assertIn('A: is_redeemed -> false → B: is_redeemed -> false', md)
        self.assertIn('Reproduced: `python3 -I repro.py --parallel 2`', md)
        self.assertIn('| normal | Weak |', md)
        self.assertIn('| S1 | I2 Data corruption or loss | R7 Message timing against faults | `design.md#failover` |', md)
        self.assertIn('| `cart.py:25` | save uses a version check |', md)

    def test_empty_sections_and_escaping(self):
        md = C.markdown([dict(GOOD[0], shared_state='a|b')])
        self.assertIn('a\\|b', md)
        self.assertIn('## Suspected\n\nNone.', md)
        self.assertIn('## Dismissed\n\nNone.', md)
        self.assertIn('## Races\n\nNone found.', C.markdown([]))


class Cli(TempTree):
    def check(self, data, *args):
        path = self.path('list.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return run('check_races', path, *args)

    def test_ok_and_markdown(self):
        code, out, _ = self.check({'items': GOOD}, '--markdown')
        self.assertEqual(code, 0)
        self.assertIn('OK: 2 races, 1 suspected, 1 dismissed', out)
        self.assertIn('## Dismissed', out)

    def test_failures(self):
        code, out, _ = self.check(with_change(0, evidence='weak'), '--markdown')
        self.assertEqual(code, 1)
        self.assertIn('FAIL item R1', out)
        self.assertNotIn('## Races', out)

    def test_bad_files(self):
        self.assertIn('cannot read', self.check('{not json')[1])
        self.assertIn('array of items', self.check({'nope': 1})[1])
        code, _, _ = run('check_races', self.path('missing.json'))
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
