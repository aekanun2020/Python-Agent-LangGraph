# Lab 10 — Pure Python Security Analytics Agent (ไม่ใช้ LangGraph)

Lab นี้ใช้ตอบคำถามตรงๆ ว่า **Agent ที่เขียนด้วย Python loop ธรรมดา สามารถรับ ZIP log, เลือก vendor skill, เขียน PySpark, submit งาน และสร้าง dashboard ได้หรือไม่**

คำตอบต้องวัดจากการรันจริง ไม่ใช่จากคำอธิบาย จึงมีทั้ง execution trace และตัวเปรียบเทียบผลกับ reference report

## สิ่งที่ Agent ตัดสินใจเอง

1. วางแผนและอัปเดต Todo
2. สั่ง local guardrail ตรวจตัวอย่าง log ผ่าน Security Skill MCP แล้วเลือก parser โดยไม่ส่ง raw event ไป LLM ภายนอก
3. เรียก Spark/HDFS MCP เพื่อนำข้อมูลเข้า HDFS
4. **เขียนโปรแกรม PySpark ผ่าน `spark_save_job` ด้วยตัวเอง**
5. validate, submit, รอผล และแก้โค้ดใหม่หาก Spark ล้มเหลว โดยใช้ read/exact-text patch สำหรับการแก้จุดเล็ก
6. ตรวจ analytical contract และสรุป Executive Security Findings

ส่วนที่เป็น deterministic guardrail คือการแตก ZIP อย่างปลอดภัย, การรอ job, การตรวจ schema ของ report และการ render HTML จาก aggregate JSON การแยกแบบนี้ทำให้เปรียบเทียบ “ความถูกต้องของการวิเคราะห์โดย Agent” ได้โดยไม่ให้หน้าตา dashboard แบบสุ่มมารบกวนผลทดสอบ

## สถาปัตยกรรม

```text
ZIP log
  │
  ▼
Pure Python ReAct loop ─── OpenRouter model
  ├── bounded local tools: ZIP staging, Todo, job wait, report validation
  ├── Security Skill MCP: ตรวจ vendor ภายในเครื่อง + คืน approved parser metadata
  └── Spark/HDFS MCP: HDFS import + write/validate/submit PySpark
                              │
                              ▼
                       Spark 1 master / 2 workers
                              │
                              ▼
                    JSON report + HTML dashboard + trace
```

ไฟล์ runtime ของ Lab นี้ไม่มีการ import `langgraph` หรือ `langchain` และติดตั้งเฉพาะ `requirements-pure-python.txt` ได้

## Step 1 — เตรียมเครื่อง

ต้องมี:

- Python 3.11+
- Docker Desktop และ Docker Compose
- OpenRouter API key
- repository `mcp-server-for-spark-hdfs`
- ZIP หรือ plain-text security log ที่ผู้ใช้มีสิทธิ์วิเคราะห์

ตรวจสอบ:

```bash
python3 --version
docker version
docker compose version
```

## Step 2 — เปิด Spark/HDFS และ Skill MCP

ทำใน repository `mcp-server-for-spark-hdfs`:

```bash
docker compose up -d --build --wait
docker compose ps
make mcp-test
make skill-mcp-test
```

ผลที่ควรเห็น:

- Spark workers 2 ตัว
- HDFS DataNodes 2 ตัว
- Spark/HDFS MCP ที่ `http://127.0.0.1:8001/mcp`
- Security Skill MCP ที่ `http://127.0.0.1:8003/mcp`

## Step 3 — ติดตั้งเฉพาะ Pure Python runtime

ทำจาก root ของ repository นี้:

```bash
python3 -m venv .venv-pure
source .venv-pure/bin/activate
python -m pip install -r requirements-pure-python.txt
```

ตรวจว่า runtime ไม่มี LangGraph:

```bash
python -c "import importlib.util; print('langgraph installed =', bool(importlib.util.find_spec('langgraph')))"
python -m unittest -v tests.test_lab10_pure_python_agent
```

แม้ environment อื่นจะติดตั้ง LangGraph อยู่ การทดสอบ AST จะยืนยันว่า agent ไม่ได้ import หรือเรียกใช้มัน

## Step 4 — ตั้งค่า LLM และ MCP

```bash
cp .env.example .env
```

แก้ `.env`:

```dotenv
OPENROUTER_API_KEY=ใส่คีย์จริงที่นี่
OPENROUTER_MODEL=anthropic/claude-sonnet-4.6
SPARK_HDFS_MCP_URL=http://127.0.0.1:8001/mcp
SECURITY_SKILLS_MCP_URL=http://127.0.0.1:8003/mcp
SPARK_HDFS_MCP_CONTAINER=spark-standalone-spark-hdfs-mcp-1
```

ห้าม commit `.env` หรือ API key ขึ้น Git

## Step 5 — รัน Agent กับ ZIP

ตัวอย่าง:

```bash
python labs/lab10_pure_python_analytics/agent_security_analytics.py \
  "/absolute/path/to/panos-traffic-100k.zip"
```

ระหว่างรันจะเห็น tool calls เช่น:

```text
[runtime] Pure Python loop; LangGraph is not imported
[MCP] discovered ... remote tools from 2 servers
[step 1] TOOL todo_write
[step 2] TOOL prepare_input_archive
[step ...] TOOL log_skill_resolve
[step ...] TOOL spark_save_job
[step ...] TOOL spark_submit_job
[step ...] TOOL wait_for_spark_job
[step ...] TOOL collect_security_report
```

Agent อาจใช้จำนวน step หรือลำดับย่อยต่างกัน เพราะ LLM เป็นผู้ควบคุม workflow แต่ต้องไม่สรุปว่าสำเร็จก่อน Spark job เป็น `SUCCEEDED` และ report ผ่าน contract

Runtime มี completion gate แบบ deterministic: ต่อให้โมเดลเขียนข้อความว่า “สำเร็จ” ระบบจะปฏิเสธ final answer จนกว่า `collect_security_report` จะคืน `ok=true`

## Step 6 — ตรวจผลลัพธ์

ไฟล์อยู่ที่ `artifacts/lab10_security_agent/`:

| ไฟล์ | ใช้ทำอะไร |
| --- | --- |
| `security-report.json` | Aggregate report จากโค้ด PySpark ที่ Agent เขียน |
| `security-dashboard.html` | Dashboard แบบ standalone เปิดได้โดยไม่ใช้อินเทอร์เน็ต |
| `agent-answer.md` | Executive summary จาก Agent |
| `agent-trace.jsonl` | Audit trail ของ model/tool calls สำหรับตรวจย้อนหลัง |

เปิด dashboard:

```bash
open artifacts/lab10_security_agent/security-dashboard.html       # macOS
# หรือ xdg-open artifacts/lab10_security_agent/security-dashboard.html  # Linux
```

## Step 7 — เทียบกับผลอ้างอิง

ใช้ report ที่สร้างจาก pipeline อ้างอิงใน repository Spark/HDFS:

```bash
python -m labs.lab10_pure_python_analytics.evaluate_report \
  artifacts/lab10_security_agent/security-report.json \
  "/absolute/path/to/mcp-server-for-spark-hdfs/artifacts/panos-traffic-100k-report.json" \
  --output artifacts/lab10_security_agent/evaluation.json
```

ผลดีที่สุดคือ:

```text
score=.../... (100.0%)
```

ตัวประเมินเทียบจำนวน record, parse quality, bytes, ช่วงเวลา, distributions, top talkers, zone/application traffic, User-ID และ NAT แบบ exact match

## Guardrails ที่ตั้งใจใส่

- รับเฉพาะไฟล์ที่ผู้ใช้ระบุใน command
- อ่าน ZIP member แบบ stream และไม่ extract path จาก ZIP ลง filesystem โดยตรง
- จำกัดขนาด uncompressed member ไม่เกิน 10 GiB
- `docker cp` ได้เฉพาะไฟล์ที่เตรียมไป `/imports/agent-security-input.log`
- HDFS workflow ถูกจำกัดไว้ใต้ `/security-agent`
- ไม่เปิด destructive tools ให้ workflow ใช้
- ไม่ส่ง raw logs เข้า final answer หรือ dashboard
- ไม่ส่ง raw log sample ไปยัง OpenRouter; vendor detection วิ่งตรงจาก local tool ไป local Skill MCP
- เก็บ tool trace ทุกขั้นเพื่อ audit

## Troubleshooting

`permission denied ... docker.sock`

- เปิด Docker Desktop และรันด้วย user ที่ใช้ Docker ได้

`Connection refused 127.0.0.1:8001/8003`

- กลับไปทำ Step 2 และตรวจ `docker compose ps`

`ยังไม่ได้ตั้ง OPENROUTER_API_KEY`

- ตรวจ `.env` ที่ root ของ repository นี้

Spark job เป็น `FAILED`

- Agent จะได้รับ logs และมีโอกาสแก้โค้ด/submit ใหม่
- ดูรายละเอียดทั้งหมดใน `agent-trace.jsonl`

คะแนนไม่ถึง 100%

- เปิด `evaluation.json` ดู check ที่ต่าง
- ตรวจ Spark code ที่ Agent บันทึกผ่าน MCP และ parser version ใน report
- ความคลาดเคลื่อนนี้คือผลการทดลองที่ควรเก็บไว้ ไม่ควรแก้ตัวเลขใน report ด้วยมือ

## ผล benchmark ที่รันในเครื่องพัฒนา

ดู [LOCAL_MODEL_BENCHMARK.md](LOCAL_MODEL_BENCHMARK.md) สำหรับหลักฐานรอบทดสอบ
Palo Alto 100k จริง จุดสำคัญคือผลที่ไม่ผ่าน completion gate จะไม่นับเป็น dashboard
สำเร็จ แม้ข้อความจากโมเดลจะอ้างว่าสำเร็จก็ตาม
