# Lab 9 — Containerized Agent + MCP Server (Capstone / Deploy)

หลักสูตร Agentic AI Development with Python — **Module 3.3**

ปิด loop ทั้งหลักสูตร: นำ **LangGraph Agent ของ Lab 8** มาห่อเป็น **API Service** ด้วย
FastAPI แล้ว deploy เป็น **Docker Container** สำหรับ Production พร้อม Error Handling,
Retry และ Logging

---

## ไฟล์ใน Lab นี้

| ไฟล์ | หน้าที่ |
|------|---------|
| `app.py` | FastAPI service — `POST /chat`, `GET /health` (reuse `build_graph()` ของ Lab 8) |
| `requirements.txt` | dependencies ของ image (LangGraph + FastAPI/uvicorn) |
| `Dockerfile` | สร้าง image ของ agent (python:3.11-slim + uvicorn + healthcheck) |
| `../../docker-compose.yml` | service `agent` (อยู่ที่ root ของ repo) |
| `../../.dockerignore` | ตัด `.env`/`.git`/screenshots ออกจาก build context |

> ออกแบบให้ `app.py` **import `build_graph()` จาก Lab 8 โดยตรง** — agent ตัวเดียวกัน
> ไม่เขียนซ้ำ ทำให้ Lab 8 → Lab 9 ต่อเนื่องกันจริง

---

## API

### `GET /health`
```json
{"status": "ok", "agent_ready": true, "mcp_server": "https://.../mcp"}
```

### `POST /chat`
Request:
```json
{"message": "แต่ละแผนกมีพนักงานกี่คน", "thread_id": "demo-1"}
```
Response:
```json
{
  "reply": "...คำตอบภาษาไทย + ตารางสรุป...",
  "thread_id": "demo-1",
  "tool_calls": ["get_database_context", "execute_query_tool"],
  "elapsed_ms": 26194
}
```
ส่ง `thread_id` เดิมซ้ำ = คุยต่อเนื่องในบทสนทนาเดียวกัน (Checkpointer จำ context ให้)

---

## คุณสมบัติตาม outline 3.3

- **API Service** — FastAPI + uvicorn ห่อ agent เป็น HTTP endpoint
- **Error Handling** — จับ exception ตอน agent ทำงาน คืน HTTP 502 แทนการ crash;
  ถ้า agent ยังไม่พร้อม (MCP ต่อไม่ได้) คืน 503
- **Retry Strategy** — ตอน startup ต่อ MCP ด้วย **exponential backoff**
  (`MCP_MAX_RETRIES`, `MCP_BACKOFF_BASE`) กัน container เพิ่งสตาร์ตแล้ว MCP ยังไม่พร้อม
- **Logging** — log ทุก request + **ทุก tool call ที่ agent เรียก** + เวลาที่ใช้
  เพื่อ debug agent behavior

---

## วิธีรัน

### 1) รันแบบ local (ทดสอบเร็ว)
```bash
conda activate agentic-ai
pip install -r labs/lab9_deploy/requirements.txt
# รันจาก root ของ repo (ให้ import labs.* ได้)
uvicorn labs.lab9_deploy.app:app --host 0.0.0.0 --port 8080
```

### 2) รันด้วย Docker Compose (production)
```bash
# ตั้งค่า .env ให้มี OPENROUTER_API_KEY และ MCP_SERVER_URL (MCP MSSQL จริง)
docker compose up --build
```

### ทดสอบ
```bash
curl -s localhost:8080/health

curl -s -X POST localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"แต่ละแผนกมีพนักงานที่ยังปฏิบัติงานกี่คน","thread_id":"demo-1"}'

# ถามต่อใน thread เดิม -> agent จำ context (Checkpointer)
curl -s -X POST localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"แล้วแผนกที่มากที่สุดนั้น มีใครบ้าง","thread_id":"demo-1"}'
```

ภาพผลการรันจริง: `screenshots/labs/lab9_api_deploy.png`

---

## หมายเหตุขอบเขต (ตามกติกาของ Space — ขอแจ้ง)

outline ข้อ 3.3 ยกตัวอย่าง compose ที่รวมหลาย MCP service (`mssql-mcp`, `rag-mcp`,
`seismic-mcp`) แต่ตามที่ **ตกลงกันในคอร์สว่ายึด MCP MSSQL จริงตัวเดียว** (สอดคล้อง
Lab 4–8 และได้เอา seismic จำลองออกแล้ว) — `docker-compose.yml` จึงมี **service
`agent` ตัวเดียว** ที่ชี้ไป MCP MSSQL จริงภายนอกผ่าน `MCP_SERVER_URL`

หากภายหลังต้องการรัน MCP server ใน compose ด้วย เพิ่ม service `mssql-mcp`
(ใช้ Dockerfile ของ MCP server จากหลักสูตรที่ 1) เข้า network เดียวกัน แล้วเปลี่ยน
`MCP_SERVER_URL=http://mssql-mcp:9000/mcp` — โครงสร้าง compose รองรับไว้แล้ว
(เป็นการปรับให้ตรงกับ MSSQL-only ที่ตกลงไว้ ไม่ได้ลดความสามารถของ Lab)
