#!/usr/bin/env python3
"""Line coverage of the skill's scripts by their tests. Standard library only.

Runs every test in this folder in one process under a line tracer, then
reports, per script, which executable lines ran. Tests that normally start
the script as a subprocess run it in-process here, so those lines count too.

Usage:
  python3 -I coverage_report.py [--fail-under PCT] [--no-missing]

Line coverage only (not branch coverage). A line counts as executable when
Python's compiler emits code for it, which includes docstrings and
signatures of functions that are defined but never called.
"""
import argparse
import dis
import os
import sys
import threading
import types
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(TESTS)
TARGETS = {os.path.join(SCRIPTS, n) for n in sorted(os.listdir(SCRIPTS)) if n.endswith('.py')}


def executable_lines(path):
    with open(path, encoding='utf-8') as fh:
        code = compile(fh.read(), path, 'exec')
    lines, todo = set(), [code]
    while todo:
        c = todo.pop()
        lines.update(ln for _, ln in dis.findlinestarts(c) if ln)
        todo.extend(k for k in c.co_consts if isinstance(k, types.CodeType))
    return lines


def ranges(nums):
    out, nums = [], sorted(nums)
    for n in nums:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ', '.join(str(a) if a == b else f'{a}-{b}' for a, b in out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fail-under', type=float, default=0)
    ap.add_argument('--no-missing', action='store_true', help='Do not list the missing line numbers.')
    a = ap.parse_args()

    hits = {t: set() for t in TARGETS}

    def tracer(frame, event, arg):
        f = frame.f_code.co_filename
        if f not in hits:
            return None
        if event in ('call', 'line'):
            hits[f].add(frame.f_lineno)
        return tracer

    os.environ['CCR_IN_PROCESS'] = '1'
    sys.path.insert(0, TESTS)
    threading.settrace(tracer)
    sys.settrace(tracer)  # before discovery, so module-level lines run at import are counted
    try:
        suite = unittest.defaultTestLoader.discover(TESTS, top_level_dir=TESTS)
        result = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w')).run(suite)
    finally:
        sys.settrace(None)
        threading.settrace(None)

    print(f'tests: {result.testsRun} run, {len(result.failures)} failed, {len(result.errors)} errors, '
          f'{len(result.skipped)} skipped')
    total_exec = total_hit = 0
    print(f'{"script":<20}{"lines":>7}{"run":>7}{"cover":>8}')
    for t in sorted(TARGETS):
        ex = executable_lines(t)
        hit = hits[t] & ex
        total_exec += len(ex)
        total_hit += len(hit)
        pct = 100.0 * len(hit) / len(ex) if ex else 100.0
        print(f'{os.path.basename(t):<20}{len(ex):>7}{len(hit):>7}{pct:>7.1f}%')
        if not a.no_missing and ex - hit:
            print(f'  missing: {ranges(ex - hit)}')
    pct = 100.0 * total_hit / total_exec if total_exec else 100.0
    print(f'{"TOTAL":<20}{total_exec:>7}{total_hit:>7}{pct:>7.1f}%')

    if not result.wasSuccessful():
        return 1
    if pct < a.fail_under:
        print(f'coverage {pct:.1f}% is under --fail-under {a.fail_under}%')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
