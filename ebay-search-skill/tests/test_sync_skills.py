"""Unit tests for the repo-root tool sync_skills.py (the .dsh skill mirror).

The mirror is a copy of the repo skills, so drift in it silently ships an old
tool to future agent sessions — this happened with windows.py after the ten-night
outage. The tests below pin the drift detection and the copy semantics.

Run from the skill directory:
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_SKILL_DIR)
sys.path.insert(0, _SKILL_DIR)
sys.path.insert(0, _REPO_ROOT)

from _helpers import temp_dir  # noqa: E402
import sync_skills  # noqa: E402

SKILLS = (("skill-a", "a"), ("skill-b", "b"))


def make_repo(root, files_a, files_b):
    """Fabricate a repo root with two skill folders (a, b)."""
    for folder, files in (("skill-a", files_a), ("skill-b", files_b)):
        os.makedirs(os.path.join(root, folder), exist_ok=True)
        for name, body in files.items():
            with open(os.path.join(root, folder, name), "w", encoding="utf-8") as f:
                f.write(body)
    return root


class TestSourceFiles(unittest.TestCase):
    def test_only_python_and_markdown_at_the_top_level(self):
        with temp_dir() as d:
            make_repo(d, {"tool.py": "x", "SKILL.md": "y", "notes.txt": "z"}, {})
            os.makedirs(os.path.join(d, "skill-a", "tests"), exist_ok=True)
            with open(os.path.join(d, "skill-a", "tests", "test_tool.py"), "w") as f:
                f.write("hidden")
            os.makedirs(os.path.join(d, "skill-a", "__pycache__"), exist_ok=True)
            with open(os.path.join(d, "skill-a", "__pycache__", "tool.pyc"), "wb") as f:
                f.write(b"\x00")
            self.assertEqual(
                sync_skills.source_files(os.path.join(d, "skill-a")),
                ["SKILL.md", "tool.py"],
            )

    def test_missing_directory_is_empty(self):
        self.assertEqual(sync_skills.source_files("does-not-exist"), [])


class TestCompare(unittest.TestCase):
    def test_identical_mirror_is_in_sync(self):
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"tool.py": "v1"}, {"SKILL.md": "s"})
            dest = os.path.join(d, "skills")
            sync_skills.sync(repo, dest, skills=SKILLS)
            drift = sync_skills.compare(repo, dest, skills=SKILLS)
            self.assertEqual(drift["missing"], [])
            self.assertEqual(drift["differ"], [])
            self.assertEqual(drift["stale"], [])
            self.assertEqual(drift["in_sync"], 2)

    def test_changed_source_is_reported_as_differing(self):
        # the real-world case: publish/ got the windows.py fix, the mirror did not
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"windows.py": "fixed"}, {})
            dest = os.path.join(d, "skills")
            sync_skills.sync(repo, dest, skills=SKILLS)
            with open(os.path.join(repo, "skill-a", "windows.py"), "w") as f:
                f.write("fixed-again")
            drift = sync_skills.compare(repo, dest, skills=SKILLS)
            self.assertEqual(drift["differ"], ["skill-a/windows.py"])

    def test_missing_and_stale_are_reported(self):
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"new.py": "n"}, {})
            dest = os.path.join(d, "skills")
            os.makedirs(os.path.join(dest, "a"), exist_ok=True)
            with open(os.path.join(dest, "a", "old.py"), "w") as f:
                f.write("o")
            drift = sync_skills.compare(repo, dest, skills=SKILLS)
            self.assertEqual(drift["missing"], ["skill-a/new.py"])
            self.assertEqual(drift["stale"], ["skill-a/old.py"])


class TestSync(unittest.TestCase):
    def test_copies_and_is_idempotent(self):
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"tool.py": "v1"}, {"SKILL.md": "s"})
            dest = os.path.join(d, "skills")
            first = sync_skills.sync(repo, dest, skills=SKILLS)
            self.assertEqual(sorted(first["copied"]), ["skill-a/tool.py", "skill-b/SKILL.md"])
            self.assertTrue(os.path.exists(os.path.join(dest, "a", "tool.py")))
            second = sync_skills.sync(repo, dest, skills=SKILLS)
            self.assertEqual(second["copied"], [])
            self.assertEqual(second["unchanged"], 2)

    def test_prune_removes_orphans_and_caches(self):
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"keep.py": "k"}, {})
            dest = os.path.join(d, "skills")
            os.makedirs(os.path.join(dest, "a", "__pycache__"), exist_ok=True)
            with open(os.path.join(dest, "a", "gone.py"), "w") as f:
                f.write("x")
            with open(os.path.join(dest, "a", "__pycache__", "keep.pyc"), "wb") as f:
                f.write(b"\x00")
            result = sync_skills.sync(repo, dest, skills=SKILLS, prune=True)
            self.assertIn("skill-a/gone.py", result["pruned"])
            self.assertIn("skill-a/__pycache__/", result["pruned"])
            self.assertFalse(os.path.exists(os.path.join(dest, "a", "gone.py")))
            self.assertFalse(os.path.exists(os.path.join(dest, "a", "__pycache__")))


class TestMain(unittest.TestCase):
    def test_check_reports_drift_with_exit_one(self):
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"tool.py": "v1"}, {})
            dest = os.path.join(d, "skills")
            self.assertEqual(
                sync_skills.main(["--repo", repo, "--dest", dest], skills=SKILLS), 0
            )
            with open(os.path.join(repo, "skill-a", "tool.py"), "w") as f:
                f.write("v2")   # same size as v1: the drift a length check misses
            self.assertEqual(
                sync_skills.main(["--repo", repo, "--dest", dest, "--check"],
                                 skills=SKILLS),
                1,
            )
            self.assertEqual(
                sync_skills.main(["--repo", repo, "--dest", dest], skills=SKILLS), 0
            )
            self.assertEqual(
                sync_skills.main(["--repo", repo, "--dest", dest, "--check"],
                                 skills=SKILLS),
                0,
            )

    def test_check_without_a_mirror_is_not_a_failure(self):
        with temp_dir() as d:
            repo = make_repo(os.path.join(d, "repo"), {"tool.py": "v1"}, {})
            self.assertEqual(
                sync_skills.main(
                    ["--repo", repo, "--dest", os.path.join(d, "nope"), "--check"],
                    skills=SKILLS,
                ),
                0,
            )

    def test_missing_repo_root_fails(self):
        with temp_dir() as d:
            self.assertEqual(
                sync_skills.main(["--repo", os.path.join(d, "ghost"), "--dest", d],
                                 skills=SKILLS),
                2,
            )


class TestRealMapping(unittest.TestCase):
    """The mapping itself must keep pointing at the two real skill folders."""

    def test_default_skills_are_the_two_repo_folders(self):
        self.assertEqual(
            [name for name, _ in sync_skills.SKILLS],
            ["ebay-search-skill", "facebook-marketplace-skill"],
        )

    def test_repo_skills_exist_and_expose_their_tools(self):
        files = sync_skills.source_files(
            os.path.join(_REPO_ROOT, "ebay-search-skill")
        )
        for expected in ("SKILL.md", "ebay_search.py", "windows.py", "queries.py",
                         "check_freshness.py", "alert.py"):
            self.assertIn(expected, files)
        fb = sync_skills.source_files(
            os.path.join(_REPO_ROOT, "facebook-marketplace-skill")
        )
        self.assertIn("SKILL.md", fb)
        self.assertIn("fb_marketplace.py", fb)

    def test_default_destination_sits_next_to_the_repo(self):
        self.assertEqual(
            os.path.normpath(sync_skills.DEFAULT_DEST),
            os.path.normpath(os.path.join(_REPO_ROOT, os.pardir, ".dsh", "skills")),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
