from dotenv import load_dotenv
load_dotenv()
"""
nodes.py — LangGraph Execution Nodes for TerraCortex Operations Intelligence
Implements:
1. ingest_telemetry_node
2. diagnose_dtc_node (Gemini with Intelligent Offline Engineering Fallback)
3. check_sap_inventory_node (Supabase sap_inventory Live Query)
4. synthesize_dispatch_node
5. chat_reasoning_engine
"""

import os
import json
import urllib.request
import ssl
from typing import Dict, Any, List
from app.state import AgentOperationalState

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://wltoldskffnbxropaspz.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndsdG9sZHNrZmZuYnhyb3Bhc3B6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEyOTMxNzAsImV4cCI6MjEwNjg2OTE3MH0."
        "_C42_3GZZlPanu_CcUcV9eZcnXfhAge7rsllTyhhlm0"
    )
)

# Reference fleet telemetry registry for realistic ground-truth parameters

def _extract_text(resp) -> str:
    if hasattr(resp, "content"):
        c = resp.content
        if isinstance(c, list):
            parts = []
            for p in c:
                if isinstance(p, dict) and "text" in p:
                    parts.append(p["text"])
                elif hasattr(p, "text"):
                    parts.append(p.text)
                else:
                    parts.append(str(p))
            return "".join(parts).strip()
        return str(c).strip()
    return str(resp).strip()

FLEET_PROFILES: Dict[str, Dict[str, Any]] = {
    "EX-04": {
        "model": "XCMG XE4000 Mining Shovel",
        "site": "Pit 4 Bench 12B Floor (-140m RL)",
        "rock": "Hard Basalt",
        "rock_mpa": 184,
        "hydraulic_pressure": 34.8,
        "manifold_temp": 96.4,
        "cavitation_freq": 142.0,
        "vibe_rms": 4.2,
        "cmsi": 94.0,
        "component": "Hydraulic Spool Valve (Main Control Block)",
        "dtc_code": "SPN 520204 / FMI 14 (Cavitation Collapse)",
        "fault_summary": "142 Hz cavitation resonance and relief spool leakage under 34.8 MPa stall load.",
        "assigned_rig": "Mobile Rig Alpha (Heavy Hydraulics)",
        "part_target": "SAP-PARK-902-KIT",
        "downtime_est": "2.5 Hours Field Service"
    },
    "EX-17": {
        "model": "XCMG XE4000 Mining Shovel",
        "site": "Pit 2 Deep Sump (-168m RL)",
        "rock": "Quartz Basalt",
        "rock_mpa": 178,
        "hydraulic_pressure": 34.2,
        "manifold_temp": 94.1,
        "cavitation_freq": 155.0,
        "vibe_rms": 3.9,
        "cmsi": 95.2,
        "component": "Main Relief Valve Cartridge",
        "dtc_code": "SPN 520210 / FMI 08 (Abnormal Frequency Flutter)",
        "fault_summary": "155 Hz high-frequency relief flutter with acute pressure pulsation.",
        "assigned_rig": "Mobile Rig Beta (Mechanical)",
        "part_target": "SAP-VLV-RELIEF-400",
        "downtime_est": "3.0 Hours Valve Replacement"
    },
    "EX-33": {
        "model": "XCMG XE7000 Mining Excavator",
        "site": "Pit 3 East Highwall (-210m RL)",
        "rock": "Quartz Vein & Granite",
        "rock_mpa": 195,
        "hydraulic_pressure": 33.6,
        "manifold_temp": 91.8,
        "cavitation_freq": 138.0,
        "vibe_rms": 4.8,
        "cmsi": 94.4,
        "component": "Slew Pinion Gearbox",
        "dtc_code": "SPN 520198 / FMI 02 (Erratic Slew Harmonic)",
        "fault_summary": "138 Hz harmonic pinion contact shock & swing bearing torsional stress.",
        "assigned_rig": "Mobile Rig Delta (Slew Specialist)",
        "part_target": "SAP-LUBE-PURGE-08",
        "downtime_est": "4.0 Hours Inspection & Purge"
    },
    "EX-12": {
        "model": "XCMG XE7000 Mining Excavator",
        "site": "Pit 2 West Bench (-110m RL)",
        "rock": "Banded Iron Formation",
        "rock_mpa": 145,
        "hydraulic_pressure": 29.5,
        "manifold_temp": 88.5,
        "cavitation_freq": 88.0,
        "vibe_rms": 3.6,
        "cmsi": 93.8,
        "component": "Slew Bearing Drive Race",
        "dtc_code": "SPN 520190 / FMI 01 (Bearing Clearance Excessive)",
        "fault_summary": "88 Hz radial vibration on swing gear with elevated centrifugal wear.",
        "assigned_rig": "Mobile Rig Alpha (Heavy Hydraulics)",
        "part_target": "SAP-LUBE-PURGE-08",
        "downtime_est": "2.0 Hours Lubrication & Torque Check"
    },
    "EX-08": {
        "model": "XCMG XE1250 Mining Excavator",
        "site": "Pit 4 Upper Waste Dump (-60m RL)",
        "rock": "Weathered Sandstone",
        "rock_mpa": 92,
        "hydraulic_pressure": 26.5,
        "manifold_temp": 88.2,
        "cavitation_freq": 28.0,
        "vibe_rms": 2.8,
        "cmsi": 91.5,
        "component": "Hydraulic Oil Cooler Core",
        "dtc_code": "SPN 520301 / FMI 16 (Cooler Core Differential High)",
        "fault_summary": "Radiator dust clogging causing delta thermal excursion to 88.2°C.",
        "assigned_rig": "Mobile Rig Beta (Mechanical)",
        "part_target": "SAP-FLT-HYD-440",
        "downtime_est": "1.5 Hours Compressed Air Flush"
    },
    "EX-27": {
        "model": "XCMG XE2000 Mining Excavator",
        "site": "Pit 1 North Cut (+80m RL)",
        "rock": "Quartzite Vein",
        "rock_mpa": 138,
        "hydraulic_pressure": 28.1,
        "manifold_temp": 81.3,
        "cavitation_freq": 42.0,
        "vibe_rms": 2.9,
        "cmsi": 90.6,
        "component": "Boom Cylinder Piston Seal Pack",
        "dtc_code": "SPN 520144 / FMI 07 (Internal Flow Bypass Leakage)",
        "fault_summary": "Internal bypass drop 12.4 L/min across distributor O-rings.",
        "assigned_rig": "Mobile Rig Alpha (Heavy Hydraulics)",
        "part_target": "SAP-PARK-W200-HP",
        "downtime_est": "3.5 Hours Seal Replacement"
    },
    "EX-19": {
        "model": "XCMG XE950G Heavy Excavator",
        "site": "Pit 3 Overburden Terrace (-210m RL)",
        "rock": "Soft Overburden & Iron Ore",
        "rock_mpa": 128,
        "hydraulic_pressure": 31.4,
        "manifold_temp": 89.2,
        "cavitation_freq": 64.0,
        "vibe_rms": 3.4,
        "cmsi": 92.1,
        "component": "Hydraulic Return Line Filter Pack",
        "dtc_code": "SPN 520188 / FMI 18 (Filter Differential Pressure)",
        "fault_summary": "Differential backpressure surge 31.4 MPa in overburden zone.",
        "assigned_rig": "Mobile Rig Alpha",
        "part_target": "SAP-FLT-HYD-440",
        "downtime_est": "2.0 Hours Filter Replacement"
    },
    "EX-31": {
        "model": "XCMG XE700D Heavy Excavator",
        "site": "Pit 1 South Cut (+80m RL)",
        "rock": "Clay & Silt Bed",
        "rock_mpa": 36,
        "hydraulic_pressure": 21.0,
        "manifold_temp": 68.0,
        "cavitation_freq": 16.0,
        "vibe_rms": 1.4,
        "cmsi": 90.2,
        "component": "Main Hydraulic Delivery Pump",
        "dtc_code": "SPN 520150 / FMI 00 (Pressure Line Excursion)",
        "fault_summary": "Pressure line excursion 33.8 MPa detected under hard bucket stall.",
        "assigned_rig": "Mobile Rig Alpha",
        "part_target": "SAP-FLT-HYD-440",
        "downtime_est": "2.0 Hours Line Pressure Recalibration"
    }
}


def ingest_telemetry_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 1: Ingests sensor streams and maps against machine physical context."""
    trace = list(state.get("execution_trace", []))
    trace.append("ingest_telemetry_node")
    
    unit_id = state.get("unit_id", "EX-04").upper()
    profile = FLEET_PROFILES.get(unit_id, FLEET_PROFILES["EX-04"])
    
    telem = dict(state.get("telemetry", {}))
    if not telem:
        telem = {
            "model": profile["model"],
            "site": profile["site"],
            "rock_stratum": profile["rock"],
            "rock_hardness_mpa": profile["rock_mpa"],
            "hydraulic_pressure_mpa": profile["hydraulic_pressure"],
            "manifold_temp_c": profile["manifold_temp"],
            "cavitation_freq_hz": profile["cavitation_freq"],
            "vibe_rms_g": profile["vibe_rms"]
        }
    
    cmsi = state.get("cmsi_score") or profile["cmsi"]
    
    return {
        **state,
        "unit_id": unit_id,
        "telemetry": telem,
        "cmsi_score": cmsi,
        "execution_trace": trace
    }


def diagnose_dtc_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 2: Diagnostic & DTC Reasoning Node (Gemini with Domain Fallback)."""
    trace = list(state.get("execution_trace", []))
    trace.append("diagnose_dtc_node")
    
    unit_id = state.get("unit_id", "EX-04")
    profile = FLEET_PROFILES.get(unit_id, FLEET_PROFILES["EX-04"])
    telem = state.get("telemetry", {})
    cmsi = state.get("cmsi_score", profile["cmsi"])
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    findings = None
    
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""
You are an expert Chief Reliability & Mining Equipment Diagnostic Engineer (OEM Certified).
Analyze this excavator telemetry packet:
- Machine: {unit_id} ({profile['model']})
- Location: {profile['site']}
- Ground Stratum: {profile['rock']} ({profile['rock_mpa']} MPa compressive strength)
- Hydraulic Pressure: {telem.get('hydraulic_pressure_mpa')} MPa
- Manifold Temp: {telem.get('manifold_temp_c')} °C
- Vibration Peak: {telem.get('cavitation_freq_hz')} Hz
- Machine Stress Index (CMSI): {cmsi} / 100

Respond strictly in valid JSON format with keys:
"component": string (affected component),
"diagnosis": string (concise engineering root-cause explanation),
"confidence": int (85-99),
"dtc": string (SAE J1939 SPN/FMI code),
"freq": string (acoustic peak descriptor),
"rul_hours": int (remaining operating hours before functional failure),
"severity": string ("CRITICAL" | "HIGH" | "NOMINAL")
"""
            resp = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
            clean_text = resp.text.strip() if resp.text else ""
            if "```json" in clean_text:
                clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in clean_text:
                clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()
            elif "{" in clean_text and "}" in clean_text:
                clean_text = clean_text[clean_text.find("{"):clean_text.rfind("}")+1].strip()
            findings = json.loads(clean_text)
            findings["source"] = "Gemini 3.5 Flash Lite Diagnostic Agent"
        except Exception:
                pass
                
    if not findings:
        rul = (
            max(12, int(48 - (cmsi - 90) * 5)) if cmsi >= 90
            else int(180 + (85 - cmsi) * 15) if cmsi >= 70
            else int(3600 + (60 - cmsi) * 80)
        )
        sev = "CRITICAL" if cmsi >= 90 else "HIGH" if cmsi >= 70 else "NOMINAL"
        
        findings = {
            "component": profile["component"],
            "diagnosis": f"{profile['fault_summary']} Correlated with {profile['rock']} stratum compressive wear under {telem.get('hydraulic_pressure_mpa', profile['hydraulic_pressure'])} MPa continuous line pressure.",
            "confidence": 98 if cmsi >= 90 else 94 if cmsi >= 70 else 99,
            "dtc": profile["dtc_code"],
            "freq": f"{telem.get('cavitation_freq_hz', profile['cavitation_freq'])} Hz Peak Resonant Spike",
            "rul_hours": rul,
            "severity": sev,
            "source": "Mining Hydraulic Knowledge Engine (Deterministic Fallback)"
        }
        
    return {
        **state,
        "diagnosis_findings": findings,
        "execution_trace": trace
    }


PARTS_CACHE = None


def check_sap_inventory_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 3: Checks live SAP MM inventory stock in Supabase with smart caching."""
    global PARTS_CACHE
    trace = list(state.get("execution_trace", []))
    trace.append("check_sap_inventory_node")
    
    unit_id = state.get("unit_id", "EX-04")
    profile = FLEET_PROFILES.get(unit_id, FLEET_PROFILES["EX-04"])
    target_sap = profile.get("part_target", "SAP-PARK-902-KIT")
    
    parts_list = PARTS_CACHE or []
    
    if not parts_list:
        try:
            url = f"{SUPABASE_URL}/rest/v1/sap_inventory?select=*"
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}"
                }
            )
            with urllib.request.urlopen(req, context=ctx, timeout=2.5) as resp:
                db_parts = json.loads(resp.read().decode())
                for p in db_parts:
                    parts_list.append({
                        "sap_code": p.get("sap_code"),
                        "name": p.get("name"),
                        "fitment": p.get("fitment"),
                        "location": p.get("location"),
                        "on_hand": p.get("on_hand", 0),
                        "min_required": p.get("min_required", 2),
                        "unit_cost": p.get("unit_cost"),
                        "status": p.get("status")
                    })
                PARTS_CACHE = parts_list
        except Exception:
            parts_list = [
                {
                    "sap_code": "SAP-PARK-902-KIT",
                    "name": "Parker Spool Valve Seal Kit #400",
                    "fitment": "XCMG XE4000 / XE7000 Spool Block",
                    "location": "Warehouse Bay 03 (Bin B-04)",
                    "on_hand": 3,
                    "min_required": 2,
                    "unit_cost": "$2,450",
                    "status": "In Stock - Ready"
                },
                {
                    "sap_code": "SAP-VLV-RELIEF-400",
                    "name": "Main Relief Valve Cartridge 350-bar",
                    "fitment": "XCMG XE4000 Powerpack Manifold",
                    "location": "Warehouse Bay 01 (Bin A-12)",
                    "on_hand": 2,
                    "min_required": 1,
                    "unit_cost": "$4,120",
                    "status": "In Stock - Ready"
                },
                {
                    "sap_code": "SAP-LUBE-PURGE-08",
                    "name": "Slew Bearing Grease Purge Pack #EP-2",
                    "fitment": "XCMG XE7000 / XE4000 Slew Race",
                    "location": "Warehouse Bay 02 (Bin A-09)",
                    "on_hand": 12,
                    "min_required": 4,
                    "unit_cost": "$680",
                    "status": "In Stock - Ready"
                },
                {
                    "sap_code": "SAP-FLT-HYD-440",
                    "name": "High-Pressure Return Filter Element #FLT-440",
                    "fitment": "Universal Mining Fleet XCMG",
                    "location": "Warehouse Bay 02 (Bin B-18)",
                    "on_hand": 18,
                    "min_required": 6,
                    "unit_cost": "$320",
                    "status": "In Stock - Ready"
                },
                {
                    "sap_code": "SAP-PARK-W200-HP",
                    "name": "Parker Boom Wiper Pack #W-200",
                    "fitment": "XCMG XE2000 Boom Cylinder",
                    "location": "Warehouse Bay 01 (Bin C-14)",
                    "on_hand": 0,
                    "min_required": 2,
                    "unit_cost": "$1,120",
                    "status": "Stock Shortage - Reordered"
                }
            ]
            PARTS_CACHE = parts_list
            
    matched = next((p for p in parts_list if p["sap_code"] == target_sap), parts_list[0])
    
    return {
        **state,
        "spare_parts": [matched],
        "execution_trace": trace
    }


def synthesize_dispatch_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 4: Synthesizes final actionable work order draft and cabin safety directives."""
    trace = list(state.get("execution_trace", []))
    trace.append("synthesize_dispatch_node")
    
    unit_id = state.get("unit_id", "EX-04")
    profile = FLEET_PROFILES.get(unit_id, FLEET_PROFILES["EX-04"])
    diag = state.get("diagnosis_findings", {})
    parts = state.get("spare_parts", [{}])
    part = parts[0] if parts else {}
    cmsi = state.get("cmsi_score", 90.0)
    
    priority = "CRITICAL" if cmsi >= 90 else "HIGH" if cmsi >= 70 else "MEDIUM"
    
    if cmsi >= 90:
        directive = f"DERATE DIGGING ENVELOPE IMMEDIATELY: Limit breakout force by 30% and avoid full-stroke cylinder stall against {profile['rock']}. Standby for {profile['assigned_rig']} inspection."
    elif cmsi >= 70:
        directive = f"CAUTION: Elevated dynamic load observed on {diag.get('component', 'hydraulic circuit')}. Dampen swing acceleration and maintain engine RPM below 1800."
    else:
        directive = "NOMINAL ENVELOPE: Standard digging operations authorized. Maintain regular shift lubrication cycle."
        
    wo_draft = {
        "id": f"WO-AI-{unit_id.replace('-', '')}",
        "unit": unit_id,
        "model": profile["model"],
        "dtc": diag.get("dtc", profile["dtc_code"]),
        "diagnosis": diag.get("diagnosis", profile["fault_summary"]),
        "part_name": part.get("name", "OEM Service Component"),
        "part_sap_code": part.get("sap_code", "SAP-GEN-KIT"),
        "inventory_location": part.get("location", "Warehouse Bay 01"),
        "part_stock": f"{part.get('on_hand', 1)} Units on Shelf ({part.get('status', 'Available')})",
        "assigned_rig": profile.get("assigned_rig", "Mobile Rig Alpha"),
        "estimated_downtime": profile.get("downtime_est", "2.0 Hours"),
        "priority": priority,
        "operator_alert": directive,
        "confidence": diag.get("confidence", 95)
    }
    
    return {
        **state,
        "work_order_draft": wo_draft,
        "execution_trace": trace
    }


def chat_reasoning_engine(query: str, state: AgentOperationalState) -> str:
    """Node 5 / Endpoint: Conversational Copilot Q&A for the fleet reliability superintendent."""
    unit_id = state.get("unit_id", "EX-04")
    diag = state.get("diagnosis_findings", {})
    wo = state.get("work_order_draft", {})
    telem = state.get("telemetry", {})
    cmsi = state.get("cmsi_score", 90.0)
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""You are the TerraCortex Mining Copilot AI, assisting a Heavy Excavator Fleet Reliability Superintendent.
Current Machine Operational Context:
- Machine Unit: {unit_id} ({wo.get('model', 'Mining Shovel')})
- Machine Stress Index (CMSI): {cmsi} / 100
- Technical Diagnosis: {diag.get('diagnosis')}
- SAE DTC Code: {diag.get('dtc')}
- Remaining Useful Life (RUL): {diag.get('rul_hours')} Operating Hours
- SAP MM Spare Part: {wo.get('part_name')} [{wo.get('part_sap_code')}] - {wo.get('part_stock')} at {wo.get('inventory_location')}
- Assigned Rig: {wo.get('assigned_rig')} (Est Downtime: {wo.get('estimated_downtime')})
- In-Cab Directive: {wo.get('operator_alert')}

User Message: "{query}"

Guidelines:
1. If the user greets (e.g. "hai", "halo", "selamat pagi", "hello"), respond warmly in Indonesian as TerraCortex Mining Copilot, stating unit {unit_id} current condition ({cmsi} CMSI Alert), and asking how you can help.
2. If asking technical, operational, risk, part, or downtime questions, answer authoritatively, concisely, and practically from the perspective of an expert OEM Mining Reliability Engineer.
3. Support both Indonesian and English seamlessly.
4. Always format your response with clean Markdown: use clear line breaks between paragraphs, bold key terms (**term**), and put numbered points (1., 2., 3.) or bullet points on separate lines for maximum readability.
"""
            resp = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )
            if resp.text:
                return resp.text.strip()
        except Exception as e:
            pass
            
    q_lower = query.lower()
    if "risk" in q_lower or "berbahaya" in q_lower or "bahaya" in q_lower or "failure" in q_lower:
        return (
            f"Operating risk for {unit_id}: Continued high-load digging against {telem.get('rock_stratum', 'Hard Basalt')} "
            f"will accelerate micro-pitting in the {diag.get('component', 'hydraulic spool valve')}. "
            f"Estimated RUL is currently {diag.get('rul_hours', 28)} operating hours. "
            f"Recommendation: Reduce breakout pressure by 30% and dispatch {wo.get('assigned_rig')} before shift handover."
        )
    elif "spare part" in q_lower or "part" in q_lower or "cadang" in q_lower or "stok" in q_lower:
        return (
            f"Inventory Check for {unit_id}: Required kit is {wo.get('part_name')} (SAP Code: {wo.get('part_sap_code')}). "
            f"Current status: {wo.get('part_stock')} located at {wo.get('inventory_location')}. No supply-chain bottleneck detected."
        )
    elif "downtime" in q_lower or "jam" in q_lower or "lama" in q_lower or "repair" in q_lower:
        return (
            f"Maintenance downtime estimate: {wo.get('estimated_downtime')} allocated to {wo.get('assigned_rig')}. "
            f"Performing this preventative valve kit swap now prevents an unplanned 36-hour catastrophic powerpack rebuild."
        )
    elif "hai" in q_lower or "halo" in q_lower or "hello" in q_lower:
        return (
            f"Halo! Saya TerraCortex Copilot. Unit {unit_id} saat ini termonitor dalam status CMSI Alert ({cmsi}/100) "
            f"dengan indikasi pada {diag.get('component', 'sistem hidrolik')}. Ada yang bisa saya bantu terkait risiko, suku cadang, atau jadwal servis?"
        )
    else:
        return (
            f"Diagnostic Summary for {unit_id}: {diag.get('diagnosis')} "
            f"SAE DTC Code {diag.get('dtc')} logged. {wo.get('assigned_rig')} is pre-staged with {wo.get('part_name')}. "
            f"Direct in-cab instruction: {wo.get('operator_alert')}"
        )
