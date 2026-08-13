"""Compare an autonomous agent report with a trusted aggregate reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from labs.lab10_pure_python_analytics.dashboard import validate_report


SCALARS = ["total_records", "bytes_sent", "bytes_received", "event_time_min", "event_time_max"]
GROUPS = [
    "top_actions", "top_applications", "top_policies", "top_source_zones",
    "top_destination_zones", "protocols", "session_end_reasons",
]
RANKINGS = [
    ("top_source_talkers", "source_ip"),
    ("top_destination_talkers", "destination_ip"),
    ("traffic_by_source_zone", "source_zone"),
    ("traffic_by_destination_zone", "destination_zone"),
    ("traffic_by_application", "application"),
    ("top_source_users", "source_user"),
]


def _index(rows: list[dict[str, Any]], key: str) -> dict[Any, dict[str, Any]]:
    return {row.get(key): row for row in rows}


def evaluate(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, observed: Any, reference: Any) -> None:
        checks.append({"check": name, "pass": observed == reference, "actual": observed, "expected": reference})

    missing = validate_report(actual)
    checks.append({"check": "analytical_contract", "pass": not missing, "actual": missing, "expected": []})
    for field in SCALARS:
        add(field, actual.get(field), expected.get(field))
    def nonzero_counts(value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {key: count for key, count in value.items() if count != 0}

    add("parse_quality", nonzero_counts(actual.get("parse_quality")), nonzero_counts(expected.get("parse_quality")))

    for group in GROUPS:
        add(group, _index(actual.get(group, []), "value"), _index(expected.get(group, []), "value"))
    for group, key in RANKINGS:
        add(group, _index(actual.get(group, []), key), _index(expected.get(group, []), key))

    for field in ["nat_sessions", "source_nat_sessions", "destination_nat_sessions"]:
        add(f"nat.{field}", actual.get("nat", {}).get(field), expected.get("nat", {}).get(field))
    for group, key in [
        ("top_source_translations", "source_ip"),
        ("top_destination_translations", "destination_ip"),
    ]:
        add(
            f"nat.{group}",
            _index(actual.get("nat", {}).get(group, []), key),
            _index(expected.get("nat", {}).get(group, []), key),
        )

    passed = sum(check["pass"] for check in checks)
    return {
        "passed": passed,
        "total": len(checks),
        "score_percent": round(100 * passed / len(checks), 2),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("actual", type=Path)
    parser.add_argument("expected", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(
        json.loads(args.actual.read_text(encoding="utf-8")),
        json.loads(args.expected.read_text(encoding="utf-8")),
    )
    document = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
    print(f"score={result['passed']}/{result['total']} ({result['score_percent']}%)")
    for check in result["checks"]:
        print(f"[{'PASS' if check['pass'] else 'FAIL'}] {check['check']}")
    raise SystemExit(0 if result["passed"] == result["total"] else 1)


if __name__ == "__main__":
    main()
