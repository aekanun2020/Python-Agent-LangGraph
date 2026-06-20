"""
MCP Server — Seismic & Insurance Analytics (Streamable HTTP)
============================================================
ต่อยอดจากหลักสูตรที่ 1 (Implementing MCP Server, PART 2: แบบฝึกหัดที่ 5-6)

เซิร์ฟเวอร์ MCP จำลองโดเมน FireExit (Seismic Insurance) สำหรับใช้เป็น "tool backend"
ของ LangGraph Agent ในหลักสูตรที่ 2 (Lab 8)

Transport: Streamable HTTP — endpoint เดียว /mcp (มาตรฐาน MCP ปัจจุบัน, spec 2025-03-26)
รันด้วย: python src/mcp_server_seismic.py   (ค่าเริ่มต้น port 9000)

หมายเหตุ: ผู้เรียนสามารถเปลี่ยนไปชี้ MCP Server จริงของหลักสูตรที่ 1
(MSSQL 9000, RAG 8000, Seismic) ได้โดยแก้ค่า MCP_SERVER_URL ใน agent
"""
from fastmcp import FastMCP

mcp = FastMCP("seismic-insurance")

# ---- ฐานข้อมูล asset ที่เอาประกัน (จำลองแทน MSSQL จากหลักสูตรที่ 1) ----
ASSETS = [
    {"asset_id": "A001", "name": "FireExit Tower A", "city": "Chiang Mai",
     "lat": 18.7883, "lon": 98.9853, "sum_insured": 50_000_000},
    {"asset_id": "A002", "name": "FireExit Warehouse B", "city": "Chiang Rai",
     "lat": 19.9105, "lon": 99.8406, "sum_insured": 30_000_000},
    {"asset_id": "A003", "name": "FireExit Plant C", "city": "Mae Hong Son",
     "lat": 19.3013, "lon": 97.9685, "sum_insured": 80_000_000},
]

# ---- ข้อมูลแผ่นดินไหวล่าสุด (จำลองแทน USGS FDSN / TMD จากหลักสูตรที่ 1) ----
RECENT_QUAKES = [
    {"event_id": "us7000x1", "magnitude": 6.2, "city": "Chiang Rai",
     "lat": 19.95, "lon": 99.83, "depth_km": 10},
    {"event_id": "us7000x2", "magnitude": 4.1, "city": "Chiang Mai",
     "lat": 18.80, "lon": 98.98, "depth_km": 8},
]


@mcp.tool
def list_insured_assets() -> list[dict]:
    """คืนรายการ asset ทั้งหมดที่บริษัทเอาประกันไว้ (asset_id, ชื่อ, เมือง, ทุนประกัน)."""
    return ASSETS


@mcp.tool
def get_recent_earthquakes(min_magnitude: float = 0.0) -> list[dict]:
    """ดึงเหตุการณ์แผ่นดินไหวล่าสุด กรองด้วยขนาดขั้นต่ำ (min_magnitude)."""
    return [q for q in RECENT_QUAKES if q["magnitude"] >= min_magnitude]


@mcp.tool
def calculate_parametric_payout(asset_id: str, magnitude: float) -> dict:
    """
    คำนวณ parametric payout ของ asset หนึ่ง ๆ ตามขนาดแผ่นดินไหว (magnitude).

    ตารางจ่ายแบบ parametric:
      magnitude >= 6.0  -> จ่าย 100% ของทุนประกัน
      magnitude >= 5.0  -> จ่าย 50%
      magnitude >= 4.0  -> จ่าย 10%
      ต่ำกว่านั้น        -> ไม่จ่าย
    """
    asset = next((a for a in ASSETS if a["asset_id"] == asset_id), None)
    if asset is None:
        return {"error": f"ไม่พบ asset_id {asset_id}"}
    if magnitude >= 6.0:
        pct = 1.0
    elif magnitude >= 5.0:
        pct = 0.5
    elif magnitude >= 4.0:
        pct = 0.1
    else:
        pct = 0.0
    payout = int(asset["sum_insured"] * pct)
    return {
        "asset_id": asset_id,
        "asset_name": asset["name"],
        "magnitude": magnitude,
        "payout_pct": pct,
        "sum_insured": asset["sum_insured"],
        "payout_amount": payout,
    }


if __name__ == "__main__":
    # Streamable HTTP transport — endpoint /mcp (เหมือนหลักสูตรที่ 1)
    mcp.run(transport="http", host="127.0.0.1", port=9000)
