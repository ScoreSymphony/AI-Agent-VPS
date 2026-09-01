"""Read-only access to the ScoreSymphony component registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPOSITORY_ROOT / "COMPONENTS.yaml"


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("components"), dict):
        raise ValueError(f"Invalid component registry: {path}")
    return data


def component_status(name: str, component: dict[str, Any], root: Path) -> str:
    del name
    if component["bundled"]:
        component_path = root / component["path"]
        return "bundled" if component_path.is_dir() else "missing"
    return "available" if component["enabled"] else "disabled"


def list_components(registry: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rows = []
    for name, component in sorted(registry["components"].items()):
        rows.append(
            {
                "name": name,
                "kind": component["kind"],
                "license": component["license"],
                "status": component_status(name, component, root),
            }
        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("component", nargs="?", help="Show one component")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    registry = load_registry(args.registry)
    root = args.registry.resolve().parent

    if args.component:
        try:
            component = registry["components"][args.component]
        except KeyError:
            raise SystemExit(f"Unknown component: {args.component}") from None
        result = {
            "name": args.component,
            **component,
            "status": component_status(args.component, component, root),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    rows = list_components(registry, root)
    if args.as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(
                f"{row['name']:<16} {row['kind']:<18} "
                f"{row['license']:<12} {row['status']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
