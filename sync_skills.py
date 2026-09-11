#!/usr/bin/env python3
"""Mirror this repo's skills into the DSH skill directory — and detect drift.

Why this exists
---------------
The agent-facing skills under `.dsh/skills/` are a *mirror* of the two skill
folders in this repo:

    ebay-search-skill/          -> <dest>/ebay-search/
    facebook-marketplace-skill/ -> <dest>/facebook-marketplace/

That mirror drifted once already: when the CWD-dependent
`window_for_query(q, None)` bug was fixed in `publish/`, the copy in
`.dsh/skills/ebay-search/windows.py` still had the old code — the very file
that had frozen the dataset for ten nights — so a future session would have
re-introduced it. Hand-editing two copies of the same tool is the bug; this
script makes the mirror derived.

Usage (from the repo root):
    python sync_skills.py                 # copy repo -> <dest>
    python sync_skills.py --check         # 0 = in sync, 1 = drift (for CI/hooks)
    python sync_skills.py --prune         # also delete mirror files with no source
    python sync_skills.py --dest D        # mirror somewhere else

Only top-level `*.py` and `*.md` files are mirrored: no `tests/`, no
`__pycache__`, no generated data. `--prune` additionally removes those
caches from the mirror.

The destination defaults to `../.dsh/skills` **relative to this file**, never
relative to the working directory — the whole point of this guard is to stop
depending on where a process happens to be started.
"""

import argparse
import hashlib
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEST = os.path.normpath(os.path.join(REPO_ROOT, os.pardir, ".dsh", "skills"))

# (source folder in the repo, folder name in the skill root)
SKILLS = (
    ("ebay-search-skill", "ebay-search"),
    ("facebook-marketplace-skill", "facebook-marketplace"),
)
MIRRORED_SUFFIXES = (".py", ".md")
CACHE_DIR = "__pycache__"


def source_files(src_dir):
    """Top-level *.py/*.md names in `src_dir` (sorted); [] when it is absent."""
    if not os.path.isdir(src_dir):
        return []
    return sorted(
        name
        for name in os.listdir(src_dir)
        if name.endswith(MIRRORED_SUFFIXES)
        and os.path.isfile(os.path.join(src_dir, name))
    )


def digest(path):
    """sha256 of a file's bytes.

    Deliberately NOT `filecmp.cmp`: its (size, mtime) signature cache can
    report a same-size rewrite as identical, which is exactly the drift this
    guard exists to catch (a one-character fix in a mirrored .py file).
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def skill_pairs(repo_root=REPO_ROOT, dest_root=DEFAULT_DEST, skills=SKILLS):
    """[(source dir, destination dir), ...] for every mirrored skill."""
    return [
        (os.path.join(repo_root, src_name), os.path.join(dest_root, dest_name))
        for src_name, dest_name in skills
    ]


def compare(repo_root=REPO_ROOT, dest_root=DEFAULT_DEST, skills=SKILLS):
    """Drift between repo and mirror.

    -> {"missing": [rel], "differ": [rel], "stale": [rel], "in_sync": n}
    `missing` = in the repo, absent from the mirror; `differ` = different
    content; `stale` = only in the mirror (a source that was deleted/renamed).
    """
    missing, differ, stale = [], [], []
    in_sync = 0
    for src_dir, dest_dir in skill_pairs(repo_root, dest_root, skills):
        label = os.path.basename(src_dir)
        expected = set(source_files(src_dir))
        for name in sorted(expected):
            dest = os.path.join(dest_dir, name)
            rel = f"{label}/{name}"
            if not os.path.exists(dest):
                missing.append(rel)
            elif digest(os.path.join(src_dir, name)) != digest(dest):
                differ.append(rel)
            else:
                in_sync += 1
        for name in source_files(dest_dir):
            if name not in expected:
                stale.append(f"{label}/{name}")
    return {"missing": missing, "differ": differ, "stale": stale, "in_sync": in_sync}


def sync(repo_root=REPO_ROOT, dest_root=DEFAULT_DEST, skills=SKILLS, prune=False):
    """Copy repo -> mirror. -> {"copied": [rel], "pruned": [rel], "unchanged": n}."""
    copied, pruned, unchanged = [], [], 0
    for src_dir, dest_dir in skill_pairs(repo_root, dest_root, skills):
        label = os.path.basename(src_dir)
        expected = set(source_files(src_dir))
        if not expected:
            continue
        os.makedirs(dest_dir, exist_ok=True)
        for name in sorted(expected):
            src = os.path.join(src_dir, name)
            dest = os.path.join(dest_dir, name)
            if os.path.exists(dest) and digest(src) == digest(dest):
                unchanged += 1
                continue
            shutil.copy2(src, dest)
            copied.append(f"{label}/{name}")
        if prune:
            for name in source_files(dest_dir):
                if name not in expected:
                    os.remove(os.path.join(dest_dir, name))
                    pruned.append(f"{label}/{name}")
            cache = os.path.join(dest_dir, CACHE_DIR)
            if os.path.isdir(cache):
                shutil.rmtree(cache, ignore_errors=True)
                pruned.append(f"{label}/{CACHE_DIR}/")
    return {"copied": copied, "pruned": pruned, "unchanged": unchanged}


def main(argv=None, skills=SKILLS):
    """CLI entry point (returns an exit code). `skills` is injectable for tests."""
    ap = argparse.ArgumentParser(
        description="Mirror the repo skills into the DSH skill directory"
    )
    ap.add_argument("--repo", default=REPO_ROOT,
                    help=f"repo root holding the skill folders (default: {REPO_ROOT})")
    ap.add_argument("--dest", default=None,
                    help=f"skill root to write (default: {DEFAULT_DEST})")
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 instead of copying anything")
    ap.add_argument("--prune", action="store_true",
                    help="also delete mirror files that have no source anymore")
    args = ap.parse_args(argv)

    repo = os.path.abspath(args.repo)
    dest = os.path.abspath(args.dest) if args.dest else os.path.normpath(
        os.path.join(repo, os.pardir, ".dsh", "skills")
    )

    if args.check:
        drift = compare(repo, dest, skills=skills)
        if not os.path.isdir(dest):
            print(f"no skill mirror at {dest} — nothing to check (run without --check to create it)")
            return 0
        for kind in ("missing", "differ", "stale"):
            for rel in drift[kind]:
                print(f"{kind.upper():8} {rel}")
        if drift["missing"] or drift["differ"] or drift["stale"]:
            print(f"\nDRIFT: {len(drift['missing'])} missing, {len(drift['differ'])} "
                  f"differing, {len(drift['stale'])} stale — run: python sync_skills.py")
            return 1
        print(f"skills in sync ({drift['in_sync']} files) — {dest}")
        return 0

    if not os.path.isdir(repo):
        print(f"ERROR: no such repo root: {repo}")
        return 2
    result = sync(repo, dest, skills=skills, prune=args.prune)
    for rel in result["copied"]:
        print(f"COPIED   {rel}")
    for rel in result["pruned"]:
        print(f"PRUNED   {rel}")
    print(f"skill mirror updated: {len(result['copied'])} copied, "
          f"{result['unchanged']} unchanged, {len(result['pruned'])} pruned — {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
