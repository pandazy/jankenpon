"""Tests for check_report.py. Run: python3 -I -m unittest discover -s <scripts>/tests -t <scripts>/tests"""
import unittest

from helpers import TempTree, load, run

C = load('check_report')

ANSWER = '<p>The code is mostly healthy. Two spots need work, and one small change fixes the worst of them today at low cost.</p>'
GOOD_HTML = f"""<!doctype html><html><head><title>r</title><style>.x {{ content: "Layer B" }}</style></head><body>
<h1>Review</h1>{ANSWER}
<h2>Red</h2><p>One item<ul><li>open li<li>second</ul>
<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody>
<tr><td>1</td><td>2</td></tr><tr><td colspan="2">wide</td></tr></tbody></table>
<h2>Green</h2><img src="c.png" alt="chart"><a href="https://example.com">link</a><br>
</body></html>"""
GOOD_MD = """# Review

The code is mostly healthy. Two spots need work, and one small change fixes the worst of them today at low cost.

## Red

| a | b |
|---|---|
| 1 | x \\| y |

```
| not | a | table |
```

## Green
"""


def html_errors(body):
    return C.check_html(body)[0]


class Html(unittest.TestCase):
    def test_good_report_has_no_errors(self):
        errors, headings, _, before = C.check_html(GOOD_HTML)
        self.assertEqual(errors, [])
        self.assertEqual(headings, ['Review', 'Red', 'Green'])
        self.assertIn('mostly healthy', before)

    def test_each_failure(self):
        cases = {
            '<div id="x"></div><span id="x"></span>': 'duplicate id "x"',
            '<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>':
                'table row has 1 cells, header has 2',
            '<img src="a.png">': 'without alt text',
            '<a href="#">x</a>': 'empty href',
            '<h3> </h3>': 'empty <h3>',
            '<section><div></section>': '<div> is not closed before </section>',
            '<p>x</p></div>': '</div> has no matching open tag',
            '<main><span>x</main>': '<span> is not closed',
            '<div>never closed': '<div> is never closed',
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                errors = html_errors(body)
                self.assertTrue(any(expected in e for e in errors), errors)

    def test_self_closing_tags(self):
        self.assertEqual(html_errors('<div><br/><span/><img src="a" alt="a"/></div>'), [])
        self.assertEqual(html_errors('<p>a<br></br></p>'), [])  # a stray end tag on a void element is harmless

    def test_table_without_thead_uses_first_row(self):
        self.assertEqual(html_errors('<table><tr><td>1</td><td>2</td></tr><tr><td>3</td><td>4</td></tr></table>'), [])
        self.assertTrue(html_errors('<table><tr><td>1</td><td>2</td></tr><tr><td>3</td></tr></table>'))

    def test_error_reports_line_number(self):
        errors = html_errors('<p>a</p>\n<p>b</p>\n<img src="x">')
        self.assertTrue(errors[0].startswith('line 3:'), errors)


class Markdown(unittest.TestCase):
    def test_good_report(self):
        errors, headings, _, before = C.check_markdown(GOOD_MD)
        self.assertEqual(errors, [])
        self.assertEqual(headings, ['Review', 'Red', 'Green'])
        self.assertIn('mostly healthy', before)
        self.assertNotIn('Review', before)

    def test_bad_row(self):
        errors = C.check_markdown('## T\n\n| a | b |\n|---|---|\n| 1 |\n')[0]
        self.assertEqual(errors, ['line 5: table row has 1 columns, header has 2'])

    def test_heading_inside_code_block_ignored(self):
        _, headings, _, _ = C.check_markdown('# A\n```\n## not a heading\n```\n## B\n')
        self.assertEqual(headings, ['A', 'B'])


class Cli(TempTree):
    def check(self, name, text, *args):
        self.write({name: text})
        return run('check_report', f'{self.root}/{name}', *args)

    def test_pass_exits_zero(self):
        for name, text in [('r.html', GOOD_HTML), ('r.md', GOOD_MD)]:
            with self.subTest(name=name):
                code, out, _ = self.check(name, text, '--require', 'Red,Green')
                self.assertEqual(code, 0, out)
                self.assertIn('OK', out)

    def test_missing_section(self):
        code, out, _ = self.check('r.html', GOOD_HTML, '--require', 'Red,Limits')
        self.assertEqual(code, 1)
        self.assertIn('missing a section heading that contains "Limits"', out)

    def test_method_label_in_visible_text(self):
        # The same phrase inside <style> above is ignored; in visible text it fails.
        code, out, _ = self.check('r.html', GOOD_HTML.replace('One item', 'Per Layer B, one item'))
        self.assertEqual(code, 1)
        self.assertIn('"Layer B"', out)

    def test_forbid_replaces_default_list(self):
        text = GOOD_MD.replace('## Green', '## Green\n\nThis uses the Feynman way and is synergy-driven.')
        code, out, _ = self.check('r.md', text, '--forbid', 'synergy')
        self.assertEqual(code, 1)
        self.assertIn('"synergy"', out)
        self.assertNotIn('Feynman', out)

    def test_answer_first(self):
        text = '# Review\n\nShort.\n\n## Red\n'
        code, out, _ = self.check('r.md', text)
        self.assertEqual(code, 1)
        self.assertIn('open with the answer', out)
        code, out, _ = self.check('r.md', text, '--min-answer-words', '0')
        self.assertEqual(code, 0, out)

    def test_format_detected_from_content(self):
        code, out, _ = self.check('report.txt', GOOD_HTML)
        self.assertEqual(code, 0, out)
        self.assertIn(': HTML,', out)


if __name__ == '__main__':
    unittest.main()
