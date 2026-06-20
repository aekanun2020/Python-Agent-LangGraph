"""
Lab 8 (Extension) — LangGraph Agent ต่อ MCP MSSQL Server *จริง* ของหลักสูตรที่ 1
================================================================================
ใช้โค้ด LangGraph Agent ตัวเดิม (State/Node/Edge/Checkpointer + MCP Tool Discovery)
แต่เปลี่ยน MCP_SERVER_URL ไปชี้ MCP MSSQL Server จริง (ผ่าน ngrok) โดยไม่แก้สถาปัตยกรรม

แสดงให้เห็นว่า Agent กับ Tools ถูก decouple ผ่านมาตรฐาน MCP:
เปลี่ยนแค่ URL ก็สลับจาก server จำลอง -> server จริง ได้ทันที

ฐานข้อมูลจริง: TestDB (MS SQL Server 2022) — โดเมน HR (employees + projects/skills/...)
Agent ตอบ business question โดยเรียก get_database_context -> execute_query_tool เอง

รัน: python agent_mssql_demo.py
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

# ชี้ไป MCP MSSQL Server จริงของหลักสูตรที่ 1 (override ผ่าน env ได้)
MCP_SERVER_URL = os.environ.get(
    "MCP_MSSQL_URL", "https://9f9a-184-22-55-183.ngrok-free.app/mcp"
)
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6")


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0,
    )


async def build_graph():
    client = MultiServerMCPClient(
        {"mssql": {"url": MCP_SERVER_URL, "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    print(f"[MCP] ค้นพบ {len(tools)} tools จาก MSSQL จริง: {[t.name for t in tools]}")

    llm_with_tools = build_llm().bind_tools(tools)

    def call_model(state: AgentState):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    tool_node = ToolNode(tools)

    def should_continue(state: AgentState):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "call_model")
    graph.add_conditional_edges("call_model", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "call_model")

    return graph.compile(checkpointer=MemorySaver())


async def main():
    app = await build_graph()
    config = {"configurable": {"thread_id": "mssql-business-1"}}

    system = (
        "คุณคือนักวิเคราะห์ข้อมูลของบริษัท ตอบคำถามเชิงธุรกิจจากฐานข้อมูล MS SQL Server "
        "ขั้นตอน: เรียก get_database_context ก่อนเสมอเพื่อดู schema แล้วจึงเขียน T-SQL "
        "ที่ถูกต้อง (ใช้ TOP ไม่ใช่ LIMIT) ส่งให้ execute_query_tool ตอบเป็นภาษาไทย "
        "พร้อมตารางสรุปและข้อสังเกตเชิงธุรกิจ"
    )

    questions = [
        "แต่ละแผนก (department) มีพนักงานที่ยัง 'ปฏิบัติงาน' อยู่กี่คน เรียงจากมากไปน้อย",
        "พนักงาน 5 อันดับแรกที่ทำโครงการรวมมูลค่า (project_value) สูงสุดคือใคร อยู่แผนกไหน",
    ]

    msgs = [{"role": "system", "content": system}]
    for i, q in enumerate(questions, 1):
        print("\n" + "=" * 70)
        print(f"[Q{i}] ผู้ใช้: {q}")
        msgs.append({"role": "user", "content": q})
        result = await app.ainvoke({"messages": msgs}, config=config)
        msgs = result["messages"]
        print(f"[A{i}] Agent: {msgs[-1].content}")

    snapshot = app.get_state(config)
    print("\n" + "=" * 70)
    print(f"[Checkpointer] มี {len(snapshot.values['messages'])} messages ใน thread นี้")


if __name__ == "__main__":
    asyncio.run(main())
