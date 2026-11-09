#!/usr/bin/env python3
"""Check a review report (HTML or Markdown) before handing it over.

Read-only. Python 3.8+ standard library only. Exit code 1 when a check fails.

Checks:
  HTML      unbalanced tags, duplicate ids, table rows whose cell count
            (with colspan) differs from the header, empty headings, images
            without alt text, empty links.
  Markdown  table rows whose column count differs from the header.
  Both      required section headings are present; no method labels leak
            into the text; the report opens with an answer before the first
            section heading.

Usage:
  python3 -I check_report.py REPORT [--require "Red,Yellow,Green"] [--forbid "a,b"]
"""
import argparse
import html.parser
import re
import sys

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
OPTIONAL_END = {'p', 'li', 'td', 'th', 'tr', 'thead', 'tbody', 'tfoot', 'option', 'dt', 'dd'}
DEFAULT_FORBID = [
    'Layer A', 'Layer B', 'Layer C', 'STE100', 'ASD-STE100', 'Feynman', 'ELI5',
    'explained simply', 'in plain English', 'Simple explanation', 'Bayesian update',
]


class HtmlChecker(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors, self.ids, self.stack = [], {}, []
        self.headings, self._heading = [], None
        self.text_before_first_h2, self.seen_h2 = [], False
        self.tables, self.in_script = [], False
        self.visible = []

    def line(self):
        return self.getpos()[0]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            if a['id'] in self.ids:
                self.errors.append(f'line {self.line()}: duplicate id "{a["id"]}" (first at line {self.ids[a["id"]]})')
            else:
                self.ids[a['id']] = self.line()
        if tag == 'img' and not a.get('alt'):
            self.errors.append(f'line {self.line()}: <img> without alt text')
        if tag == 'a' and 'href' in a and a['href'].strip() in ('', '#'):
            self.errors.append(f'line {self.line()}: link with empty href')
        if tag in ('script', 'style'):
            self.in_script = True
        if re.fullmatch(r'h[1-6]', tag):
            self._heading = [tag, self.line(), '']
            if tag == 'h2':
                self.seen_h2 = True
        if tag == 'table':
            self.tables.append({'line': self.line(), 'header': None, 'rows': [], 'cur': None, 'in_head': False})
        if self.tables:
            t = self.tables[-1]
            if tag == 'thead':
                t['in_head'] = True
            elif tag == 'tr':
                t['cur'] = [self.line(), 0, t['in_head']]
            elif tag in ('td', 'th') and t['cur'] is not None:
                t['cur'][1] += int(a.get('colspan') or 1)
        if tag not in VOID:
            self.stack.append((tag, self.line()))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in ('script', 'style'):
            self.in_script = False
        if self._heading and tag == self._heading[0]:
            if not self._heading[2].strip():
                self.errors.append(f'line {self._heading[1]}: empty <{tag}>')
            self.headings.append(self._heading[2].strip())
            self._heading = None
        if self.tables:
            t = self.tables[-1]
            if tag == 'thead':
                t['in_head'] = False
            elif tag == 'tr' and t['cur'] is not None:
                ln, cells, head = t['cur']
                if head and t['header'] is None:
                    t['header'] = cells
                else:
                    t['rows'].append((ln, cells))
                t['cur'] = None
            elif tag == 'table':
                self._check_table(self.tables.pop())
        # pop to the matching open tag; anything skipped must allow an implied end tag
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for skipped, ln in self.stack[i + 1:]:
                    if skipped not in OPTIONAL_END:
                        self.errors.append(f'line {ln}: <{skipped}> is not closed before </{tag}> at line {self.line()}')
                del self.stack[i:]
                return
        self.errors.append(f'line {self.line()}: </{tag}> has no matching open tag')

    def handle_data(self, data):
        if self.in_script:
            return
        if self._heading:
            self._heading[2] += data
        self.visible.append(data)
        if not self.seen_h2:
            self.text_before_first_h2.append(data)

    def _check_table(self, t):
        width = t['header'] if t['header'] is not None else (t['rows'][0][1] if t['rows'] else 0)
        for ln, cells in t['rows']:
            if cells != width:
                self.errors.append(f'line {ln}: table row has {cells} cells, header has {width} (table at line {t["line"]})')

    def finish(self):
        for tag, ln in self.stack:
            if tag not in OPTIONAL_END and tag not in ('html', 'body', 'head'):
                self.errors.append(f'line {ln}: <{tag}> is never closed')


def check_html(text):
    c = HtmlChecker()
    c.feed(text)
    c.close()
    c.finish()
    return c.errors, c.headings, ' '.join(c.visible), ' '.join(c.text_before_first_h2)


def check_markdown(text):
    errors, headings, lines = [], [], text.split('\n')
    in_code = False
    first_h2 = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith('```'):
            in_code = not in_code
        elif not in_code:
            m = re.match(r'^(#{1,6})\s+(.*)$', ln)
            if m:
                headings.append(m.group(2).strip())
                if len(m.group(1)) == 2 and first_h2 is None:
                    first_h2 = i
            if ln.strip().startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|?\s*:?-{3,}', lines[i + 1]):
                cols = lambda s: len([c for c in re.split(r'(?<!\\)\|', s.strip().strip('|'))])
                width = cols(ln)
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith('|'):
                    if cols(lines[j]) != width:
                        errors.append(f'line {j + 1}: table row has {cols(lines[j])} columns, header has {width}')
                    j += 1
                i = j
                continue
        i += 1
    before = '\n'.join(lines[:first_h2] if first_h2 is not None else lines)
    before = re.sub(r'(?m)^#\s+.*$', '', before)
    return errors, headings, text, before


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('report')
    ap.add_argument('--require', default='', help='Comma-separated words that must each appear in some heading.')
    ap.add_argument('--forbid', default=','.join(DEFAULT_FORBID), help='Comma-separated phrases that must not appear.')
    ap.add_argument('--min-answer-words', type=int, default=20)
    a = ap.parse_args()

    with open(a.report, encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    is_html = a.report.lower().endswith(('.html', '.htm')) or re.search(r'<html[\s>]', text[:2000], re.I)
    errors, headings, visible, before = (check_html if is_html else check_markdown)(text)

    for word in filter(None, (w.strip() for w in a.require.split(','))):
        if not any(word.lower() in h.lower() for h in headings):
            errors.append(f'missing a section heading that contains "{word}"')
    for phrase in filter(None, (p.strip() for p in a.forbid.split(','))):
        if re.search(r'\b' + re.escape(phrase) + r'\b', visible, re.I):
            errors.append(f'method label in the text: "{phrase}" (say the result, not the method)')
    words = len(re.findall(r'\w+', before))
    if words < a.min_answer_words:
        errors.append(f'only {words} words before the first section heading; open with the answer')

    print(f'{a.report}: {"HTML" if is_html else "Markdown"}, {len(headings)} headings')
    for e in errors:
        print('  FAIL', e)
    print('  OK' if not errors else f'  {len(errors)} problem(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
