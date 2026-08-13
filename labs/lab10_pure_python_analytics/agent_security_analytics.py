"""Autonomous security-log analytics agent implemented with a plain Python loop.

This module intentionally does not import LangGraph or LangChain.  The model owns
the workflow: it selects tools, writes the PySpark application, submits it, checks
the result, and materializes a dashboard through bounded local/MCP tools.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from labs.core import config, llm  # noqa: E402
from labs.core.registry import ToolRegistry  # noqa: E402
from labs.lab10_pure_python_analytics.dashboard import (  # noqa: E402
    render_dashboard,
    validate_report,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS = ROOT / "artifacts" / "lab10_security_agent"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

ANALYTICAL_CONTRACT = """
The PySpark report is one JSON object and MUST contain:
- parser: id, version, vendor, product, log_type
- total_records, parse_quality, event_time_min, event_time_max, bytes_sent, bytes_received
- top_actions, top_applications, top_policies, top_source_zones,
  top_destination_zones, protocols (each item has value and count)
- top_source_talkers and top_destination_talkers
- traffic_by_source_zone, traffic_by_destination_zone, traffic_by_application
  (traffic rankings contain sessions, bytes_sent, bytes_received, total_bytes)
- session_end_reasons
- top_source_users ranked by sessions, excluding null/blank users
- nat containing nat_sessions, source_nat_sessions, destination_nat_sessions,
  top_source_translations, top_destination_translations

NAT is observed only when a translated IP is non-null, not 0.0.0.0, and differs
from the original IP, OR the translated port is non-null/non-zero and differs from
the original port. Write normalized events as Parquet and the report with
coalesce(1).write.mode("overwrite").text(REPORT_PATH). Never collect raw events.

Parser correctness rules:
- Treat parser.mapping keys as exact zero-based raw CSV column indexes. Never
  subtract one from a mapping key. For this csv_syslog format, c1 is event_time,
  c3 is log_type, c7 is source_ip, and so on exactly as the Skill MCP returns.
- Use pyspark.sql.functions.from_csv with a sufficiently wide DDL and the parser's
  delimiter/quotechar. Do not use split(value, ',') because quoted CSV is valid.
- parse_quality must be a dictionary of status counts such as {"parsed": 100000},
  not a percentage or scalar. A parsed row satisfies required_output.
- Ranking rows must preserve their contract-specific dimension names (source_ip,
  destination_ip, source_zone, destination_zone, application, source_user) rather
  than replacing them with a generic value key.

Use this exact parsing shape for csv_syslog. It prevents the common off-by-one
error caused by giving the first CSV field the name of mapping index 1:
  ddl = ",".join(f"c{{i}} STRING" for i in range(column_count))
  parsed = raw.select(F.from_csv(F.col("value"), ddl, csv_options).alias("csv"))
  events = parsed.select(
      F.col("csv.c1").alias("event_time"),
      F.col("csv.c3").alias("log_type"),
      ... every remaining output field from the exact Skill mapping ...
  )
There MUST be a c0 placeholder even when no normalized field uses c0. Never make
a StructType whose first field is event_time: that shifts every field left.

Use top 10 for normal dimensions/talkers, top 20 for session_end_reasons and
top_source_users, and top 20 for each NAT translation ranking. Rank traffic tables
by total_bytes descending with a stable ascending dimension tie-breaker.

Cast timestamp, integer, and long fields according to each parser.mapping type
before aggregation. total_records is the raw input count; parse_quality is computed
from required_output and its counts must sum to total_records. Do not filter failed
or partial rows out before measuring parse quality.

Never ask Spark to infer the nested Python report dictionary. Serialize it first:
  report_json = json.dumps(report, default=str, sort_keys=True)
  spark.createDataFrame([(report_json,)], ["value"]).coalesce(1) \
      .write.mode("overwrite").text(REPORT_PATH)
Writing a DataFrame made directly from [report], writing an RDD, or calling
DataFrame.write.text on a multi-column DataFrame is invalid for this report.
""".strip()

SYSTEM = f"""
You are a senior security data engineer operating an Apache Spark/HDFS batch
analytics environment. You are an autonomous ReAct agent implemented in Pure
Python; there is no LangGraph runtime.

Complete the user's request end-to-end. Mandatory workflow:
1. For a multi-step request, create a todo list and keep its statuses current.
2. Call prepare_input_archive exactly once. Raw sample inspection and vendor
   detection happen locally inside that bounded tool so raw log text is never sent
   to the external LLM. Use its skill_resolution metadata, then obtain the complete
   skill and parser definition with log_skill_get.
3. Import the prepared source_name into HDFS with hdfs_import_file at
   /security-agent/input/events.log using overwrite=true.
4. Inspect Spark and HDFS cluster status.
5. Generate a complete, standalone PySpark program yourself. Save it as
   pure_python_security_analysis.py with spark_save_job(overwrite=true), validate,
   and submit it. Pass these three arguments in order:
   hdfs://namenode:9000/mcp/security-agent/input/events.log
   hdfs://namenode:9000/mcp/security-agent/curated
   hdfs://namenode:9000/mcp/security-agent/report
   The job must read these from sys.argv[1], sys.argv[2], sys.argv[3]; do not
   hardcode a different HDFS RPC port.
6. Call wait_for_spark_job. If the job fails, inspect logs, repair the code, and
   resubmit. Use spark_read_job plus spark_replace_job_text for a small repair when
   possible instead of rewriting the complete file. Do not mark a failed job done
   and do not claim success from a RUNNING job.
7. Call collect_security_report with /security-agent/report. This validates the
   analytical contract and creates JSON plus an HTML dashboard on the host.
8. Give an executive security summary citing actual aggregate values and the
   generated artifact paths. Never expose raw log lines in the final answer.

Use the parser returned by Security Skill MCP; do not guess column positions.
The generated Spark job must satisfy this analytical contract:
{ANALYTICAL_CONTRACT}

Safety: operate only on the fixed /security-agent HDFS subtree and the authorized
input archive. Do not delete HDFS, cancel unrelated jobs, or write drafts.
""".strip()


def _json_result(value: str) -> Any:
    """Decode the normal FastMCP text result while tolerating plain text."""
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


class ModelDeadline:
    """POSIX hard deadline around one model turn; a no-op on unsupported hosts."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self.enabled = hasattr(signal, "SIGALRM") and seconds > 0
        self.previous: Any = None

    def __enter__(self) -> None:
        if self.enabled:
            self.previous = signal.signal(signal.SIGALRM, self._expired)
            signal.alarm(self.seconds)

    def __exit__(self, *_: Any) -> None:
        if self.enabled:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, self.previous)

    @staticmethod
    def _expired(_signum: int, _frame: Any) -> None:
        raise TimeoutError("model turn exceeded the configured hard deadline")


@dataclass
class LocalTool:
    schema: dict[str, Any]
    handler: Callable[..., Any]


class TodoState:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def write(self, items: list[str]) -> dict[str, Any]:
        self.items = [
            {"index": index, "task": task, "status": "todo"}
            for index, task in enumerate(items, 1)
        ]
        return {"items": self.items}

    def update(self, index: int, status: str) -> dict[str, Any]:
        for item in self.items:
            if item["index"] == index:
                item["status"] = status
                return {"updated": True, "items": self.items}
        return {"updated": False, "error": f"todo index does not exist: {index}", "items": self.items}


class RunTrace:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.path.write_text("", encoding="utf-8")

    def add(self, event: str, **payload: Any) -> None:
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class SecurityAnalyticsTools:
    """Combined MCP registry plus narrowly-scoped host tools."""

    def __init__(
        self,
        archive: Path,
        artifacts: Path,
        container: str,
        spark_mcp_url: str,
        skills_mcp_url: str,
        trace: RunTrace,
    ) -> None:
        self.archive = archive.resolve()
        self.artifacts = artifacts.resolve()
        self.container = container
        self.trace = trace
        self.todo = TodoState()
        self.report_collected = False
        self.report_summary: dict[str, Any] | None = None
        self.registry = ToolRegistry()
        self.registry.add_server(spark_mcp_url)
        self.registry.add_server(skills_mcp_url)
        self.local: dict[str, LocalTool] = {}
        self._register_local_tools()

    def _add(self, name: str, description: str, parameters: dict[str, Any], handler: Callable[..., Any]) -> None:
        self.local[name] = LocalTool(
            schema={"type": "function", "function": {"name": name, "description": description, "parameters": parameters}},
            handler=handler,
        )

    def _register_local_tools(self) -> None:
        self._add(
            "todo_write",
            "Create or replace the execution plan for this multi-step task.",
            {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "string"}}}, "required": ["items"]},
            self.todo.write,
        )
        self._add(
            "todo_update",
            "Update one 1-based todo item status.",
            {"type": "object", "properties": {"index": {"type": "integer", "minimum": 1}, "status": {"type": "string", "enum": ["todo", "doing", "done"]}}, "required": ["index", "status"]},
            self.todo.update,
        )
        self._add(
            "prepare_input_archive",
            "Inspect the authorized ZIP/plain log, detect its vendor locally through Skill MCP without disclosing raw events to the LLM, and stage one safe log member in Spark MCP /imports.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            self.prepare_input_archive,
        )
        self._add(
            "wait_for_spark_job",
            "Poll an MCP-submitted Spark job until SUCCEEDED/FAILED or timeout; includes failure logs.",
            {"type": "object", "properties": {"job_id": {"type": "string"}, "timeout_seconds": {"type": "integer", "minimum": 10, "maximum": 900, "default": 300}}, "required": ["job_id"]},
            self.wait_for_spark_job,
        )
        self._add(
            "collect_security_report",
            "Read the Spark JSON report directory from HDFS, enforce the analytical contract, and create local JSON and HTML dashboard artifacts.",
            {"type": "object", "properties": {"report_path": {"type": "string", "enum": ["/security-agent/report"]}}, "required": ["report_path"]},
            self.collect_security_report,
        )

    @property
    def openai_tools(self) -> list[dict[str, Any]]:
        return self.registry.openai_tools + [tool.schema for tool in self.local.values()]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        self.trace.add("tool_start", tool=name, arguments=arguments)
        try:
            if name in self.local:
                result = self.local[name].handler(**arguments)
                text = json.dumps(result, ensure_ascii=False, default=str)
            else:
                text = self.registry.dispatch(name, arguments)
            self.trace.add("tool_end", tool=name, result_preview=text[:2_000])
            return text
        except Exception as exc:  # return failures to the model so it can repair its plan
            error = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
            self.trace.add("tool_error", tool=name, **error)
            return json.dumps(error, ensure_ascii=False)

    def prepare_input_archive(self) -> dict[str, Any]:
        if not self.archive.is_file():
            raise FileNotFoundError(f"input archive not found: {self.archive}")
        if not SAFE_NAME.fullmatch(self.container):
            raise ValueError("unsafe Docker container name")

        target_name = "agent-security-input.log"
        with tempfile.TemporaryDirectory(prefix="pure-python-security-agent-") as tmp:
            extracted = Path(tmp) / target_name
            member_name = self.archive.name
            if zipfile.is_zipfile(self.archive):
                with zipfile.ZipFile(self.archive) as archive:
                    candidates = [item for item in archive.infolist() if not item.is_dir() and not (item.flag_bits & 1)]
                    if not candidates:
                        raise ValueError("ZIP has no readable unencrypted file")
                    member = max(candidates, key=lambda item: item.file_size)
                    if member.file_size > 10 * 1024**3:
                        raise ValueError("ZIP member exceeds the 10 GiB safety limit")
                    member_name = member.filename
                    with archive.open(member) as source, extracted.open("wb") as output:
                        while chunk := source.read(1024 * 1024):
                            output.write(chunk)
            else:
                with self.archive.open("rb") as source, extracted.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)

            with extracted.open("rb") as stream:
                sample = stream.readline(16_384).decode("utf-8", errors="replace").strip()[:8_000]
            if not sample:
                raise ValueError("input log is empty")
            destination = f"{self.container}:/imports/{target_name}"
            process = subprocess.run(
                ["docker", "cp", str(extracted), destination],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if process.returncode:
                raise RuntimeError((process.stderr or process.stdout).strip())
            size = extracted.stat().st_size

        resolution = _json_result(self.registry.dispatch("log_skill_resolve", {"sample": sample}))
        if not isinstance(resolution, dict):
            raise RuntimeError(f"unexpected local skill resolution: {resolution}")

        return {
            "ok": True,
            "archive": str(self.archive),
            "archive_member": member_name,
            "source_name": target_name,
            "uncompressed_bytes": size,
            "skill_resolution": resolution,
            "privacy": "raw sample remained local and was not returned to the LLM",
        }

    def wait_for_spark_job(self, job_id: str, timeout_seconds: int = 300) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last: Any = None
        while time.monotonic() < deadline:
            last = _json_result(self.registry.dispatch("spark_job_status", {"job_id": job_id}))
            status = last.get("status") if isinstance(last, dict) else None
            if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                result = {"ok": status == "SUCCEEDED", "job": last}
                if status != "SUCCEEDED":
                    result["logs"] = _json_result(
                        self.registry.dispatch("spark_job_logs", {"job_id": job_id, "tail_lines": 200})
                    )
                return result
            time.sleep(2)
        return {"ok": False, "error": "timeout", "last_status": last}

    def collect_security_report(self, report_path: str) -> dict[str, Any]:
        if report_path != "/security-agent/report":
            raise ValueError("report_path is outside the authorized subtree")
        listing = _json_result(self.registry.dispatch("hdfs_list", {"path": report_path}))
        if not isinstance(listing, list):
            raise RuntimeError(f"unexpected hdfs_list result: {listing}")
        parts = [item["pathSuffix"] for item in listing if item.get("type") == "FILE" and item.get("pathSuffix", "").startswith("part-")]
        if len(parts) != 1:
            raise RuntimeError(f"expected one Spark report part, found {parts}")
        payload = _json_result(
            self.registry.dispatch("hdfs_read_text", {"path": f"{report_path}/{parts[0]}", "max_bytes": 1_048_576})
        )
        if not isinstance(payload, dict) or "text" not in payload:
            raise RuntimeError(f"unexpected hdfs_read_text result: {payload}")
        data = json.loads(payload["text"].strip())
        missing = validate_report(data)
        if missing:
            return {"ok": False, "missing_fields": missing, "instruction": "repair and rerun the Spark job"}

        self.artifacts.mkdir(parents=True, exist_ok=True)
        report_file = self.artifacts / "security-report.json"
        dashboard_file = self.artifacts / "security-dashboard.html"
        report_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        render_dashboard(data, dashboard_file)
        deny_drop = sum(item.get("count", 0) for item in data["top_actions"] if item.get("value") in {"deny", "drop"})
        result = {
            "ok": True,
            "report_file": str(report_file),
            "dashboard_file": str(dashboard_file),
            "total_records": data["total_records"],
            "parse_quality": data["parse_quality"],
            "bytes_total": (data.get("bytes_sent") or 0) + (data.get("bytes_received") or 0),
            "deny_drop_sessions": deny_drop,
            "top_source_talker": (data.get("top_source_talkers") or [None])[0],
            "top_destination_talker": (data.get("top_destination_talkers") or [None])[0],
            "nat_sessions": data["nat"]["nat_sessions"],
            "top_source_users": data.get("top_source_users", [])[:5],
        }
        self.report_collected = True
        self.report_summary = result
        return result

    def close(self) -> None:
        self.registry.close()


def run_agent(question: str, tools: SecurityAnalyticsTools, trace: RunTrace, max_steps: int = 48) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    for step in range(1, max_steps + 1):
        trace.add("model_start", step=step, message_count=len(messages))
        hard_timeout = int(os.getenv("AGENT_HARD_LLM_TIMEOUT_SECONDS", "360"))
        try:
            with ModelDeadline(hard_timeout):
                response = llm.chat(
                    messages=messages,
                    tools=tools.openai_tools,
                    temperature=0,
                    max_tokens=16_000,
                    timeout=float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "300")),
                )
        except Exception as exc:
            trace.add("model_error", step=step, error_type=type(exc).__name__, error=str(exc))
            return (
                f"FAILED: model turn {step} ended with {type(exc).__name__}: {exc}. "
                "No dashboard is accepted as complete."
            )
        message = response.choices[0].message
        trace.add(
            "model_end",
            step=step,
            content_preview=(message.content or "")[:1_000],
            tool_calls=[call.function.name for call in (message.tool_calls or [])],
        )
        if message.tool_calls:
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [call.model_dump() for call in message.tool_calls],
            })
            for call in message.tool_calls:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as exc:
                    result = json.dumps({"ok": False, "error": f"invalid tool JSON: {exc}"})
                else:
                    print(f"[step {step}] TOOL {call.function.name}")
                    result = tools.dispatch(call.function.name, arguments)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            continue

        answer = message.content or "Agent ended without a text response."
        if not tools.report_collected:
            trace.add("completion_gate_rejected", step=step, answer_preview=answer[:1_000])
            messages.append({"role": "assistant", "content": answer})
            messages.append({
                "role": "user",
                "content": (
                    "COMPLETION GATE REJECTED: collect_security_report has not returned ok=true. "
                    "Your claimed success is invalid. Inspect the failed contract, repair/resubmit "
                    "the Spark job, and call collect_security_report again."
                ),
            })
            continue
        trace.add("final", step=step, answer=answer, todo=tools.todo.items)
        return answer

    answer = (
        f"FAILED: reached the {max_steps}-step limit before collect_security_report returned ok=true. "
        "No dashboard is accepted as complete. Inspect agent-trace.jsonl and Spark job logs."
    )
    trace.add("step_limit", answer=answer, todo=tools.todo.items)
    return answer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure Python security-log analytics agent (no LangGraph)")
    parser.add_argument("archive", type=Path, help="Path to an authorized ZIP or plain-text security log")
    parser.add_argument(
        "--question",
        default="Analyze this security log end-to-end, build the dashboard, and provide executive findings and early warning signals.",
    )
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--max-steps", type=int, default=48)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = args.artifacts.resolve()
    trace = RunTrace(artifacts / "agent-trace.jsonl")
    spark_url = os.getenv("SPARK_HDFS_MCP_URL", "http://127.0.0.1:8001/mcp")
    skills_url = os.getenv("SECURITY_SKILLS_MCP_URL", "http://127.0.0.1:8003/mcp")
    container = os.getenv("SPARK_HDFS_MCP_CONTAINER", "spark-standalone-spark-hdfs-mcp-1")

    print("[runtime] Pure Python loop; LangGraph is not imported")
    print(f"[input] {args.archive.resolve()}")
    tools = SecurityAnalyticsTools(args.archive, artifacts, container, spark_url, skills_url, trace)
    print(f"[MCP] discovered {len(tools.registry.openai_tools)} remote tools from 2 servers")
    try:
        answer = run_agent(args.question, tools, trace, args.max_steps)
    finally:
        tools.close()
    (artifacts / "agent-answer.md").write_text(answer + "\n", encoding="utf-8")
    print("\n" + "=" * 72 + "\n" + answer)
    print(f"\n[trace] {trace.path}")


if __name__ == "__main__":
    main()
