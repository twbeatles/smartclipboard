"""Generate a symbol inventory for refactor safety checks."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def _args_from_signature(node: ast.FunctionDef) -> dict:
    args = node.args
    posonly = [a.arg for a in args.posonlyargs]
    regular = [a.arg for a in args.args]
    kwonly = [a.arg for a in args.kwonlyargs]
    return {
        "posonly": posonly,
        "args": regular,
        "vararg": args.vararg.arg if args.vararg else None,
        "kwonly": kwonly,
        "kwarg": args.kwarg.arg if args.kwarg else None,
        "defaults_count": len(args.defaults),
        "kw_defaults_count": sum(1 for x in args.kw_defaults if x is not None),
    }


def build_inventory(path: str | Path) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text)

    classes = []
    top_functions = []
    constants = set()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(
                        {
                            "name": item.name,
                            "signature": _args_from_signature(item),
                        }
                    )
            classes.append({"name": node.name, "methods": methods})
        elif isinstance(node, ast.FunctionDef):
            top_functions.append({"name": node.name, "signature": _args_from_signature(node)})
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.add(target.id)

    classes.sort(key=lambda c: c["name"])
    for c in classes:
        c["methods"].sort(key=lambda m: m["name"])
    top_functions.sort(key=lambda f: f["name"])

    return {
        "file": str(path).replace("\\", "/"),
        "has_main_entry": 'if __name__ == "__main__":' in text,
        "constants": sorted(constants),
        "top_functions": top_functions,
        "classes": classes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="smartclipboard_app/legacy_main_src.py")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    inventory = build_inventory(args.target)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
