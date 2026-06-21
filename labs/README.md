# Labs 1–7 — Pure Python Agent (หลักสูตร Agentic AI Development with Python)

Lab 1–7 สอน "เขียน Agent ด้วย Pure Python เอง" (while loop + model + tools) ทีละขั้น
จนเข้าใจกลไกเบื้องหลังทั้งหมด ก่อนจะไปดู Lab 8 ที่ทำสิ่งเดียวกันด้วย **LangGraph**
(`src/agent_langgraph.py`) เพื่อเทียบว่า framework ช่วย "ลดโค้ดส่วนไหน" ให้บ้าง

> ทุก Lab ต่อกับ **MCP MSSQL Server จริง** ของหลักสูตรที่ 1 (ฐานข้อมูล `TestDB`)
> เป็นแกนเดียวกันทั้งหมด — สอดคล้องกับ Lab 8

---

## สถาปัตยกรรมที่ต่อเนื่องกัน

ทุก Lab ใช้ชุดเครื่องมือกลางใน `labs/core/` ร่วมกัน และแต่ละ Lab "ต่อยอด" จาก Lab ก่อนหน้า:

```
core/config.py     โหลด .env รวมที่เดียว (LLM + MCP)        ← เริ่มใช้ Lab 1
core/llm.py        OpenRouter thin client (OpenAI SDK)      ← เริ่มใช้ Lab 1–2
core/mcp_client.py MCP client เขียนเอง (Streamable HTTP/SSE) ← เริ่มใช้ Lab 4
core/registry.py   Tool Registry รวม tools หลาย MCP server   ← เริ่มใช้ Lab 4

Lab 3  agent loop (local tools)
  └─ Lab 4  + MCP MSSQL จริง (แทน local tools)
       └─ Lab 5  + Skill routing (Progressive Disclosure)
            └─ Lab 6  + TodoWrite (วางแผนงานหลายขั้น)
                 └─ Lab 7  + Memory + Compaction + Note-taking
                      └─ Lab 8  = ทุกอย่างข้างบน แต่เขียนด้วย LangGraph (`lab8_langgraph/`)
                           └─ Lab 9  = ห่อ Lab 8 เป็น FastAPI API + Docker (`lab9_deploy/`)
```

---

## รายการ Lab

| Lab | โฟลเดอร์ | เนื้อหา (อ้างอิง outline) | สิ่งที่เพิ่มจาก Lab ก่อน |
|-----|----------|---------------------------|---------------------------|
| 1 | `lab1_setup/check_env.py` | ตรวจสภาพแวดล้อม — บทที่ 1.2 | ตรวจ LLM + MCP เป็น precondition |
| 2 | `lab2_llm/first_llm.py`, `compare_models.py` | เรียก LLM ครั้งแรก + เทียบโมเดล — บทที่ 1.2 | messages/role + token usage |
| 3 | `lab3_agent_loop/agent_loop.py` | Agent loop แรก (Pure Python) — บทที่ 1.3 | while loop + local tools |
| 4 | `lab4_mcp_agent/agent_mcp.py` | Agent + MCP จริง — บทที่ 1.4 | MCP client + Tool Registry |
| 5 | `lab5_skills/agent_skills.py` | Skill routing — บทที่ 2.1 | SkillLoader + Progressive Disclosure |
| 6 | `lab6_todo/agent_todo.py` | TodoWrite — บทที่ 2.2 | วางแผนงานหลายขั้นใน state |
| 7 | `lab7_memory/agent_memory.py` | Memory — บทที่ 2.3 | จำข้ามรอบ + compaction + notes |
| 8 | `lab8_langgraph/agent_langgraph.py` | LangGraph Agent — บทที่ 3.1 | State/Node/Edge/Checkpointer (เทียบ Pure Python) |
| 9 | `lab9_deploy/` (app.py, Dockerfile) | Deploy — บทที่ 3.3 | FastAPI `/chat` + Docker + Retry/Logging |

---

## การเตรียมสภาพแวดล้อม (Miniconda)

```bash
# สร้าง env (Python 3.11)
conda create -n agentic-ai python=3.11 -y
conda activate agentic-ai

# ติดตั้ง dependencies
pip install -r requirements.txt

# ตั้งค่า .env (ห้าม commit คีย์จริง — .env ถูก gitignore แล้ว)
cp .env.example .env
#   แก้ OPENROUTER_API_KEY = คีย์จริงของคุณ
#   แก้ MCP_SERVER_URL     = URL ngrok ของ MCP MSSQL Server ที่เปิดไว้
```

ค่าใน `.env` ที่ต้องมี:

- `OPENROUTER_API_KEY` — ขอที่ https://openrouter.ai/keys
- `OPENROUTER_BASE_URL` — `https://openrouter.ai/api/v1`
- `OPENROUTER_MODEL` — `anthropic/claude-sonnet-4.6`
- `MCP_SERVER_URL` — URL ของ MCP MSSQL Server จริง (Streamable HTTP, ลงท้าย `/mcp`)

---

## วิธีรันแต่ละ Lab

> รันจาก root ของโปรเจกต์เสมอ (เพื่อให้ `import labs.core` ทำงาน)

```bash
conda activate agentic-ai

# Lab 1 — ตรวจ LLM + MCP พร้อมใช้งานไหม
python labs/lab1_setup/check_env.py

# Lab 2 — เรียก LLM ครั้งแรก + เทียบโมเดล
python labs/lab2_llm/first_llm.py "อธิบาย MCP ใน 2 ประโยค"
python labs/lab2_llm/compare_models.py

# Lab 3 — agent loop + local tools
python labs/lab3_agent_loop/agent_loop.py "ตอนนี้กี่โมง แล้ว 15*4 เท่ากับเท่าไร"

# Lab 4 — agent + MCP MSSQL จริง
python labs/lab4_mcp_agent/agent_mcp.py "มีตารางอะไรบ้าง และมีพนักงานกี่คน"

# Lab 5 — skill routing
python labs/lab5_skills/agent_skills.py "แต่ละแผนกมีพนักงานกี่คน"
python labs/lab5_skills/agent_skills.py "ลูกค้าโกรธมาก ขอคุยหัวหน้า"

# Lab 6 — TodoWrite (multi-step)
python labs/lab6_todo/agent_todo.py

# Lab 7 — Memory ข้ามรอบ
python labs/lab7_memory/agent_memory.py

# Lab 8 — LangGraph Agent (ทำสิ่งเดียวกับ Lab 4 แต่เขียนด้วย LangGraph)
python labs/lab8_langgraph/agent_langgraph.py

# Lab 9 — ห่อ agent เป็น API + Docker (ดูรายละเอียดที่ labs/lab9_deploy/README.md)
uvicorn labs.lab9_deploy.app:app --host 0.0.0.0 --port 8080   # หรือ  docker compose up --build
```

---

## ภาพหน้าจอผลการทดสอบ (รันจริง)

ทุกภาพอยู่ใน `screenshots/labs/` รันจริงกับ MCP MSSQL Server (`TestDB`):

| Lab | ภาพ | สรุปผล |
|-----|-----|--------|
| 1 | `screenshots/labs/lab1_check_env.png` | LLM ผ่าน + MCP ผ่าน (พบ 5 tools) |
| 3 | `screenshots/labs/lab3_agent_loop.png` | loop เรียก local tool `get_time` + `calculate` ถูกต้อง |
| 4 | `screenshots/labs/lab4_mcp_agent.png` | ต่อ MCP จริง 5 tools, ตอบ 16 ตาราง / 25 คน / 8 แผนก |
| 5 | `screenshots/labs/lab5_skill_routing.png` | route ไป `hr_analytics` และ `customer_service` ถูกตาม domain |
| 6 | `screenshots/labs/lab6_todowrite.png` | วางแผน todo ก่อน แล้วอัปเดตสถานะระหว่างทำ |
| 7 | `screenshots/labs/lab7_memory.png` | จำบริบทข้ามรอบได้ ("แผนกนั้น" อ้างถึง IT จากรอบก่อน) |
| 8 | `screenshots/labs/lab8_01_mssql_discovery.png`, `lab8_02_agent_q1.png`, `lab8_03_agent_q2.png` | LangGraph: discover 5 tools, ตอบ Q1/Q2, Checkpointer จำ context ข้ามคำถาม |
| 9 | `screenshots/labs/lab9_api_deploy.png` | API service: `/health` ok, `POST /chat` 2 รอบ (thread เดียว) + log tool calls + Checkpointer จำ context |

> Lab 2 ไม่ได้แนบภาพ เพราะ `compare_models.py` เรียกหลายโมเดลและมีค่าใช้จ่าย —
> รันได้เองตามคำสั่งด้านบน

---

## หมายเหตุขอบเขต (ตามกติกาของ Space)

- Lab 1–7 ยึด **MCP MSSQL จริงตัวเดียว** เป็นแกน (ตามที่ตกลงไว้ และสอดคล้องกับ Lab 8)
- ใน outline เดิม Lab 5 ยกตัวอย่าง skill ชื่อ `seismic_insurance` — แต่เนื่องจาก
  ฐานข้อมูลจริงคือ `TestDB` (โดเมน HR/Customer Service) จึงเปลี่ยนตัวอย่าง skill เป็น
  `hr_analytics`, `customer_service`, `database_query` ให้ตรงข้อมูลจริง
  (เป็นการปรับให้สอดคล้องข้อมูล ไม่ได้ขยายขอบเขตเนื้อหา)
