"""Shared helpers for the skill unit tests."""

import os
import shutil
import uuid

# Sandbox-safe temp root: the DSH sandbox blocks writes to the OS temp dir,
# so tests create temp dirs under the tests folder itself (workspace-local).
# Works everywhere else too (CI, local machines) since the repo is writable.
#
# NOTE: `tempfile.mkdtemp`/`TemporaryDirectory` are deliberately NOT used —
# the DSH sandbox denies file creation inside directories those functions
# create (their restricted 0o700 perms trip the sandbox), while plain
# os.makedirs-created dirs are fine. Names are unique per call via uuid.
_TMP_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp")


class _TempDir:
    """Context manager over a workspace-local temp dir (plain rmtree cleanup)."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)
        return False


def temp_dir():
    """Context manager yielding a fresh workspace-local temp directory."""
    os.makedirs(_TMP_ROOT, exist_ok=True)
    path = os.path.join(_TMP_ROOT, uuid.uuid4().hex[:12])
    os.makedirs(path)
    return _TempDir(path)
