# Lab 2 — เรียกใช้ LLM API ครั้งแรกและเปรียบเทียบโมเดล

> หลักสูตร **Agentic AI Development with Python (หลักสูตรที่ 2)** — Module 1.2

---

## จุดประสงค์การเรียนรู้

- เข้าใจโครงสร้าง **messages** และ **role** (system / user / assistant) ที่ใช้กับ LLM API
- อ่านและตีความ **token usage** (prompt / completion / total) เพื่อบริหารต้นทุนและ context window
- เปรียบเทียบผลลัพธ์และเวลาตอบสนองของหลายโมเดลบน OpenRouter เพื่อเลือกโมเดลให้เหมาะกับงาน

---

## สิ่งที่ต้องเตรียมก่อน (Prerequisites)

- ทำ Setup สภาพแวดล้อมใน [Lab 1](../lab1_setup/README.md) ให้เสร็จก่อน (conda env `agentic-ai` + `.env`)

---

## วิธีรัน

```bash
conda activate agentic-ai
cd Python-Agent-LangGraph   # รันจาก root repo (เพราะ import labs.core.*)

# ไฟล์ที่ 1: เรียก LLM ครั้งแรก + ดู token usage
python labs/lab2_llm/first_llm.py "อธิบาย Agent Loop ใน 2 ประโยค"

# ไฟล์ที่ 2: เปรียบเทียบหลายโมเดลด้วยคำถามเดียวกัน
python labs/lab2_llm/compare_models.py
```

---

## อธิบายจุดสำคัญของโค้ด

### `first_llm.py` — โครงสร้าง messages และ token usage

#### ฟังก์ชัน `ask(question, max_tokens)`

จุดสำคัญที่ควรเปิดอ่าน:

```python
messages = [
    {"role": "system", "content": SYSTEM},   # system : กำหนดบทบาท/พฤติกรรม
    {"role": "user",   "content": question}, # user   : คำถามจากผู้ใช้
]
resp = llm.chat(messages=messages, max_tokens=max_tokens)
```

- ตัวแปร `SYSTEM` คือ system prompt ที่กำหนดบทบาทของ LLM
- `resp.choices[0].message.content` คือคำตอบของโมเดล
- `resp.usage` มีฟิลด์ `prompt_tokens`, `completion_tokens`, `total_tokens` — ใช้ติดตามค่าใช้จ่ายและตรวจว่าใกล้ context limit หรือยัง
- การตั้ง `max_tokens` ต่ำๆ เป็นวิธีฝึกดูผลของ output limit

### `compare_models.py` — เปรียบเทียบโมเดล

#### ฟังก์ชัน `run()`

ส่ง `QUESTION` เดียวกัน (`"อธิบายความต่างของ Chatbot กับ Agent ใน 2 ประโยค"`) ไปยังหลายโมเดลใน `MODELS` list โดยใช้ `llm.chat(model=model, ...)` แล้ววัด:
- `resp.usage.total_tokens` — จำนวน token ที่ใช้
- `time.time()` ก่อน/หลัง — เวลาตอบสนอง (วินาที)

สรุปผลเป็นตาราง `model / total_tok / sec / note` เพื่อเปรียบเทียบได้ทันที

> จุดที่ควรเปิดอ่าน: parameter `model=model` ใน `llm.chat()` — แสดงว่า OpenRouter รองรับการเลือกโมเดลต่อ request โดยไม่ต้องสร้าง client ใหม่

---

## ผลลัพธ์ที่คาดหวัง

### `first_llm.py`

```
============================================================
[user]      อธิบาย Agent Loop ใน 2 ประโยค
[assistant] Agent Loop คือ...
------------------------------------------------------------
[token] prompt=42 completion=68 total=110
[model] anthropic/claude-sonnet-4.6
```

### `compare_models.py`

```
==============================================================================
model                                   total_tok    sec  note
------------------------------------------------------------------------------
anthropic/claude-sonnet-4.6                   185   2.31  Agent คือระบบที่...
openai/gpt-oss-120b                           172   3.10  ...
meta-llama/llama-3.1-8b-instruct              144   1.05  ...
```

> Lab 2 ไม่มี screenshot รวมไว้ใน repo เพราะ `compare_models.py` เรียกหลายโมเดลและมีค่าใช้จ่าย — รันได้เองตามคำสั่งด้านบน
