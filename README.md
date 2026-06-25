# Python-Agent-LangGraph

> หลักสูตร **Agentic AI Development with Python (หลักสูตรที่ 2)** —
> เขียน Agent ด้วย Pure Python ทีละขั้น (Lab 1–7) แล้วเปรียบเทียบกับ LangGraph (Lab 8) ก่อน deploy เป็น API Service (Lab 9)

repo นี้เป็นชุดแล็บ **9 Lab** ที่ต่อเนื่องกัน สอนตั้งแต่เรียก LLM ครั้งแรก จนถึง deploy Agent เป็น API + Docker
ทุก Lab เชื่อมกับ **MCP MSSQL Server จริง** ของหลักสูตรที่ 1 เป็นแกนข้อมูลเดียวกัน

---

## เอกสารในโปรเจกต์นี้ต่างกันอย่างไร (อ่านไฟล์ไหนก่อน)

repo นี้มี README หลายระดับ แต่ละไฟล์ตอบคนละคำถาม — เลือกอ่านตามว่าคุณอยากรู้อะไร:

| ไฟล์ | ตอบคำถามว่า | เหมาะกับใคร |
| --- | --- | --- |
| **`README.md` (ไฟล์นี้)** | "โปรเจกต์นี้คืออะไร โครงสร้าง repo เป็นแบบไหน จะเริ่มอ่านที่ไหน" — ภาพรวมระดับ repo + จุดเริ่มต้น | คนเปิด repo ครั้งแรก |
| [`labs/README.md`](labs/README.md) | "หลักสูตรมีกี่ Lab เรียงยังไง **เส้นทางการเรียนรู้** ไล่จาก Lab 1 ถึง 9 อย่างไร ติดตั้ง/รันยังไง" — สารบัญ + เส้นเรื่องการสอน + setup/run | ผู้เรียน/ผู้สอนที่จะเดินตามหลักสูตร |
| `labs/labN_*/README.md` | "Lab นี้มีจุดประสงค์อะไร รันยังไง โค้ดจุดสำคัญอยู่ตรงไหน" — รายละเอียดเชิงลึกราย Lab | คนที่กำลังทำ Lab นั้นอยู่ |

> สรุปสั้น: **ไฟล์นี้ = ประตูหน้าระดับ repo** (โครงสร้าง + ชี้ทาง) · **`labs/README.md` = สารบัญ + เส้นเรื่องหลักสูตร + setup/run** · **README ราย Lab = คู่มือลงมือทำของแต่ละ Lab**

---

## เริ่มต้น (Clone Repository)

```bash
git clone https://github.com/aekanun2020/Python-Agent-LangGraph.git
cd Python-Agent-LangGraph
```

> **ขั้นตอนติดตั้งสภาพแวดล้อม (conda env + `.env` + dependencies) และวิธีรันแต่ละ Lab อยู่ใน [`labs/README.md`](labs/README.md)** — โดย Setup เต็มเป็นแหล่งเดียว (single source) อยู่ที่ [Lab 1](labs/lab1_setup/README.md) ทำครั้งเดียวก่อนเริ่มทุก Lab (พัฒนา/ทดสอบด้วย **Miniconda**, Python 3.11)

---

## โครงสร้างโปรเจกต์

```
Python-Agent-LangGraph/
├── README.md                   # ไฟล์นี้ — ภาพรวมระดับ repo + ชี้ทาง
├── labs/
│   ├── README.md               # สารบัญ Lab 1–9 + เส้นทางการเรียนรู้ + setup/run
│   ├── core/                   # โค้ดกลางที่ทุก Lab ใช้ร่วมกัน (config/llm/mcp_client/registry)
│   ├── lab1_setup/             # Lab 1: ตรวจสภาพแวดล้อม (เจ้าของ Setup เต็ม)
│   ├── lab2_llm/               # Lab 2: เรียก LLM + เทียบโมเดล
│   ├── lab3_agent_loop/        # Lab 3: agent loop แรก (Pure Python)
│   ├── lab4_mcp_agent/         # Lab 4: + MCP MSSQL จริง
│   ├── lab5_skills/            # Lab 5: + Skill routing (มีโฟลเดอร์ skills/)
│   ├── lab6_todo/              # Lab 6: + TodoWrite
│   ├── lab7_memory/            # Lab 7: + Memory/Compaction/Note-taking
│   ├── lab8_langgraph/         # Lab 8: LangGraph Agent (pivot — เทียบ Pure Python)
│   └── lab9_deploy/            # Lab 9: ห่อ agent เป็น FastAPI API + Docker
├── docker-compose.yml          # Lab 9: service agent (ชี้ MCP MSSQL จริงผ่าน .env)
├── .dockerignore
├── discover_mssql.py           # ยูทิลิตี้ตรวจการเชื่อมต่อ + list tools/args schema
├── screenshots/labs/           # ภาพหน้าจอผลการรันทดสอบจริง (Lab 1–9)
│   ├── lab1_check_env.png ... lab7_memory.png
│   ├── lab8_01_mssql_discovery.png / lab8_02_agent_q1.png / lab8_03_agent_q2.png
│   ├── lab9_api_deploy.png
│   └── layer_coverage_matrix.png   # ตารางแมป layer สถาปัตยกรรม × Lab
├── requirements.txt
├── .env.example                # เทมเพลต env (ไม่มีคีย์จริง)
├── .gitignore
└── (README.md)
```

---

## สถาปัตยกรรม Agent: App → Agent → LLM + 8 Layers

เพื่อให้เข้าใจว่าแต่ละ Lab "กำลังสร้างชิ้นส่วนไหนของ Agent" repo นี้ยึดภาพสถาปัตยกรรมเดียวกันทั้งหลักสูตร
หัวใจคือ **LLM ทำหน้าที่ reasoning/decision** แต่สิ่งที่ทำให้มันเป็น "Agent" และประกอบขึ้นเป็น "App" จริง
คือ layer ที่ห่อรอบ LLM ต่างหาก

```
┌──────────────────────────────────────────────┐
│                    APP                         │
│  + UI, Auth, DB, Business Logic, Infra         │
│  ┌──────────────────────────────────────────┐ │
│  │              AGENT                        │ │
│  │  + Memory, Tools, Hooks, State            │ │
│  │   ┌────────────────────────────────┐      │ │
│  │   │           LLM                  │      │ │
│  │   │  (reasoning / decision)        │      │ │
│  │   └────────────────────────────────┘      │ │
│  └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

กางภาพข้างบนออกเป็น **8 layer** ของ Agent harness — แต่ละ layer มีคำอธิบายและ **แหล่งอ้างอิงต้นทาง** (origin paper / เอกสารทางการของบริษัทเทคโนโลยี) ที่เข้าดูได้จริง:

| # | Layer | ทำหน้าที่อะไร | แหล่งอ้างอิงต้นทาง (เปิดดูได้จริง) |
| :-: | --- | --- | --- |
| 1 | **Instructions / Bootstrap** | คำสั่งระบบ/บุคลิก/ขอบเขตที่โหลดตอนเริ่ม (เช่น `SOUL.md`, `AGENTS.md`) — กำหนดพฤติกรรมก่อนโมเดลเห็นงาน | Anthropic — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 2 | **Memory** | ความจำสั้น/ยาว/procedural + compaction + note-taking | CoALA: [Cognitive Architectures for Language Agents](https://arxiv.org/abs/2309.02427) (Sumers et al., 2024) · Anthropic — [context engineering: compaction & note-taking](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| 3 | **Tools + Skills** | ความสามารถภายนอก (MCP) + procedure ที่นำกลับมาใช้ซ้ำ (Skills) โหลดตามความจำเป็น | Anthropic — [Introducing the Model Context Protocol](https://www.anthropic.com/news/model-context-protocol) · [Agent Skills (Claude Docs)](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| 4 | **Hooks** | callback ที่ดักจังหวะ lifecycle ของ agent (เช่น `PreToolUse`/`PostToolUse`/`Stop`) เพื่อ log/บล็อก/แทรก context แบบ deterministic | Anthropic — [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks) |
| 5 | **Reasoning Loop** | วงคิด-ทำ-สังเกต (reason → act → observe → วน) แกนของ agent | ReAct: [Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) (Yao et al., ICLR 2023) |
| 6 | **Sandbox + Execution** | ที่รันโค้ด/คำสั่งที่โมเดลสร้างขึ้นแบบแยกขอบเขต (Docker/VM/Computer Use) | Anthropic — [Computer use tool](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool) · [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) |
| 7 | **Gateway + Scheduler** | ช่องทางเข้า-ออก (HTTP/Telegram/Slack) + ตัวกระตุ้นตามเวลา (Cron) | Anthropic — [MCP: Transports (Streamable HTTP / stdio)](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) |
| 8 | **Safety Layer** | permission gating, audit trail, self-check + containment ที่ environment layer | Anthropic — [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) |

> หมายเหตุ: CoALA (layer 2) และ ReAct (layer 5) เป็น academic paper ส่วน MCP/Skills/Hooks/Computer Use/Containment เป็นเอกสารทางการของ Anthropic

### แต่ละ Lab อยู่ตรงไหนของ 8 Layer นี้

สัญลักษณ์: ● = เป็นแกนหลักของ Lab นั้น · ◐ = แตะ/มีบางส่วน · (ว่าง) = ไม่มี

| Layer | L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9 |
| --- | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: | :--: |
| 1. Instructions / Bootstrap | | | ◐ | ◐ | ● | ◐ | ◐ | ◐ | ◐ |
| 2. Memory | | | | | | | ● | ● | ◐ |
| 3. Tools + Skills | ◐ | | ◐ | ● | ● | ● | ● | ● | ● |
| 4. Hooks | | | | | | | ◐* | | ◐* |
| 5. Reasoning Loop | | | ● | ● | ● | ● | ● | ● | ◐ |
| 6. Sandbox + Execution | | | ◐* | | | | | | ◐* |
| 7. Gateway + Scheduler | | | | | | | | | ◐ |
| 8. Safety Layer | | | ◐* | | | | | | ◐ |

> `◐*` = มีร่องรอย/พฤติกรรมคล้าย แต่ยังไม่ใช่ระบบจริงตามนิยาม layer
> **สรุป coverage:** ครบจริง 4 layer (1, 2, 3, 5) · มีบางส่วน 1 layer (7 — มี HTTP gateway แต่ยังไม่มี Telegram/Slack/Cron) · ยังไม่มีจริง 3 layer (4 Hooks, 6 Sandbox/Execution, 8 Safety)
> รายละเอียด gap + เหตุผลว่าทำไม layer 4/6/8 อยู่นอกขอบเขต `course2_outline-1.pdf` อธิบายไว้ที่ [Lab 9 — Layer Coverage & Gaps](labs/lab9_deploy/README.md) (มีภาพ matrix ประกอบ)

README ของแต่ละ Lab จะมีบรรทัด **"ตำแหน่งใน 8 Layer"** บอกว่า Lab นั้นสร้างชิ้นส่วนไหนของภาพนี้

---

## หมายเหตุด้านความปลอดภัย

- `.env` (คีย์จริง) ถูก `gitignore` ไว้ — repo นี้มีเฉพาะ `.env.example` ที่ไม่มีคีย์จริง
- ก่อน push ทุกครั้ง ตรวจสอบว่าไม่มีคีย์หลุดเข้าไปในไฟล์ที่ commit
