#!/usr/bin/env python3
"""Check a logic-gap-review loophole list, and optionally print it as Markdown.

Read-only. Python 3.8+ standard library only.

Input: a JSON file holding an array of items, or an object {"items": [...]}.
Every item has a "status": "loophole", "suspected" or "dismissed". The fields
each status needs are listed in the skill's SKILL.md, Step 7.

Usage:
  python3 -I check_loopholes.py LIST.json [--markdown]

Prints one FAIL line per problem and exits 1, or prints OK and exits 0.
With --markdown and no problems, also prints the Loopholes, Suspected and
Dismissed tables.
"""
import argparse
import json
import re
import sys

SEVERITIES = ['critical', 'high', 'medium', 'low']
EVIDENCE = ['reproduced', 'strong', 'weak', 'guess']
CATEGORIES = {
    'C1': 'Crash', 'C2': 'Injection', 'C3': 'Wrong result', 'C4': 'Security bypass',
    'C5': 'Data corruption or loss', 'C6': 'Hang or resource exhaustion', 'C7': 'Concurrency fault',
    'C8': 'Silent failure', 'C9': 'Sensitive data exposure', 'C10': 'Resource leak',
}
COMMON = ['id', 'status', 'location', 'node', 'missing_case', 'trigger']
REQUIRED = {
    'loophole': COMMON + ['severity', 'category', 'outcome', 'evidence'],
    'suspected': COMMON + ['category', 'outcome', 'to_confirm'],
    'dismissed': COMMON + ['blocked_by'],
}
LOCATION = re.compile(r'^\S(?:.*\S)?:\d+(?:-\d+)?$')
CONCRETE_CHARS = re.compile(r'[0-9"\'`\[\]{}()=:<>/\\-]')
CONCRETE_WORDS = re.compile(r'\b(?:null|nil|None|undefined|NaN|Infinity|true|false|True|False|empty)\b')
SECRETS = [
    ('private key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('access key ID', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('signed token', re.compile(r'\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}')),
    ('credential value', re.compile(r'(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*[\'"]?'
                                    r'[^\s\'"<${][^\s\'"]{7,}')),
]


def text(v):
    return isinstance(v, str) and v.strip() != ''


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
        locations = [('location', it.get('location')), ('blocked_by', it.get('blocked_by'))]
        also = it.get('also_at', [])
        if not isinstance(also, list):
            fails.append(f'{label}: "also_at" must be a list')
            also = []
        locations += [('also_at', x) for x in also]
        for field, value in locations:
            if text(value) and not LOCATION.match(value):
                fails.append(f'{label}: "{field}" must look like file:line, got {value!r}')
        if text(it.get('trigger')) and not (CONCRETE_CHARS.search(it['trigger']) or CONCRETE_WORDS.search(it['trigger'])):
            fails.append(f'{label}: "trigger" must be a concrete value, not a description')
        if 'category' in it and it['category'] not in CATEGORIES:
            fails.append(f'{label}: category must be C1-C10')
        severity, evidence = it.get('severity'), it.get('evidence')
        if severity is not None and severity not in SEVERITIES:
            fails.append(f'{label}: severity must be one of {", ".join(SEVERITIES)}')
            severity = None
        if evidence is not None and evidence not in EVIDENCE:
            fails.append(f'{label}: evidence must be one of {", ".join(EVIDENCE)}')
            evidence = None
        if status == 'loophole':
            if evidence == 'guess':
                fails.append(f'{label}: a guess is not a loophole; mark it "suspected"')
            if severity in ('critical', 'high') and evidence == 'weak':
                fails.append(f'{label}: {severity} needs reproduced or strong evidence; confirm it or mark it "suspected"')
            if evidence == 'reproduced' and not text(it.get('reproduction')):
                fails.append(f'{label}: reproduced evidence needs a "reproduction" command')
            if severity in SEVERITIES:
                rank = SEVERITIES.index(severity)
                if rank < last_rank:
                    fails.append(f'{label}: loopholes must be ordered critical, high, medium, low')
                last_rank = max(last_rank, rank)
        if status == 'suspected' and severity in ('critical', 'high'):
            fails.append(f'{label}: a suspected item is rated medium at most')
        for field, value in it.items():
            for what, pat in SECRETS:
                if isinstance(value, str) and pat.search(value):
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

    def evidence(it):
        e = it['evidence'].capitalize()
        return f"{e}: `{it['reproduction']}`" if text(it.get('reproduction')) else e

    def category(it):
        return f"{it['category']} {CATEGORIES[it['category']]}"

    parts = []
    loopholes = [i for i in items if i['status'] == 'loophole']
    suspected = [i for i in items if i['status'] == 'suspected']
    dismissed = [i for i in items if i['status'] == 'dismissed']
    parts.append('## Loopholes\n\n' + (table(
        ['ID', 'Severity', 'Category', 'Where', 'Logic node', 'Missing case', 'Trigger input', 'What happens', 'Evidence'],
        [[i['id'], i['severity'].capitalize(), category(i), where(i), i['node'], i['missing_case'], f"`{i['trigger']}`",
          i['outcome'], evidence(i)] for i in loopholes]) if loopholes else 'None found.'))
    parts.append('## Suspected\n\n' + (table(
        ['ID', 'Category', 'Where', 'Missing case', 'Trigger input', 'Possible outcome', 'To confirm'],
        [[i['id'], category(i), where(i), i['missing_case'], f"`{i['trigger']}`", i['outcome'], i['to_confirm']]
         for i in suspected]) if suspected else 'None.'))
    parts.append('## Dismissed\n\n' + (table(
        ['ID', 'Where', 'Missing case', 'Trigger input', 'Blocked by', 'Note'],
        [[i['id'], where(i), i['missing_case'], f"`{i['trigger']}`", f"`{i['blocked_by']}`", i.get('note', '')]
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
    print(f"OK: {counts['loophole']} loopholes, {counts['suspected']} suspected, {counts['dismissed']} dismissed")
    if a.markdown:
        print('\n' + markdown(items))
    return 0


if __name__ == '__main__':
    sys.exit(main())
