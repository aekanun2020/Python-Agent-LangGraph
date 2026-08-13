import ast
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from labs.lab10_pure_python_analytics.agent_security_analytics import ModelDeadline
from labs.lab10_pure_python_analytics.dashboard import render_dashboard, validate_report
from labs.lab10_pure_python_analytics.evaluate_report import evaluate


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "labs" / "lab10_pure_python_analytics" / "agent_security_analytics.py"


def sample_report():
    traffic = {"sessions": 1, "bytes_sent": 10, "bytes_received": 20, "total_bytes": 30}
    return {
        "parser": {"id": "p", "version": "1", "vendor": "v", "product": "x", "log_type": "traffic"},
        "total_records": 1, "parse_quality": {"parsed": 1}, "event_time_min": "a", "event_time_max": "b",
        "bytes_sent": 10, "bytes_received": 20,
        "top_actions": [{"value": "allow", "count": 1}],
        "top_applications": [{"value": "ssl", "count": 1}],
        "top_policies": [{"value": "allow-web", "count": 1}],
        "top_source_zones": [{"value": "trust", "count": 1}],
        "top_destination_zones": [{"value": "untrust", "count": 1}],
        "protocols": [{"value": "tcp", "count": 1}],
        "top_source_talkers": [{"source_ip": "10.0.0.1", **traffic}],
        "top_destination_talkers": [{"destination_ip": "10.0.0.2", **traffic}],
        "traffic_by_source_zone": [{"source_zone": "trust", **traffic}],
        "traffic_by_destination_zone": [{"destination_zone": "untrust", **traffic}],
        "traffic_by_application": [{"application": "ssl", **traffic}],
        "session_end_reasons": [{"value": "aged-out", "count": 1}],
        "top_source_users": [],
        "nat": {"nat_sessions": 0, "source_nat_sessions": 0, "destination_nat_sessions": 0,
                "top_source_translations": [], "top_destination_translations": []},
    }


class PurePythonAgentTests(unittest.TestCase):
    def test_agent_does_not_import_langgraph_or_langchain(self):
        tree = ast.parse(AGENT.read_text(encoding="utf-8"))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertFalse([name for name in imported if name.startswith(("langgraph", "langchain"))])

    def test_dashboard_contract_and_render(self):
        report = sample_report()
        self.assertEqual(validate_report(report), [])
        with tempfile.TemporaryDirectory() as tmp:
            target = render_dashboard(report, Path(tmp) / "dashboard.html")
            text = target.read_text(encoding="utf-8")
            self.assertIn("Pure Python Agent", text)
            self.assertIn('"total_records":1', text)

    def test_evaluator_accepts_identical_report(self):
        report = sample_report()
        result = evaluate(report, json.loads(json.dumps(report)))
        self.assertEqual(result["passed"], result["total"])
        self.assertEqual(result["score_percent"], 100.0)

    def test_panos_semantic_guard_rejects_shifted_columns(self):
        report = sample_report()
        report["parser"]["id"] = "paloalto-panos-11x-traffic"
        report["top_actions"] = [{"value": "tcp", "count": 1}]
        report["protocols"] = [{"value": "ssl", "count": 1}]
        problems = validate_report(report)
        self.assertTrue(any("non-action" in item for item in problems))
        self.assertTrue(any("non-protocol" in item for item in problems))

    def test_report_rejects_null_dimension(self):
        report = sample_report()
        report["top_applications"] = [{"value": None, "count": 1}]
        self.assertTrue(any("top_applications.value" in item for item in validate_report(report)))

    def test_zip_fixture_is_readable_without_path_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sample.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("nested/vendor.log", "header,TRAFFIC,event\n")
            with zipfile.ZipFile(archive) as stream:
                member = max((item for item in stream.infolist() if not item.is_dir()), key=lambda x: x.file_size)
                self.assertEqual(stream.open(member).readline(), b"header,TRAFFIC,event\n")

    def test_model_deadline_disabled_is_safe(self):
        with ModelDeadline(0):
            value = 42
        self.assertEqual(value, 42)


if __name__ == "__main__":
    unittest.main()
