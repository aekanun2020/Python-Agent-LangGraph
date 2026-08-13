# Local-model benchmark — PAN-OS traffic 100k

วันที่ทดสอบ: 2026-08-13 (Asia/Bangkok)

Input: `panos-traffic-100k.zip`, 100,000 records, 49,458,688 uncompressed bytes

Environment:

- Pure Python ReAct loop; AST test confirms no `langgraph`/`langchain` import
- Spark standalone: 1 master, 2 workers
- HDFS: 1 NameNode, 2 DataNodes
- Spark/HDFS MCP: 18 tools
- Security Skill MCP: 9 tools
- Parser resolved locally: `paloalto-panos-11x-traffic` v1.1.0

## Results

| Model | What worked | Failure | Accepted dashboard |
| --- | --- | --- | --- |
| `qwen3.5:35b-a3b-coding-nvfp4` | Planned, resolved Skill, imported to HDFS, checked clusters, wrote/validated/submitted PySpark, inspected logs and patched code repeatedly | First attempt shifted CSV fields; Action became protocol. Semantic gate rejected the claimed result. A later aligned job failed during nested report serialization and the following model turn stalled. | No |
| `nemotron-3.5-lightning:latest` | Planned, resolved Skill, imported to HDFS, checked clusters | Stalled while generating the full PySpark program; run was terminated without a submitted valid report. | No |

## Conclusion

The harness and MCP integration operated as designed, including the most important
negative behavior: a model-generated success statement was rejected. These two
local models did **not** reproduce the end-to-end quality of the reference pipeline
in this run. This is a model-quality/latency benchmark result, not evidence of a
successful dashboard.

Use a stronger tool-calling coding model through OpenRouter and run the exact
evaluator documented in the Lab README. Keep any score below 100% as a failed or
partial experiment; never patch aggregate numbers by hand.
