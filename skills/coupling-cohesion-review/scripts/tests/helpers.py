"""Shared test helpers: load a script as a module, build temp trees, run the CLI."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    """Import scripts/<name>.py by path (works under `python3 -I`)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(script, *args):
    """Run scripts/<script>.py in isolated mode; return (exit code, stdout, stderr).

    Under coverage_report.py (CCR_IN_PROCESS=1) the script runs in this process
    instead, so its lines can be traced."""
    if os.environ.get('CCR_IN_PROCESS') == '1':
        return _run_in_process(script, args)
    p = subprocess.run([sys.executable, '-I', os.path.join(SCRIPTS, script + '.py'), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def _run_in_process(script, args):
    import contextlib
    import io
    out, err = io.StringIO(), io.StringIO()
    old_argv = sys.argv
    sys.argv = [os.path.join(SCRIPTS, script + '.py'), *args]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = load(script).main() or 0
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = old_argv
    return code, out.getvalue(), err.getvalue()


class TempTree(unittest.TestCase):
    """A test case with a fresh temp directory and a `write` helper."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='ccr-test-')
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, files):
        for rel, text in files.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(text)
        return self.root

    def signals(self, *args, root=None):
        """Run signals.py on the tree and return the parsed JSON results."""
        out = os.path.join(tempfile.mkdtemp(prefix='ccr-json-'), 'signals.json')
        self.addCleanup(shutil.rmtree, os.path.dirname(out), True)
        code, stdout, stderr = run('signals', root or self.root, '--json', out, *args)
        self.assertEqual(code, 0, stderr)
        with open(out, encoding='utf-8') as fh:
            return json.load(fh)

    def git(self, *args):
        subprocess.run(['git', '-C', self.root, '-c', 'user.name=t', '-c', 'user.email=t@example.com',
                        '-c', 'commit.gpgsign=false', *args], check=True, capture_output=True)


def has_git():
    return shutil.which('git') is not None
