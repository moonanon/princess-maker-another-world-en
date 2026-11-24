#!/usr/bin/env python3
"""Build every variant and publish their IPS patches as a GitHub release, with docs/release-notes.md as its text.

    python3 -I tools/rom/release.py v1.0            # tag v1.0 on the pushed HEAD, publish
    python3 -I tools/rom/release.py v1.0 --draft    # a draft release, published by hand on GitHub

Needs the GitHub CLI (`gh`, logged in) and a clean tree whose HEAD is pushed: the tag is made on that commit.
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import VARIANTS, variant_paths  # noqa: E402
from RomExtract import REPO  # noqa: E402

NOTES = REPO / 'docs' / 'release-notes.md'


def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=REPO, check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('tag', help='the release tag, e.g. v1.0')
    ap.add_argument('--draft', action='store_true', help='create a draft release')
    args = ap.parse_args()
    if git('status', '--porcelain', '--untracked-files=no'):
        raise SystemExit('the tree has uncommitted changes: commit them first, the release is built from HEAD')
    head = git('rev-parse', 'HEAD')
    if not git('branch', '-r', '--contains', head):
        raise SystemExit('HEAD is not pushed: push it first, the tag is made on that commit')
    patches = []
    for variant in VARIANTS:
        subprocess.run([sys.executable, '-I', str(HERE / 'build.py'), '--variant', variant], check=True)
        patches.append(str(variant_paths(variant)[1]))
    subprocess.run(['gh', 'release', 'create', args.tag, *patches, '--target', head, '--title', args.tag,
                    '--notes-file', str(NOTES), *(['--draft'] if args.draft else [])], cwd=REPO, check=True)


if __name__ == '__main__':
    main()
