"""textgate try / sample / recheck.

SPEC is "module:name", a textgate.Spec importable from the folder the command runs in.
"""

import argparse
import glob
import importlib
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .check import find_forbidden
from .rules import load_forbid
from .sampling import Spec, recheck, sample


def load_spec(ref: str) -> Spec:
    module, _, name = ref.partition(":")
    if not module or not name:
        raise SystemExit(f"textgate: SPEC must look like module:name, got {ref!r}")
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    spec = getattr(importlib.import_module(module), name, None)
    if not isinstance(spec, Spec):
        raise SystemExit(f"textgate: {ref} is not a textgate.Spec")
    return spec


def expand(patterns: Sequence[str]) -> list[Path]:
    """Windows shells do not expand data/*.jsonl, so do it here."""
    files: list[Path] = []
    for p in patterns:
        hits = sorted(glob.glob(p))
        if not hits and not Path(p).exists():
            raise SystemExit(f"textgate: no file matches {p}")
        files += [Path(h) for h in hits] or [Path(p)]
    return files


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="textgate", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("try", help="show which [[forbid]] patterns of a rule file a sentence hits")
    t.add_argument("rules", type=Path)
    t.add_argument("text", nargs="+")

    s = sub.add_parser("sample", help="ask the real writer for N drafts and summarize the verdicts")
    s.add_argument("spec")
    s.add_argument("-n", type=int, default=10)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", type=Path, default=Path("data"), help="folder, or a .jsonl file (default: data)")

    r = sub.add_parser("recheck", help="judge saved drafts again with today's rules (no API calls)")
    r.add_argument("spec")
    r.add_argument("files", nargs="+")

    args = parser.parse_args(argv)

    if args.command == "try":
        groups = load_forbid(args.rules)
        hit = False
        for text in args.text:
            found = find_forbidden(text, groups)
            hit = hit or bool(found)
            print(f"{text}: {', '.join(found) if found else 'ok'}")
        return 1 if hit else 0

    spec = load_spec(args.spec)
    if args.command == "sample":
        summary = sample(spec, args.n, args.out, seed=args.seed)
        print()
        print("\n".join(summary.lines(spec.price)))
        return 0

    summary, changes = recheck(spec, expand(args.files))
    print("\n".join(summary.lines()))
    print(f"verdict changed: {len(changes)}")
    for c in changes:
        print(f"  {c.where}")
        print(f"    before {c.before}")
        print(f"    after  {c.after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
