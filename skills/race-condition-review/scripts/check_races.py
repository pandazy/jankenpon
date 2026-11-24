#!/usr/bin/env python3
"""Check a race-condition-review finding list, and optionally print it as Markdown.

Read-only. Python 3.8+ standard library only.

Input: a JSON file holding an array of items, or an object {"items": [...]}.
Every item has a "status": "race", "suspected" or "dismissed". The fields
each status needs are listed in the skill's SKILL.md, Step 9.

Usage:
  python3 -I check_races.py LIST.json [--markdown]

Prints one FAIL line per problem and exits 1, or prints OK and exits 0.
With --markdown and no problems, also prints the Races, Suspected and
Dismissed tables.
"""
import argparse
import json
import re
import sys

SEVERITIES = ['critical', 'high', 'medium', 'low']
EVIDENCE = ['reproduced', 'strong', 'weak', 'guess']
TRIGGERS = ['outside', 'normal', 'rare']
PATTERNS = {
    'R1': 'Check-then-act', 'R2': 'Lost update', 'R3': 'Order violation', 'R4': 'Stale or out-of-order result',
    'R5': 'Exposed partial state', 'R6': 'Duplicate or replayed operation', 'R7': 'Message timing against faults',
    'R8': 'Isolation anomaly', 'R9': 'Lifecycle race', 'R10': 'Lock and memory fault', 'R11': 'Stampede',
}
IMPACTS = {
    'I1': 'Security or limit bypass', 'I2': 'Data corruption or loss', 'I3': 'Wrong or stale result', 'I4': 'Crash',
    'I5': 'Hang, deadlock or outage', 'I6': 'Wasted resources', 'I7': 'Resource leak', 'I8': 'Cross-user data exposure',
    'I9': 'Silent divergence',
}
COMMON = ['id', 'status', 'location', 'shared_state', 'window', 'invariant']
REQUIRED = {
    'race': COMMON + ['pattern', 'impact', 'trigger', 'severity', 'outcome', 'evidence'],
    'suspected': COMMON + ['pattern', 'impact', 'outcome', 'to_confirm'],
    'dismissed': COMMON + ['blocked_by'],
}
LOCATION = re.compile(r'^\S(?:.*\S)?(?::\d+(?:-\d+)?|#\S+)$')
STEP = re.compile(r'^\s*([A-Za-z][\w .-]{0,30}?)\s*:\s*\S')
SECRETS = [
    ('private key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    # A long token that mixes upper case, lower case and digits, the shape most generated keys share.
    ('long random-looking key', re.compile(r'(?<![\w+/-])(?=[\w+/-]*[A-Z])(?=[\w+/-]*[a-z])(?=[\w+/-]*\d)'
                                         r'[\w+/-]{32,}={0,2}(?![\w+/-])')),
    ('signed token', re.compile(r'\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}')),
    ('credential value', re.compile(r'(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*[\'"]?'
                                    r'[^\s\'"<${][^\s\'"]{7,}')),
]


def text(v):
    return isinstance(v, str) and v.strip() != ''


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


def check_interleaving(label, it, fails):
    steps = it.get('interleaving')
    if not isinstance(steps, list) or len(steps) < 2 or not all(text(s) for s in steps):
        fails.append(f'{label}: "interleaving" must be a list of at least 2 steps, e.g. ["A: reads 10", "B: reads 10"]')
        return
    actors = []
    for s in steps:
        m = STEP.match(s)
        if not m:
            fails.append(f'{label}: interleaving step {s!r} must start with its actor, e.g. "A: ..."')
            return
        actors.append(m.group(1).strip().lower())
    if len(set(actors)) < 2:
        fails.append(f'{label}: the interleaving needs at least 2 different actors')


def check(items):
    fails, ids, last_rank = [], set(), -1
    for n, it in enumerate(items, 1):
        label = f'item {n}'
        if not isinstance(it, dict):
            fails.append(f'{label}: must be an object')
            continue
        if text(it.get('id')):
            label = f"item {it['id']}"
            if it['id'] in ids:
                fails.append(f'{label}: duplicate id')
            ids.add(it['id'])
        status = it.get('status')
        if status not in REQUIRED:
            fails.append(f'{label}: status must be one of {", ".join(REQUIRED)}')
            continue
        for field in REQUIRED[status]:
            if not text(it.get(field)):
                fails.append(f'{label}: missing or empty "{field}"')
        check_interleaving(label, it, fails)
        locations = [('location', it.get('location')), ('blocked_by', it.get('blocked_by'))]
        also = it.get('also_at', [])
        if not isinstance(also, list):
            fails.append(f'{label}: "also_at" must be a list')
            also = []
        locations += [('also_at', x) for x in also]
        for field, value in locations:
            if text(value) and not LOCATION.match(value):
                fails.append(f'{label}: "{field}" must look like file:line or file#section, got {value!r}')
        if 'pattern' in it and it['pattern'] not in PATTERNS:
            fails.append(f'{label}: pattern must be R1-R11')
        if 'impact' in it and it['impact'] not in IMPACTS:
            fails.append(f'{label}: impact must be I1-I9')
        severity, evidence, trigger = it.get('severity'), it.get('evidence'), it.get('trigger')
        if severity is not None and severity not in SEVERITIES:
            fails.append(f'{label}: severity must be one of {", ".join(SEVERITIES)}')
            severity = None
        if evidence is not None and evidence not in EVIDENCE:
            fails.append(f'{label}: evidence must be one of {", ".join(EVIDENCE)}')
            evidence = None
        if trigger is not None and trigger not in TRIGGERS:
            fails.append(f'{label}: trigger must be one of {", ".join(TRIGGERS)}')
            trigger = None
        if status == 'race':
            if evidence == 'guess':
                fails.append(f'{label}: a guess is not a race finding; mark it "suspected"')
            if severity in ('critical', 'high') and evidence == 'weak':
                fails.append(f'{label}: {severity} needs reproduced or strong evidence; confirm it or mark it "suspected"')
            if evidence == 'reproduced' and not text(it.get('reproduction')):
                fails.append(f'{label}: reproduced evidence needs a "reproduction" command')
            if severity == 'critical' and trigger == 'rare':
                fails.append(f'{label}: a rare trigger is rated high at most')
            if severity in SEVERITIES:
                rank = SEVERITIES.index(severity)
                if rank < last_rank:
                    fails.append(f'{label}: races must be ordered critical, high, medium, low')
                last_rank = max(last_rank, rank)
        if status == 'suspected' and severity in ('critical', 'high'):
            fails.append(f'{label}: a suspected item is rated medium at most')
        for field, value in it.items():
            for s in strings(value):
                for what, pat in SECRETS:
                    if pat.search(s):
                        fails.append(f'{label}: "{field}" looks like it holds a {what}; cite the location instead')
    return fails


def cell(v):
    return str(v or '').replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    out += ['| ' + ' | '.join(cell(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def markdown(items):
    def where(it):
        return ', '.join([f"`{it['location']}`"] + [f'`{x}`' for x in it.get('also_at', [])])

    def steps(it):
        return ' → '.join(it['interleaving'])

    def evidence(it):
        e = it['evidence'].capitalize()
        return f"{e}: `{it['reproduction']}`" if text(it.get('reproduction')) else e

    def pattern(it):
        return f"{it['pattern']} {PATTERNS[it['pattern']]}"

    def impact(it):
        return f"{it['impact']} {IMPACTS[it['impact']]}"

    races = [i for i in items if i['status'] == 'race']
    suspected = [i for i in items if i['status'] == 'suspected']
    dismissed = [i for i in items if i['status'] == 'dismissed']
    parts = ['## Races\n\n' + (table(
        ['ID', 'Severity', 'Impact', 'Pattern', 'Where', 'Shared state', 'Interleaving', 'Invariant broken',
         'What happens', 'Trigger', 'Evidence'],
        [[i['id'], i['severity'].capitalize(), impact(i), pattern(i), where(i), i['shared_state'], steps(i),
          i['invariant'], i['outcome'], i['trigger'], evidence(i)] for i in races]) if races else 'None found.')]
    parts.append('## Suspected\n\n' + (table(
        ['ID', 'Impact', 'Pattern', 'Where', 'Shared state', 'Interleaving', 'Possible outcome', 'To confirm'],
        [[i['id'], impact(i), pattern(i), where(i), i['shared_state'], steps(i), i['outcome'], i['to_confirm']]
         for i in suspected]) if suspected else 'None.'))
    parts.append('## Dismissed\n\n' + (table(
        ['ID', 'Where', 'Shared state', 'Interleaving', 'Blocked by', 'Note'],
        [[i['id'], where(i), i['shared_state'], steps(i), f"`{i['blocked_by']}`", i.get('note', '')]
         for i in dismissed]) if dismissed else 'None.'))
    return '\n\n'.join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--markdown', action='store_true', help='Print the tables when the list passes.')
    a = ap.parse_args(argv)
    try:
        with open(a.file, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        print(f'FAIL cannot read {a.file}: {e}')
        return 1
    items = data.get('items') if isinstance(data, dict) else data
    if not isinstance(items, list):
        print('FAIL the file must hold an array of items, or an object with an "items" array')
        return 1
    fails = check(items)
    for f in fails:
        print('FAIL ' + f)
    if fails:
        return 1
    counts = {s: sum(1 for i in items if i['status'] == s) for s in REQUIRED}
    print(f"OK: {counts['race']} races, {counts['suspected']} suspected, {counts['dismissed']} dismissed")
    if a.markdown:
        print('\n' + markdown(items))
    return 0


if __name__ == '__main__':
    sys.exit(main())
