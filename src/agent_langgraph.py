"""
Lab 8 — สร้าง Agent ด้วย LangGraph (ต่อยอดจาก Pure Python Agent ใน Lab 4)
=========================================================================
หลักสูตร Agentic AI Development with Python (หลักสูตรที่ 2) — Module 3.1

แสดงองค์ประกอบหลักของ LangGraph ตาม course outline:
  - State        : สถานะที่ไหลผ่านกราฟ (ในที่นี้คือ messages)
  - Node         : call_model (เรียก LLM), tools (เรียก MCP tools)
  - Edge         : เส้นเชื่อม + Conditional Routing (มี tool call หรือไม่)
  - Checkpointer : Memory/Persistence แบบ built-in (MemorySaver)

LLM provider : OpenRouter (OpenAI SDK + base_url) — เหมือนหลักสูตรที่ 1
Tools        : ค้นพบอัตโนมัติจาก MCP Server (Streamable HTTP) ด้วย MCP Tool Discovery

ค่าเริ่มต้นเชื่อมกับ **MCP MSSQL Server จริง** ของหลักสูตรที่ 1 (ฐานข้อมูล TestDB)
ผ่านตัวแปร MCP_SERVER_URL ใน .env — เปลี่ยน URL อย่างเดียวก็สลับ MCP server ได้
(เช่นชี้ไป RAG MCP :8000) โดยไม่ต้องแก้โค้ด Agent เลย

รัน: python src/agent_langgraph.py
"""
import os
import asyncio
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# ---- MCP Server URL ----
# ค่าเริ่มต้นชี้ไป MCP MSSQL Server จริงของหลักสูตรที่ 1 (ตั้งใน .env)
# เปลี่ยนเป็น MCP Server อื่น เช่น RAG MCP :8000 ได้โดยแก้ค่านี้อย่างเดียว
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:9000/mcp")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6")


# ---- (1) State : สิ่งที่ไหลผ่านทุก Node ใน graph ----
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def build_llm() -> ChatOpenAI:
    """LLM ชี้ไปที่ OpenRouter (thin client) — แนวคิดเดียวกับหลักสูตรที่ 1."""
    return ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0,
    )


async def build_graph():
    """ประกอบ LangGraph: State + Node + Edge + Checkpointer และต่อ MCP tools."""
    # ---- MCP Tool Discovery : ค้นพบ tools อัตโนมัติจาก MCP Server ----
    client = MultiServerMCPClient(
        {"mcp": {"url": MCP_SERVER_URL, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    print(f"[MCP] เชื่อมกับ {MCP_SERVER_URL}")
    print(f"[MCP] ค้นพบ {len(tools)} tools: {[t.name for t in tools]}")

    llm_with_tools = build_llm().bind_tools(tools)

    # ---- (2) Node : call_model (LLM ตัดสินใจว่าจะเรียก tool หรือตอบ) ----
    def call_model(state: AgentState):
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    # ---- (2) Node : tools (รัน MCP tool ตามที่ LLM ขอ) ----
    tool_node = ToolNode(tools)

    # ---- (3) Conditional Edge : ถ้ามี tool_calls ไป tools, ไม่งั้นจบ ----
    def should_continue(state: AgentState):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    # ---- ประกอบ graph ----
    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "call_model")          # วนกลับให้ LLM อ่านผล tool

    # ---- (4) Checkpointer : Memory/Persistence แบบ built-in ----
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


async def main():
    app = await build_graph()
    config = {"configurable": {"thread_id": "fireexit-demo-1"}}

    # System prompt สำหรับโดเมนฐานข้อมูล (MSSQL) — ให้ agent วางแผนเรียก tool เอง
    system = (
        "คุณคือนักวิเคราะห์ข้อมูลของบริษัท ตอบคำถามเชิงธุรกิจจากฐานข้อมูล MS SQL Server "
        "ขั้นตอน: เรียก get_database_context ก่อนเสมอเพื่อดู schema แล้วจึงเขียน T-SQL "
        "ที่ถูกต้อง (ใช้ TOP ไม่ใช่ LIMIT) ส่งให้ execute_query_tool ตอบเป็นภาษาไทย "
        "พร้อมตารางสรุปและข้อสังเกตเชิงธุรกิจ"
    )

    # คำถามเชิงธุรกิจหลายขั้นที่ต้องใช้หลาย tool ต่อเนื่อง (context -> query -> สรุป)
    questions = [
        "แต่ละแผนกมีพนักงานที่ยัง 'ปฏิบัติงาน' อยู่กี่คน เรียงจากมากไปน้อย",
        "พนักงาน 5 อันดับแรกที่ทำโครงการรวมมูลค่า (project_value) สูงสุดคือใคร อยู่แผนกไหน",
    ]

    msgs = [{"role": "system", "content": system}]
    for i, q in enumerate(questions, 1):
        print("\n" + "=" * 70)
        print(f"[Q{i}] ผู้ใช้: {q}")
        msgs.append({"role": "user", "content": q})
        result = await app.ainvoke({"messages": msgs}, config=config)
        msgs = result["messages"]          # Checkpointer จำ context ข้ามรอบ
        print(f"[A{i}] Agent: {msgs[-1].content}")

    # แสดงว่า Checkpointer เก็บ state ไว้จริง
    snapshot = app.get_state(config)
    print("\n" + "=" * 70)
    print(f"[Checkpointer] มี {len(snapshot.values['messages'])} messages ใน thread นี้")


if __name__ == "__main__":
    asyncio.run(main())
