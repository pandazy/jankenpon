"""Shared test helpers: load a script as a module, build temp trees, run the CLI."""
import contextlib
import importlib.util
import io
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

    Under coverage_report.py (LGR_IN_PROCESS=1) the script runs in this process
    instead, so its lines can be traced."""
    if os.environ.get('LGR_IN_PROCESS') == '1':
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = load(script).main(list(args)) or 0
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, out.getvalue(), err.getvalue()
    p = subprocess.run([sys.executable, '-I', os.path.join(SCRIPTS, script + '.py'), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


class TempTree(unittest.TestCase):
    """A test case with a fresh temp directory and a `write` helper."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='lgr-test-')
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, files):
        for rel, body in files.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(body)
        return self.root

    def path(self, rel):
        return os.path.join(self.root, rel)

    def git(self, *args):
        subprocess.run(['git', '-C', self.root, '-c', 'user.name=t', '-c', 'user.email=t@example.com',
                        '-c', 'commit.gpgsign=false', *args], check=True, capture_output=True)


def has_git():
    return shutil.which('git') is not None
