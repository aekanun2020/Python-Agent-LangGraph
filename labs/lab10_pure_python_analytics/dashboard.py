"""Render a standalone security dashboard from the agent's aggregate JSON report."""

from __future__ import annotations

import json
from pathlib import Path


def validate_report(data: dict) -> list[str]:
    """Return missing analytical-contract fields; an empty list means valid."""
    required = [
        "parser", "total_records", "parse_quality", "event_time_min", "event_time_max",
        "bytes_sent", "bytes_received", "top_actions", "top_applications", "top_policies",
        "top_source_zones", "top_destination_zones", "protocols", "top_source_talkers",
        "top_destination_talkers", "traffic_by_source_zone", "traffic_by_destination_zone",
        "traffic_by_application", "session_end_reasons", "top_source_users", "nat",
    ]
    missing = [name for name in required if name not in data]
    nat_required = [
        "nat_sessions", "source_nat_sessions", "destination_nat_sessions",
        "top_source_translations", "top_destination_translations",
    ]
    if isinstance(data.get("nat"), dict):
        missing.extend(f"nat.{name}" for name in nat_required if name not in data["nat"])
    else:
        missing.append("nat must be an object")

    if not isinstance(data.get("parse_quality"), dict):
        missing.append("parse_quality must be an object of status counts")
    elif sum(value for value in data["parse_quality"].values() if isinstance(value, int)) != data.get("total_records"):
        missing.append("parse_quality counts must sum to total_records")
    if not isinstance(data.get("total_records"), int) or data.get("total_records", 0) <= 0:
        missing.append("total_records must be a positive integer")
    if not data.get("event_time_min") or not data.get("event_time_max"):
        missing.append("event_time_min and event_time_max must be non-null")
    for field in ("bytes_sent", "bytes_received"):
        if not isinstance(data.get(field), int) or data.get(field, 0) < 0:
            missing.append(f"{field} must be a non-negative integer")

    row_contracts = {
        "top_actions": {"value", "count"},
        "top_applications": {"value", "count"},
        "top_policies": {"value", "count"},
        "top_source_zones": {"value", "count"},
        "top_destination_zones": {"value", "count"},
        "protocols": {"value", "count"},
        "session_end_reasons": {"value", "count"},
        "top_source_talkers": {"source_ip", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
        "top_destination_talkers": {"destination_ip", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
        "traffic_by_source_zone": {"source_zone", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
        "traffic_by_destination_zone": {"destination_zone", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
        "traffic_by_application": {"application", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
        "top_source_users": {"source_user", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
    }
    for field, keys in row_contracts.items():
        rows = data.get(field)
        if not isinstance(rows, list):
            missing.append(f"{field} must be a list")
        elif rows and not keys.issubset(rows[0]):
            missing.append(f"{field} rows require {sorted(keys)}")
        elif rows:
            dimension = next((key for key in keys if key not in {
                "count", "sessions", "bytes_sent", "bytes_received", "total_bytes"
            }), None)
            if dimension and any(row.get(dimension) in (None, "") for row in rows):
                missing.append(f"{field}.{dimension} must be non-null and non-blank")
    for field in (
        "top_actions", "top_applications", "top_policies", "top_source_zones",
        "top_destination_zones", "protocols", "session_end_reasons",
        "top_source_talkers", "top_destination_talkers", "traffic_by_source_zone",
        "traffic_by_destination_zone", "traffic_by_application",
    ):
        if isinstance(data.get(field), list) and not data[field]:
            missing.append(f"{field} cannot be empty for a non-empty traffic dataset")

    nat_rows = {
        "top_source_translations": {"source_ip", "source_translated_ip", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
        "top_destination_translations": {"destination_ip", "destination_translated_ip", "sessions", "bytes_sent", "bytes_received", "total_bytes"},
    }
    if isinstance(data.get("nat"), dict):
        for field, keys in nat_rows.items():
            rows = data["nat"].get(field)
            if not isinstance(rows, list):
                missing.append(f"nat.{field} must be a list")
            elif rows and not keys.issubset(rows[0]):
                missing.append(f"nat.{field} rows require {sorted(keys)}")

    parser_id = str(data.get("parser", {}).get("id", "")).lower()
    if "paloalto" in parser_id or "panos" in parser_id:
        action_values = {str(row.get("value", "")).lower() for row in data.get("top_actions", [])}
        protocol_values = {str(row.get("value", "")).lower() for row in data.get("protocols", [])}
        allowed_actions = {
            "allow", "deny", "drop", "reset-both", "reset-client", "reset-server",
            "block-url", "block-continue", "continue", "alert", "override-lockout",
            "override", "block",
        }
        allowed_protocols = {"tcp", "udp", "icmp", "icmp6", "esp", "gre", "sctp", "ip"}
        unexpected_actions = sorted(action_values - allowed_actions)
        unexpected_protocols = sorted(protocol_values - allowed_protocols)
        if unexpected_actions:
            missing.append(f"top_actions contains non-action values: {unexpected_actions}")
        if unexpected_protocols:
            missing.append(f"protocols contains non-protocol values: {unexpected_protocols}")
    return missing


def render_dashboard(data: dict, target: Path) -> Path:
    missing = validate_report(data)
    if missing:
        raise ValueError("report misses required fields: " + ", ".join(missing))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:">
<title>Pure Python Agent · Security Analytics</title><style>
:root{color-scheme:dark;--bg:#07121b;--card:#0d1c28;--line:#203747;--text:#edf7fb;--muted:#8fa6b3;--cyan:#43e4cb;--blue:#4ba5ff;--red:#ff6b7d;--amber:#ffc35b}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 90% 0,#0d3140 0,transparent 28%),var(--bg);color:var(--text);font:14px/1.45 Inter,system-ui,sans-serif}.wrap{max-width:1440px;margin:auto;padding:32px}.top{display:flex;justify-content:space-between;gap:18px;align-items:end;margin-bottom:22px}.eyebrow{color:var(--cyan);font-size:11px;letter-spacing:.16em;text-transform:uppercase}.top h1{margin:6px 0 4px;font-size:30px}.muted{color:var(--muted)}.badge{border:1px solid #285065;padding:8px 11px;font:12px ui-monospace,monospace;color:var(--cyan)}.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.card{background:linear-gradient(145deg,#102330,var(--card));border:1px solid var(--line);padding:17px}.kpi b{display:block;font:650 25px ui-monospace,monospace;margin:7px 0}.label{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}h2{font-size:17px;margin:27px 0 11px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}h3{font-size:13px;margin:0 0 14px}.bars{display:grid;gap:9px}.bar{display:grid;grid-template-columns:minmax(100px,1fr) 2fr 84px;gap:9px;align-items:center}.name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font:12px ui-monospace,monospace}.track{height:8px;background:#19303e}.fill{height:100%;background:linear-gradient(90deg,var(--cyan),var(--blue))}.num{text-align:right;font:12px ui-monospace,monospace}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:9px;border-bottom:1px solid var(--line);text-align:right;font:12px ui-monospace,monospace}.table th:first-child,.table td:first-child{text-align:left}.table th{color:var(--muted);font-size:10px;text-transform:uppercase}.signals{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px}.signal{border-left:2px solid var(--amber)}footer{margin-top:25px;color:var(--muted);font-size:11px;border-top:1px solid var(--line);padding-top:14px}@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid,.grid3,.signals{grid-template-columns:1fr}}@media(max-width:520px){.wrap{padding:18px}.kpis{grid-template-columns:1fr}.top{align-items:start;flex-direction:column}}
</style></head><body><main class="wrap"><header class="top"><div><div class="eyebrow">Autonomous batch analytics · no LangGraph</div><h1>PAN-OS Traffic Intelligence</h1><div class="muted" id="range"></div></div><div class="badge" id="parser"></div></header><section class="kpis" id="kpis"></section><section class="signals" id="signals"></section><h2>Traffic concentration</h2><section class="grid"><article class="card"><h3>Top source talkers</h3><div class="bars" id="sources"></div></article><article class="card"><h3>Top destination talkers</h3><div class="bars" id="destinations"></div></article><article class="card"><h3>Traffic by application</h3><div class="bars" id="apps"></div></article><article class="card"><h3>Traffic by source zone</h3><div class="bars" id="zones"></div></article></section><h2>Session behavior</h2><section class="grid3"><article class="card"><h3>Actions</h3><div class="bars" id="actions"></div></article><article class="card"><h3>End reasons</h3><div class="bars" id="reasons"></div></article><article class="card"><h3>Source users</h3><div class="bars" id="users"></div></article></section><h2>Observed NAT</h2><article class="card"><table class="table"><thead><tr><th>Original → translated</th><th>Sessions</th><th>Sent</th><th>Received</th><th>Total</th></tr></thead><tbody id="nat"></tbody></table></article><footer>Aggregates produced by a Pure Python ReAct agent using Security Skill MCP and Spark/HDFS MCP. Raw events remain in HDFS.</footer></main><script>
const d=__DATA__;const q=s=>document.querySelector(s);const esc=v=>String(v??'—').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));const n=v=>new Intl.NumberFormat('en-US').format(Number(v)||0);const bytes=v=>{v=Number(v)||0;for(const [u,x] of [['TB',1e12],['GB',1e9],['MB',1e6],['KB',1e3]])if(v>=x)return(v/x).toFixed(v/x>=100?0:v/x>=10?1:2)+' '+u;return n(v)+' B'};const pct=v=>(100*(Number(v)||0)/Math.max(Number(d.total_records)||1,1)).toFixed(1)+'%';q('#range').textContent=`${d.event_time_min} → ${d.event_time_max}`;q('#parser').textContent=`${d.parser.id} v${d.parser.version}`;const deny=(d.top_actions||[]).filter(x=>['deny','drop'].includes(x.value)).reduce((s,x)=>s+x.count,0),total=d.bytes_sent+d.bytes_received,nat=d.nat||{};q('#kpis').innerHTML=[['Sessions',n(d.total_records),'parsed '+n(d.parse_quality.parsed||0)],['Traffic',bytes(total),bytes(d.bytes_sent)+' sent'],['Denied / dropped',n(deny),pct(deny)],['Source NAT',n(nat.source_nat_sessions),pct(nat.source_nat_sessions)],['User-ID',n((d.top_source_users||[]).reduce((s,x)=>s+(x.sessions||0),0)),'top identified sessions']].map(x=>`<article class="card kpi"><span class="label">${x[0]}</span><b>${x[1]}</b><span class="muted">${x[2]||''}</span></article>`).join('');const unknown=(d.top_applications||[]).filter(x=>['unknown-tcp','not-applicable'].includes(x.value)).reduce((s,x)=>s+x.count,0),aged=(d.session_end_reasons||[]).find(x=>x.value==='aged-out')?.count||0;q('#signals').innerHTML=[[deny,'blocked/denied sessions'],[unknown,'unidentified applications'],[aged,'aged-out sessions']].map(x=>`<article class="card signal"><b>${n(x[0])}</b><div class="muted">${x[1]} · ${pct(x[0])}</div></article>`).join('');function bars(sel,rows,label,value,fmt=bytes){rows=rows||[];const max=Math.max(1,...rows.map(value));q(sel).innerHTML=rows.slice(0,10).map(r=>`<div class="bar"><span class="name" title="${esc(label(r))}">${esc(label(r))}</span><span class="track"><div class="fill" style="width:${100*value(r)/max}%"></div></span><span class="num">${fmt(value(r))}</span></div>`).join('')||'<span class="muted">No data</span>'}bars('#sources',d.top_source_talkers,r=>r.source_ip,r=>r.total_bytes);bars('#destinations',d.top_destination_talkers,r=>r.destination_ip,r=>r.total_bytes);bars('#apps',d.traffic_by_application,r=>r.application,r=>r.total_bytes);bars('#zones',d.traffic_by_source_zone,r=>r.source_zone,r=>r.total_bytes);bars('#actions',d.top_actions,r=>r.value,r=>r.count,n);bars('#reasons',d.session_end_reasons,r=>r.value,r=>r.count,n);bars('#users',d.top_source_users,r=>r.source_user,r=>r.sessions,n);q('#nat').innerHTML=(nat.top_source_translations||[]).slice(0,15).map(r=>`<tr><td>${esc(r.source_ip)} → ${esc(r.source_translated_ip)}</td><td>${n(r.sessions)}</td><td>${bytes(r.bytes_sent)}</td><td>${bytes(r.bytes_received)}</td><td>${bytes(r.total_bytes)}</td></tr>`).join('')||'<tr><td colspan="5">No source NAT observed</td></tr>';
</script></body></html>'''
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template.replace("__DATA__", payload), encoding="utf-8")
    return target
