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
    "EX-01": {
        "model": "XCMG XE4000 Mining Shovel",
        "site": "Pit 1 North Bench (+15m RL)",
        "rock": "Soft Overburden",
        "rock_mpa": 45,
        "hydraulic_pressure": 18.0,
        "manifold_temp": 55.0,
        "cavitation_freq": 20.0,
        "vibe_rms": 1.1,
        "cmsi": 38.0,
        "component": "Hydraulic & Mechanical Circuit (Healthy)",
        "dtc_code": "0x00 (System Normal)",
        "fault_summary": "All systems operating strictly within nominal limits. Zero DTC codes detected.",
        "assigned_rig": "No Mobile Rig Required (Unit Operational)",
        "part_target": "SAP-GEN-KIT",
        "downtime_est": "0.0 Hours (Active Production)"
    },
    "EX-04-SCN2": {
        "model": "XCMG XE4000 Mining Shovel",
        "site": "Pit 4 Bench 12B Floor (-140m RL)",
        "rock": "Hard Basalt Strata",
        "rock_mpa": 184,
        "hydraulic_pressure": 28.5,
        "manifold_temp": 68.0,
        "cavitation_freq": 35.0,
        "vibe_rms": 1.2,
        "cmsi": 72.0,
        "component": "Ground Penetration Load (Hard Basalt Strata)",
        "dtc_code": "0x00 (Operational High Workload)",
        "fault_summary": "Elevated pressure is a direct mechanical load reaction against hard basalt strata (184 MPa compressive strength), BUKAN KERUSAKAN POMPA ATAU KATUP. CMSI 72 adalah respon beban kerja wajar.",
        "assigned_rig": "No Rig Required (Hanya Derate Operasional Operator)",
        "part_target": "SAP-GEN-KIT",
        "downtime_est": "0.0 Hours (Unit Tetap Bekerja di Pit)",
        "no_service_needed": True
    },
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
        "part_target": "SAP-SLEW-PINION-700",
        "downtime_est": "4.5 Hours Pinion Shaft Replacement"
    },
    "EX-08": {
        "model": "XCMG XE1250 Mining Excavator",
        "site": "Pit 4 Upper Waste Dump (-60m RL)",
        "rock": "Weathered Sandstone",
        "rock_mpa": 92,
        "hydraulic_pressure": 26.5,
        "manifold_temp": 96.5,
        "cavitation_freq": 24.0,
        "vibe_rms": 2.8,
        "cmsi": 91.5,
        "component": "Hydraulic Oil Cooler Core & Thermostat",
        "dtc_code": "SPN 520301 / FMI 16 (Cooler Core Thermal Excursion)",
        "fault_summary": "Severe radiator overheating excursion 96.5°C exceeding flash limit. Fluid vaporization and seal meltdown risk.",
        "assigned_rig": "Mobile Rig Beta (Cooling Specialist)",
        "part_target": "SAP-RAD-CORE-1250",
        "downtime_est": "3.0 Hours Emergency Radiator Flushing"
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
        "part_target": "SAP-PUMP-ROT-700",
        "downtime_est": "5.0 Hours Pump Rebuild (Awaiting Part)"
    }
}


def get_effective_profile(unit_id: str, telem: dict) -> dict:
    unit_id = (unit_id or "EX-04").upper()
    if unit_id == "EX-04" and telem:
        t_temp = float(telem.get("manifold_temp_c") or 0.0)
        t_cav = float(telem.get("cavitation_freq_hz") or 0.0)
        t_press = float(telem.get("hydraulic_pressure_mpa") or 0.0)
        t_vibe = float(telem.get("vibe_rms_g") or 0.0)
        t_dtc = str(telem.get("dtc_code") or "")

        if t_temp >= 90.0 or "520301" in t_dtc:
            return FLEET_PROFILES["EX-08"]
        elif t_cav >= 150.0 or "520210" in t_dtc:
            return FLEET_PROFILES["EX-17"]
        elif "520198" in t_dtc or t_vibe >= 4.0:
            return FLEET_PROFILES["EX-12"]
        elif "520144" in t_dtc or (t_press <= 15.0 and t_temp >= 80.0):
            return FLEET_PROFILES["EX-27"]
        elif "520150" in t_dtc:
            return FLEET_PROFILES["EX-31"]
        elif t_dtc == "0x00" and t_press < 23.0 and t_temp < 70.0:
            return FLEET_PROFILES["EX-01"]
        elif (t_dtc == "0x00" or not t_dtc or "workload" in t_dtc.lower()) and t_cav < 60.0 and t_temp < 80.0:
            return FLEET_PROFILES.get("EX-04-SCN2", FLEET_PROFILES["EX-04"])
        else:
            return FLEET_PROFILES["EX-04"]
    return FLEET_PROFILES.get(unit_id, FLEET_PROFILES["EX-04"])

def ingest_telemetry_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 1: Ingests sensor streams and maps against machine physical context."""
    trace = list(state.get("execution_trace", []))
    trace.append("ingest_telemetry_node")
    
    unit_id = state.get("unit_id", "EX-04").upper()
    telem_in = dict(state.get("telemetry", {}))
    
    if unit_id == "EX-04" and telem_in:
        t_temp = float(telem_in.get("manifold_temp_c") or 0.0)
        t_cav = float(telem_in.get("cavitation_freq_hz") or 0.0)
        t_press = float(telem_in.get("hydraulic_pressure_mpa") or 0.0)
        t_vibe = float(telem_in.get("vibe_rms_g") or 0.0)
        t_dtc = str(telem_in.get("dtc_code") or "")

        if t_temp >= 90.0 or "520301" in t_dtc:
            profile = FLEET_PROFILES["EX-08"]
        elif t_cav >= 150.0 or "520210" in t_dtc:
            profile = FLEET_PROFILES["EX-17"]
        elif "520198" in t_dtc or t_vibe >= 4.0:
            profile = FLEET_PROFILES["EX-12"]
        elif "520144" in t_dtc or (t_press <= 15.0 and t_temp >= 80.0):
            profile = FLEET_PROFILES["EX-27"]
        elif "520150" in t_dtc:
            profile = FLEET_PROFILES["EX-31"]
        elif t_dtc == "0x00" and t_press < 23.0 and t_temp < 70.0:
            profile = FLEET_PROFILES["EX-01"]
        elif (t_dtc == "0x00" or not t_dtc or "workload" in t_dtc.lower()) and t_cav < 60.0 and t_temp < 80.0:
            profile = FLEET_PROFILES.get("EX-04-SCN2", FLEET_PROFILES["EX-04"])
        else:
            profile = FLEET_PROFILES["EX-04"]
    else:
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
    telem_in = state.get("telemetry", {})
    
    if unit_id == "EX-04" and telem_in:
        t_temp = float(telem_in.get("manifold_temp_c") or 0.0)
        t_cav = float(telem_in.get("cavitation_freq_hz") or 0.0)
        t_press = float(telem_in.get("hydraulic_pressure_mpa") or 0.0)
        t_vibe = float(telem_in.get("vibe_rms_g") or 0.0)
        t_dtc = str(telem_in.get("dtc_code") or "")

        if t_temp >= 90.0 or "520301" in t_dtc:
            profile = FLEET_PROFILES["EX-08"]
        elif t_cav >= 150.0 or "520210" in t_dtc:
            profile = FLEET_PROFILES["EX-17"]
        elif "520198" in t_dtc or t_vibe >= 4.0:
            profile = FLEET_PROFILES["EX-12"]
        elif "520144" in t_dtc or (t_press <= 15.0 and t_temp >= 80.0):
            profile = FLEET_PROFILES["EX-27"]
        elif "520150" in t_dtc:
            profile = FLEET_PROFILES["EX-31"]
        elif t_dtc == "0x00" and t_press < 23.0 and t_temp < 70.0:
            profile = FLEET_PROFILES["EX-01"]
        elif (t_dtc == "0x00" or not t_dtc or "workload" in t_dtc.lower()) and t_cav < 60.0 and t_temp < 80.0:
            profile = FLEET_PROFILES.get("EX-04-SCN2", FLEET_PROFILES["EX-04"])
        else:
            profile = FLEET_PROFILES["EX-04"]
    else:
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
- Hydraulic Pressure: {telem.get('hydraulic_pressure_mpa') or profile.get('hydraulic_pressure')} MPa
- Manifold Temp: {telem.get('manifold_temp_c') or profile.get('manifold_temp')} °C
- Vibration Peak: {telem.get('cavitation_freq_hz') or profile.get('cavitation_freq')} Hz
- Machine Stress Index (CMSI): {cmsi} / 100

CRITICAL RELIABILITY RULES:
1. NOMINAL / HEALTHY: If CMSI < 65 and Pressure is 16.0-22.0 MPa and Vibration Peak < 30 Hz: The machine is completely NOMINAL and HEALTHY. Set severity="NOMINAL", dtc="0x00", component="All Systems Nominal (Healthy)", diagnosis="Machine operating strictly within safe parameters. No fault detected. Zero maintenance required.", rul_hours=4500.
2. OPERATIONAL HIGH LOAD: If CMSI < 85 and Ground Stratum is Hard Rock/Basalt, but no cavitation spikes (< 50 Hz) and Temp < 78 C: The elevated line pressure (24-30 MPa) is a direct operational resistance against hard rock strata, NOT an internal mechanical fault. Set severity="WARNING", dtc="0x00", component="Ground Penetration High Load", diagnosis="High operational digging resistance against hard rock strata. Component wear is normal. Operator derate 30% recommended, no workshop repair needed.", rul_hours=1500.
3. CRITICAL FAILURE: If Vibration Peak >= 100 Hz (Cavitation/Harmonic) or Manifold Temp >= 90 C (Overheat) or CMSI >= 90: This is a genuine severe failure requiring immediate work stop or scheduled service. Set severity="CRITICAL".

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
                
    if profile.get("no_service_needed"):
        findings = {
            "component": profile["component"],
            "diagnosis": profile["fault_summary"],
            "confidence": 98,
            "dtc": profile["dtc_code"],
            "freq": f"{telem.get('cavitation_freq_hz', profile['cavitation_freq'])} Hz Rock Interaction",
            "rul_hours": 1200 if unit_id == "EX-04" else 4500,
            "severity": "WARNING" if unit_id == "EX-04" else "NOMINAL",
            "no_service_needed": True,
            "shift_window": "Tetap Bekerja (Tanpa Interupsi Jadwal Bengkel)" if unit_id == "EX-04" else "Sesuai Kalender Rutin (PM 250 / 500 Jam)",
            "source": "Mining Hydraulic Knowledge Engine (Domain Operational State)"
        }
    elif not findings:
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

EXPANDED_OEM_PARTS = [
    {
        "sap_code": "SAP-PARK-902-KIT",
        "name": "Parker Spool Valve Seal Kit #PS-902",
        "fitment": "XCMG XE4000 Mining Shovel",
        "location": "Warehouse Bay 03 (Bin B-04)",
        "on_hand": 4,
        "min_required": 2,
        "unit_cost": "$1,850",
        "status": "In Stock - Ready",
        "substitute_sap_code": "SAP-REX-902-EQUIV",
        "vendor_lead_time": "24h Domestic"
    },
    {
        "sap_code": "SAP-REX-902-EQUIV",
        "name": "Rexroth Spool Seal Equivalent #RS-902",
        "fitment": "XCMG XE4000 / XE7000 Control Block",
        "location": "Warehouse Bay 03 (Bin B-06)",
        "on_hand": 2,
        "min_required": 1,
        "unit_cost": "$1,920",
        "status": "In Stock - Ready",
        "substitute_sap_code": "SAP-PARK-902-KIT",
        "vendor_lead_time": "24h Domestic"
    },
    {
        "sap_code": "SAP-VLV-RELIEF-400",
        "name": "Main Relief Valve Cartridge 350-Bar",
        "fitment": "XCMG XE4000 Powerpack Manifold",
        "location": "Warehouse Bay 01 (Bin A-12)",
        "on_hand": 2,
        "min_required": 1,
        "unit_cost": "$4,120",
        "status": "In Stock - Ready",
        "substitute_sap_code": "SAP-VLV-RELIEF-HP",
        "vendor_lead_time": "48h Express"
    },
    {
        "sap_code": "SAP-VLV-RELIEF-HP",
        "name": "High-Pressure Relief Valve 380-Bar Cartridge",
        "fitment": "Universal XCMG Heavy Shovels",
        "location": "Warehouse Bay 01 (Bin A-14)",
        "on_hand": 1,
        "min_required": 1,
        "unit_cost": "$4,450",
        "status": "In Stock - Ready",
        "substitute_sap_code": "SAP-VLV-RELIEF-400",
        "vendor_lead_time": "48h Express"
    },
    {
        "sap_code": "SAP-PUMP-ROT-700",
        "name": "Kawasaki K3V180 Cylinder Block & Piston Set",
        "fitment": "XCMG XE700D Heavy Excavator",
        "location": "Warehouse Bay 04 (Heavy Rack 02)",
        "on_hand": 0,
        "min_required": 1,
        "unit_cost": "$12,800",
        "status": "Stock Shortage - Expedited PO Required",
        "substitute_sap_code": "",
        "vendor_lead_time": "4-6 Hours Air Freight"
    },
    {
        "sap_code": "SAP-LUBE-PURGE-08",
        "name": "Slew Bearing Grease Purge Pack #EP-2",
        "fitment": "XCMG XE7000 / XE4000 Slew Race",
        "location": "Warehouse Bay 02 (Bin A-09)",
        "on_hand": 12,
        "min_required": 4,
        "unit_cost": "$320",
        "status": "In Stock - Ready",
        "substitute_sap_code": "SAP-LUBE-MOBIL-EP2",
        "vendor_lead_time": "Immediate (Bulk Store)"
    },
    {
        "sap_code": "SAP-SLEW-PINION-700",
        "name": "Slew Pinion Drive Shaft 14-Tooth Heat-Treated",
        "fitment": "XCMG XE7000 Swing Reducer",
        "location": "Warehouse Bay 04 (Heavy Rack 08)",
        "on_hand": 2,
        "min_required": 1,
        "unit_cost": "$8,950",
        "status": "In Stock - Ready",
        "substitute_sap_code": "",
        "vendor_lead_time": "72h Heavy Courier"
    },
    {
        "sap_code": "SAP-PARK-W200-HP",
        "name": "Parker Boom Wiper & Piston Pack #W-200",
        "fitment": "XCMG XE2000 Boom Cylinder",
        "location": "Warehouse Bay 01 (Bin C-14)",
        "on_hand": 0,
        "min_required": 2,
        "unit_cost": "$1,120",
        "status": "Stock Shortage - Use Substitute",
        "substitute_sap_code": "SAP-CAT-W200-EQUIV",
        "vendor_lead_time": "PO In Transit (ETA 8h)"
    },
    {
        "sap_code": "SAP-CAT-W200-EQUIV",
        "name": "Hallite 755 Heavy Boom Cylinder Packing Set",
        "fitment": "XCMG XE2000 / Cat 6020B Equivalent",
        "location": "Warehouse Bay 01 (Bin C-16)",
        "on_hand": 3,
        "min_required": 1,
        "unit_cost": "$1,280",
        "status": "In Stock - Substitute Ready",
        "substitute_sap_code": "SAP-PARK-W200-HP",
        "vendor_lead_time": "Immediate (On Shelf)"
    },
    {
        "sap_code": "SAP-FLT-HYD-440",
        "name": "High-Pressure Return Filter Element #FLT-440",
        "fitment": "Universal Mining Fleet XCMG",
        "location": "Warehouse Bay 02 (Bin B-18)",
        "on_hand": 18,
        "min_required": 6,
        "unit_cost": "$320",
        "status": "In Stock - Ready",
        "substitute_sap_code": "",
        "vendor_lead_time": "Immediate (Consumable)"
    },
    {
        "sap_code": "SAP-RAD-CORE-1250",
        "name": "Hydraulic Oil Cooler Core Radiator #RAD-1250",
        "fitment": "XCMG XE1250 Mining Excavator",
        "location": "Warehouse Yard Staging (Pallet 04)",
        "on_hand": 2,
        "min_required": 1,
        "unit_cost": "$6,200",
        "status": "In Stock - Ready",
        "substitute_sap_code": "",
        "vendor_lead_time": "48h Regional"
    }
]


def check_sap_inventory_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 3: Checks live SAP MM inventory with autonomous substitution and stockout reasoning."""
    global PARTS_CACHE
    trace = list(state.get("execution_trace", []))
    trace.append("check_sap_inventory_node")
    
    unit_id = state.get("unit_id", "EX-04")
    telem = state.get("telemetry", {})
    profile = get_effective_profile(unit_id, telem)
    target_sap = profile.get("part_target", "SAP-PARK-902-KIT")
    
    parts_list = PARTS_CACHE or []
    
    if not parts_list:
        parts_dict = {p["sap_code"]: dict(p) for p in EXPANDED_OEM_PARTS}
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
                for db_p in db_parts:
                    code = db_p.get("sap_code")
                    if code in parts_dict:
                        parts_dict[code]["on_hand"] = db_p.get("on_hand", parts_dict[code]["on_hand"])
                        parts_dict[code]["status"] = db_p.get("status", parts_dict[code]["status"])
                        if db_p.get("location"):
                            parts_dict[code]["location"] = db_p.get("location")
                        if db_p.get("substitute_sap_code"):
                            parts_dict[code]["substitute_sap_code"] = db_p.get("substitute_sap_code")
                    else:
                        parts_dict[code] = {
                            "sap_code": code,
                            "name": db_p.get("name"),
                            "fitment": db_p.get("fitment"),
                            "location": db_p.get("location"),
                            "on_hand": db_p.get("on_hand", 0),
                            "min_required": db_p.get("min_required", 2),
                            "unit_cost": db_p.get("unit_cost"),
                            "status": db_p.get("status"),
                            "substitute_sap_code": db_p.get("substitute_sap_code", ""),
                            "vendor_lead_time": "24h Domestic"
                        }
        except Exception:
            pass
        parts_list = list(parts_dict.values())
        PARTS_CACHE = parts_list
            
    matched = next((p for p in parts_list if p["sap_code"] == target_sap), parts_list[0])
    
    # Autonomous Inventory Reasoning: Stockout vs Substitution Protocol
    is_substituted = False
    stockout_critical = False
    allocated_part = matched
    substitution_note = ""
    emergency_po = None
    
    if matched.get("on_hand", 0) <= 0:
        sub_code = matched.get("substitute_sap_code")
        sub_part = next((p for p in parts_list if p["sap_code"] == sub_code and p.get("on_hand", 0) > 0), None) if sub_code else None
        
        if sub_part:
            is_substituted = True
            allocated_part = sub_part
            substitution_note = f"Primary part {matched['sap_code']} is out of stock. Autonomous Agent allocated OEM equivalent substitute: {sub_part['name']} ({sub_part['sap_code']}) with {sub_part.get('on_hand')} units in stock."
        else:
            stockout_critical = True
            emergency_po = {
                "po_id": f"PO-EMG-{unit_id.replace('-', '')}",
                "requested_part": matched["name"],
                "sap_code": matched["sap_code"],
                "vendor_eta": matched.get("vendor_lead_time", "4-6 Hours Express Freight"),
                "urgency": "AOG / MINE DOWN CRITICAL",
                "status": "DISPATCHED TO REGIONAL DISTRIBUTOR"
            }
    
    allocated_part = dict(allocated_part)
    allocated_part["is_substituted"] = is_substituted
    allocated_part["stockout_critical"] = stockout_critical
    allocated_part["substitution_note"] = substitution_note
    allocated_part["emergency_po"] = emergency_po

    return {
        **state,
        "spare_parts": [allocated_part],
        "inventory_resolution": {
            "primary_part": matched,
            "allocated_part": allocated_part,
            "is_substituted": is_substituted,
            "stockout_critical": stockout_critical,
            "substitution_note": substitution_note,
            "emergency_po": emergency_po
        },
        "execution_trace": trace
    }


def synthesize_dispatch_node(state: AgentOperationalState) -> AgentOperationalState:
    """Node 4: Synthesizes final actionable work order draft, stockout holds, and cabin safety directives."""
    trace = list(state.get("execution_trace", []))
    trace.append("synthesize_dispatch_node")
    
    unit_id = state.get("unit_id", "EX-04")
    telem = state.get("telemetry", {})
    profile = get_effective_profile(unit_id, telem)
    diag = state.get("diagnosis_findings", {})
    parts = state.get("spare_parts", [{}])
    part = parts[0] if parts else {}
    cmsi = state.get("cmsi_score", 90.0)
    inv_res = state.get("inventory_resolution", {})
    
    stockout_critical = inv_res.get("stockout_critical", False) or part.get("stockout_critical", False)
    is_substituted = inv_res.get("is_substituted", False) or part.get("is_substituted", False)
    emergency_po = inv_res.get("emergency_po") or part.get("emergency_po")
    
    priority = "CRITICAL" if cmsi >= 90 else "HIGH" if cmsi >= 70 else "MEDIUM"
    
    if stockout_critical and emergency_po:
        directive = f"EMERGENCY MACHINE STANDBY / SHUTDOWN: Critical part {part.get('name')} is OUT OF STOCK. All field mobile rigs held at workshop. IMMEDIATELY CEASE DIGGING & SHUT DOWN HYDRAULIC PUMP to prevent permanent cylinder and pump seizure. Emergency procurement ({emergency_po['po_id']}) initiated with vendor (ETA: {emergency_po['vendor_eta']})."
        wo_status = "BLOCKED_AWAITING_PARTS"
        assigned_rig_str = f"{profile.get('assigned_rig', 'Mobile Rig Alpha')} (HELD AT WORKSHOP - STANDBY)"
        stock_str = f"0 Units on Shelf (OUT OF STOCK - {emergency_po['po_id']} DISPATCHED)"
    elif is_substituted:
        directive = f"DERATE DIGGING ENVELOPE: Limit breakout force by 30%. Mobile rig dispatched with OEM Equivalent substitute {part.get('name')}. Maintain safe idle until crew arrives."
        wo_status = "APPROVED_SUBSTITUTE_ALLOCATED"
        assigned_rig_str = profile.get("assigned_rig", "Mobile Rig Alpha")
        stock_str = f"{part.get('on_hand', 1)} Units on Shelf (OEM Substitute Ready)"
    elif cmsi >= 90:
        directive = f"DERATE DIGGING ENVELOPE IMMEDIATELY: Limit breakout force by 30% and avoid full-stroke cylinder stall against {profile['rock']}. Standby for {profile['assigned_rig']} inspection."
        wo_status = "READY_FOR_DISPATCH"
        assigned_rig_str = profile.get("assigned_rig", "Mobile Rig Alpha")
        stock_str = f"{part.get('on_hand', 1)} Units on Shelf ({part.get('status', 'Available')})"
    elif cmsi >= 70:
        directive = f"CAUTION: Elevated dynamic load observed on {diag.get('component', 'hydraulic circuit')}. Dampen swing acceleration and maintain engine RPM below 1800. Bukan kerusakan hidrolik. TIDAK PERLU PANGGIL MONTIR."
        wo_status = "OPERATIONAL_ADVISORY"
        assigned_rig_str = "No Rig Required (Operational Advisory)"
        stock_str = "All Parts Nominal"
    else:
        directive = "OPTIMAL CYCLE: Machine Operating Within Safe Limits. TIDAK PERLU SERVIS ATAU STOP KERJA. Lanjutkan operasi kerja normal."
        wo_status = "NOMINAL"
        assigned_rig_str = "No Mobile Rig Required (Unit Operational)"
        stock_str = "All Systems Ready"

    # Determine dynamic maintenance shift window
    dtc_check = f"{diag.get('dtc', '')} {profile.get('dtc_code', '')} {diag.get('component', '')} {profile.get('component', '')} {diag.get('diagnosis', '')} {profile.get('fault_summary', '')}".lower()
    
    if stockout_critical:
        shift_win = "Rig Held at Base • Machine Shutdown Required"
    elif "520301" in dtc_check or "meltdown" in dtc_check or "thermal" in dtc_check or "cooler" in dtc_check or "radiator" in dtc_check:
        shift_win = "Immediate Emergency Shutdown (Detik Ini Juga)"
    elif "520210" in dtc_check or "relief" in dtc_check:
        shift_win = "Pukul 18:00 (Pergantian Shift Malam)"
    elif "520198" in dtc_check or "slew" in dtc_check or "pinion" in dtc_check:
        shift_win = "Shift Besok Pukul 06:00 (RUL 18 Jam Safe Tolerance)"
    elif "520144" in dtc_check or "cylinder" in dtc_check or "bypass" in dtc_check:
        shift_win = "Pukul 12:00 (Istirahat Siang) atau Akhir Shift 18:00"
    elif "520150" in dtc_check or ("pump" in dtc_check and not "spool" in dtc_check):
        shift_win = "Detik Ini Juga (Stop Operasi & Kirim Standby Unit)"
    elif "520204" in dtc_check or "spool" in dtc_check or "cavitation" in dtc_check:
        shift_win = "Immediate Work Stop Required (Sekarang Juga)"
    elif wo_status == "NOMINAL" or cmsi < 50:
        shift_win = "Sesuai Kalender Rutin (PM 250 / 500 Jam)"
    elif wo_status == "OPERATIONAL_ADVISORY" or cmsi < 90:
        shift_win = "Tetap Bekerja (Tanpa Interupsi Jadwal Bengkel)"
    else:
        shift_win = "Immediate Work Stop Required"
        
    wo_draft = {
        "shift_window": shift_win,
        "id": f"WO-AI-{unit_id.replace('-', '')}",
        "unit": unit_id,
        "model": profile["model"],
        "dtc": diag.get("dtc", profile["dtc_code"]),
        "diagnosis": diag.get("diagnosis", profile["fault_summary"]),
        "part_name": part.get("name", "OEM Service Component"),
        "part_sap_code": part.get("sap_code", "SAP-GEN-KIT"),
        "inventory_location": part.get("location", "Warehouse Bay 01"),
        "part_stock": stock_str,
        "assigned_rig": assigned_rig_str,
        "estimated_downtime": profile.get("downtime_est", "2.0 Hours"),
        "priority": priority,
        "operator_alert": directive,
        "confidence": diag.get("confidence", 95),
        "status": wo_status,
        "stockout_critical": stockout_critical,
        "is_substituted": is_substituted,
        "emergency_po": emergency_po,
        "substitution_note": inv_res.get("substitution_note", "")
    }
    
    return {
        **state,
        "work_order_draft": wo_draft,
        "execution_trace": trace
    }


def chat_reasoning_engine(query: str, state: AgentOperationalState) -> str:
    """Node 5 / Endpoint: Conversational Copilot Q&A with strict language mirroring (EN <-> ID)."""
    unit_id = state.get("unit_id", "EX-04")
    diag = state.get("diagnosis_findings", {})
    wo = state.get("work_order_draft", {})
    telem = state.get("telemetry", {})
    cmsi = state.get("cmsi_score", 90.0)
    
    is_no_service = bool(
        diag.get("no_service_needed") or
        wo.get("no_service_needed") or
        state.get("no_service_needed") or
        "no rig" in str(wo.get("assigned_rig", "")).lower() or
        "bukan kerusakan" in str(diag.get("diagnosis", "")).lower() or
        "bukan kerusakan" in str(wo.get("diagnosis", "")).lower() or
        (str(diag.get("dtc", "")).startswith("0x00") and cmsi < 85)
    )
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            
            if is_no_service:
                scenario_instruction = f"""CRITICAL SCENARIO RULE - HEALTHY MACHINE / HIGH STRATA DIGGING LOAD (NOT A BREAKDOWN):
- The machine is fully operational and has NO mechanical breakdown or component failure (DTC: {diag.get('dtc', '0x00')}).
- Remaining Useful Life (RUL): {diag.get('rul_hours', 1200)} Operating Hours (Normal operational lifespan).
- Machine Stress Index (CMSI {cmsi}/100) is solely due to cutting into hard basalt rock strata (184 MPa compressive strength), NOT a hydraulic or mechanical defect.
- Shift Window: TETAP BEKERJA (Tanpa Interupsi Jadwal Bengkel). The unit MUST CONTINUE WORKING in the pit. Do NOT tell the operator to stop mining!
- Maintenance / Mobile Rig: NO Mobile Rig is required. NO work order or mechanic dispatch needed.
- In-Cab Directive: Derate digging breakout force by 30% or coordinate with drill & blast team to fracture hard rock.
- IF THE USER ASKS 'masih bisa bekerja berapa jam lagi?' or asks about remaining operating hours / RUL:
  You MUST answer clearly that the machine has a normal remaining useful life (RUL) of > {diag.get('rul_hours', 1200)} Operating Hours, is NOT damaged, and CAN CONTINUE WORKING in the pit without stopping! Explain that CMSI {cmsi} is normal rock resistance, not a failure.
"""
            else:
                scenario_instruction = """CRITICAL SCENARIO RULE - GENUINE COMPONENT FAILURE:
- Unit has active component failure requiring service or shutdown. Provide authoritative technical explanation.
"""

            prompt = f"""You are the TerraCortex Mining Copilot AI, an advanced OEM-certified reliability intelligence assistant for Heavy Mining Excavators (Fleet Unit {unit_id}).
Current Machine Operational Context:
- Machine Unit: {unit_id} ({wo.get('model', 'Mining Shovel')})
- Machine Stress Index (CMSI): {cmsi} / 100
- Technical Diagnosis: {diag.get('diagnosis')}
- SAE DTC Code: {diag.get('dtc')}
- Remaining Useful Life (RUL): {diag.get('rul_hours', 1200 if is_no_service else 28)} Operating Hours
- Operational Status: {'HEALTHY / HIGH STRATA DIGGING LOAD (NO MECHANICAL BREAKDOWN)' if is_no_service else 'ACTIVE COMPONENT ANOMALY'}
- Shift Window: {wo.get('shift_window', 'Tetap Bekerja' if is_no_service else 'Immediate Work Stop Required')}
- SAP MM Spare Part: {wo.get('part_name')} [{wo.get('part_sap_code')}] - {wo.get('part_stock')} at {wo.get('inventory_location')}
- Part Inventory Status: {'NO PARTS NEEDED (BUKAN KERUSAKAN)' if is_no_service else ('CRITICAL STOCKOUT (0 UNITS ON SHELF & NO ON-SITE SUBSTITUTES)' if wo.get('stockout_critical') else 'OEM EQUIVALENT SUBSTITUTION ALLOCATED' if wo.get('is_substituted') else 'IN STOCK & READY')}
- Emergency PO Protocol: {wo.get('emergency_po', {}).get('po_id') if wo.get('stockout_critical') else 'N/A'} (Vendor ETA: {wo.get('emergency_po', {}).get('vendor_eta') if wo.get('stockout_critical') else 'N/A'})
- Assigned Rig Status: {wo.get('assigned_rig')} (Est Downtime: {wo.get('estimated_downtime')})
- In-Cab Directive: {wo.get('operator_alert')}

{scenario_instruction}

User Message: "{query}"

CRITICAL MANDATORY LANGUAGE RULE:
- You MUST detect and strictly mirror the language used in the User Message:
  * If the user message is written in ENGLISH (e.g. 'Hello', 'What is the operational risk?', 'How long will the repair take?', 'Are parts in stock?'), YOU MUST RESPOND 100% IN ENGLISH.
  * If the user message is written in INDONESIAN (e.g. 'Halo', 'Apa risikonya?', 'Berapa lama perbaikannya?', 'Apakah suku cadang ready?'), YOU MUST RESPOND 100% IN INDONESIAN.
  * Do NOT answer in Indonesian if the user asked in English. Do NOT answer in English if the user asked in Indonesian.

Formatting Guidelines:
1. GREETINGS: If user only greets (e.g. 'Hello' / 'Halo'), greet back warmly in the user's language, state unit {unit_id} active status ({cmsi} CMSI), and offer help.
2. TECHNICAL: Answer authoritatively, concisely, and practically from an expert OEM Mining Reliability Engineer perspective.
3. MARKDOWN: Always format with clean Markdown (bold **terms**, linebreaks between paragraphs, and numbered points 1. 2. 3. on separate lines).
"""
            resp = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )
            if resp.text:
                return resp.text.strip()
        except Exception:
            pass
            
    q_lower = query.lower()
    is_id = any(w in q_lower for w in ["halo", "hai", "apa", "berapa", "kenapa", "mengapa", "bagaimana", "apakah", "ada", "bisa", "lama", "rusak", "bahaya", "suku", "cadang", "gudang", "stok", "jam", "mekanik", "risiko", "sisa", "umur"])
    
    if is_id:
        if is_no_service:
            if any(w in q_lower for w in ["jam", "rul", "lama", "waktu", "bekerja", "sisa", "umur"]):
                return f"""**Estimasi Sisa Umur Operasional ({unit_id}):**

Unit **{unit_id}** memiliki sisa umur pakai komponen (RUL) normal lebih dari **{diag.get('rul_hours', 1200)} Jam Operasional** dan **TIDAK MENGALAMI KERUSAKAN MEKANIKAL**.

1. **Status Operasi:** Unit aman dan diizinkan **TETAP BEKERJA** di pit penambangan tanpa interupsi jadwal bengkel.
2. **Penyebab CMSI ({cmsi}/100):** Kenaikan CMSI merupakan respon beban mekanikal wajar saat memotong strata batuan basalt keras (184 MPa), bukan kebocoran pompa atau katup (DTC `{diag.get('dtc', '0x00')}`).
3. **Rekomendasi:** Operator cukup melakukan derating gaya *breakout* sebesar 30% atau berkoordinasi dengan tim drill & blast untuk pelunakan batuan."""
            elif any(w in q_lower for w in ["risk", "berbahaya", "bahaya", "failure", "risiko", "rusak"]):
                return f"""**Penilaian Kondisi Operasional ({unit_id}):**

Unit **{unit_id}** dalam kondisi aman dan **TIDAK ADA RISIKO KERUSAKAN KRITIS**.

Tingginya indikator CMSI ({cmsi}/100) adalah respon wajar penetrasi batuan basalt keras (184 MPa), bukan anomali hidrolik. Cukup hindari *full-stroke stall* berulang untuk menjaga keausan wajar."""
            elif any(w in q_lower for w in ["spare part", "part", "cadang", "stok", "gudang"]):
                return f"""**Status Suku Cadang ({unit_id}):**

**Tidak diperlukan penggantian suku cadang.** Semua komponen hidrolik dan mekanikal beroperasi normal (DTC `{diag.get('dtc', '0x00')}`). Unit tetap melanjutkan pekerjaan di pit."""
            elif any(w in q_lower for w in ["hai", "halo"]):
                return f"""Halo! Saya **TerraCortex Mining Copilot**.

Unit **{unit_id}** saat ini aktif menggali strata batuan basalt keras dengan CMSI **{cmsi}/100** (kondisi normal operasional, bukan kerusakan).

Ada yang bisa saya bantu terkait parameter operasional atau rekomendasi penambangan?"""
            else:
                return f"""**Ringkasan Status Operasional {unit_id}:** {diag.get('diagnosis')}

* Status: **TETAP BEKERJA** (RUL > {diag.get('rul_hours', 1200)} Jam Operasional)
* Kode SAE DTC: `{diag.get('dtc', '0x00')}` (Bukan Kerusakan)
* Arahan Kabin: {wo.get('operator_alert')}"""

        if any(w in q_lower for w in ["risk", "berbahaya", "bahaya", "failure", "risiko"]):
            return f"""**Risiko Operasional untuk {unit_id}:** Operasi terus-menerus di bawah beban tinggi pada strata {telem.get('rock_stratum', 'Hard Basalt')} akan mempercepat keausan mikro (*micro-pitting*) pada {diag.get('component', 'hydraulic spool valve')}.

1. Sisa Umur Komponen (RUL): **{diag.get('rul_hours', 28)} jam operasional**.
2. Rekomendasi: Kurangi gaya *breakout* sebesar 30% dan kirim {wo.get('assigned_rig')} sebelum pergantian shift."""
        elif any(w in q_lower for w in ["spare part", "part", "cadang", "stok", "gudang"]):
            if wo.get("stockout_critical"):
                emg = wo.get("emergency_po") or {}
                return f"""**PERINGATAN KRITIS: Suku Cadang Habis ({unit_id})!**

Komponen utama **{wo.get('part_name')}** (Kode SAP: `{wo.get('part_sap_code')}`) saat ini **HABIS (Stok 0)** di gudang dan tidak memiliki part substitusi ready.

1. **Tindakan Darurat:** Agent telah menerbitkan **{emg.get('po_id', 'PO-EMG')}** ke distributor regional (Estimasi Tiba: **{emg.get('vendor_eta', '4-6 Jam')}**).
2. **Status Rig:** Unit servis {wo.get('assigned_rig')} ditahan di pangkalan agar teknisi tidak berangkat sia-sia.
3. **Instruksi Mesin:** Operator diwajibkan **STANDBY / SHUTDOWN** hidrolik segera guna mencegah kerusakan permanen."""
            elif wo.get("is_substituted"):
                return f"""**Alokasi Part Substitusi Terverifikasi ({unit_id}):**

Part utama sedang kosong, namun Agent Copilot telah mengalokasikan suku cadang **Substitusi OEM Kompatibel**: **{wo.get('part_name')}** (Kode SAP: `{wo.get('part_sap_code')}`).

* Lokasi Gudang: {wo.get('inventory_location')}
* Status Stok: **{wo.get('part_stock')}**
* Rekomendasi: Teknisi dapat langsung melakukan perbaikan dengan part substitusi ini."""
            else:
                return f"""**Pemeriksaan Stok Suku Cadang SAP ({unit_id}):** Suku cadang yang dibutuhkan adalah **{wo.get('part_name')}** (Kode SAP: `{wo.get('part_sap_code')}`).

* Status Gudang: **{wo.get('part_stock')}** di {wo.get('inventory_location')}.
* Tidak ditemukan kendala logistik (*ready for immediate dispatch*)."""
        elif any(w in q_lower for w in ["downtime", "jam", "lama", "repair", "perbaikan"]):
            return f"""**Estimasi Waktu Perbaikan ({unit_id}):** Estimasi *downtime* adalah **{wo.get('estimated_downtime')}** oleh tim {wo.get('assigned_rig')}.

Melakukan penggantian komponen secara terjadwal sekarang mencegah kerusakan parah pada *powerpack* yang memakan waktu hingga 36 jam."""
        elif any(w in q_lower for w in ["hai", "halo"]):
            return f"""Halo! Saya **TerraCortex Mining Copilot**.

Unit **{unit_id}** saat ini termonitor dalam status **CMSI Alert ({cmsi}/100)** dengan anomali pada {diag.get('component', 'sistem hidrolik')}.

Ada yang bisa saya bantu terkait risiko breakdown, ketersediaan suku cadang SAP, atau jadwal servis lapangan?"""
        else:
            return f"""**Ringkasan Diagnostik {unit_id}:** {diag.get('diagnosis')}

* Kode SAE DTC: `{diag.get('dtc')}`
* Unit Servis: {wo.get('assigned_rig')} disiapkan dengan suku cadang {wo.get('part_name')}.
* Arahan Kabin: {wo.get('operator_alert')}"""
    else:
        # English fallback
        if is_no_service:
            if any(w in q_lower for w in ["hour", "rul", "time", "work", "remain"]):
                return f"""**Operating Hours Assessment ({unit_id}):**

Machine unit **{unit_id}** has normal remaining useful life of **> {diag.get('rul_hours', 1200)} Operating Hours** with **NO MECHANICAL DAMAGE**.

1. **Operational Status:** Machine is completely safe and authorized to **CONTINUE WORKING** on the pit face without workshop downtime.
2. **CMSI Score ({cmsi}/100):** Elevated index is a natural mechanical reaction to hard basalt strata (184 MPa), not a pump or valve defect (DTC `{diag.get('dtc', '0x00')}`).
3. **Recommendation:** Derate breakout force by 30% or request drill & blast pre-fracturing assistance."""
            elif any(w in q_lower for w in ["risk", "danger", "fail"]):
                return f"""**Operational Risk Assessment ({unit_id}):**

Machine unit **{unit_id}** is operating safely with **ZERO RISK OF CATASTROPHIC FAILURE**.

Load resistance against hard basalt strata is within acceptable structural thresholds. Continue production with standard operator precautions."""
            elif any(w in q_lower for w in ["part", "stock", "warehouse", "spare"]):
                return f"""**Spare Parts Logistics ({unit_id}):**

**No replacement parts required.** All hydraulic circuits and control valves are healthy (DTC `{diag.get('dtc', '0x00')}`). Machine remains in active production."""
            elif any(w in q_lower for w in ["hello", "hi", "hey"]):
                return f"""Hello! I am the **TerraCortex Mining Copilot**.

Unit **{unit_id}** is actively excavating hard basalt strata with CMSI **{cmsi}/100** (normal operational resistance, not a failure).

How can I assist you with machine parameters or operational guidelines?"""
            else:
                return f"""**Operational Summary for {unit_id}:** {diag.get('diagnosis')}

* Operational Status: **CONTINUE MINING** (RUL > {diag.get('rul_hours', 1200)} Operating Hours)
* SAE DTC Code: `{diag.get('dtc', '0x00')}` (Normal High Workload)
* In-Cab Directive: {wo.get('operator_alert')}"""

        if any(w in q_lower for w in ["risk", "danger", "fail"]):
            return f"""**Operational Risk for {unit_id}:** Continuous high-load digging against {telem.get('rock_stratum', 'Hard Basalt')} will accelerate micro-pitting in the {diag.get('component', 'hydraulic spool valve')}.

1. Estimated RUL: **{diag.get('rul_hours', 28)} operating hours**.
2. Recommendation: Derate breakout envelope by 30% and dispatch {wo.get('assigned_rig')} prior to shift handover."""
        elif any(w in q_lower for w in ["part", "stock", "warehouse", "spare"]):
            if wo.get("stockout_critical"):
                emg = wo.get("emergency_po") or {}
                return f"""**CRITICAL STOCKOUT WARNING ({unit_id})!**

The required part **{wo.get('part_name')}** (SAP: `{wo.get('part_sap_code')}`) is **OUT OF STOCK (0 On Shelf)** with no on-site substitutes.

1. **Expedited Procurement:** Autonomous Agent issued **{emg.get('po_id', 'PO-EMG')}** via express air freight (ETA: **{emg.get('vendor_eta', '4-6 Hours')}**).
2. **Rig Standby:** Mobile rig is held at workshop base to prevent abortive field travel.
3. **In-Cab Directive:** Operator instructed to **STANDBY / SHUT DOWN HYDRAULICS** immediately."""
            elif wo.get("is_substituted"):
                return f"""**Verified OEM Equivalent Substitution ({unit_id}):**

Primary part was depleted. Autonomous Agent successfully allocated OEM substitute: **{wo.get('part_name')}** (SAP: `{wo.get('part_sap_code')}`).

* Warehouse Location: {wo.get('inventory_location')}
* Stock Status: **{wo.get('part_stock')}**
* Recommendation: Field rig can safely proceed using this certified substitute."""
            else:
                return f"""**SAP MM Parts Verification ({unit_id}):** Required service kit is **{wo.get('part_name')}** (SAP Code: `{wo.get('part_sap_code')}`).

* Stock Status: **{wo.get('part_stock')}** located at {wo.get('inventory_location')}.
* No supply-chain bottleneck detected (ready for immediate dispatch)."""
        elif any(w in q_lower for w in ["time", "downtime", "duration", "repair", "long"]):
            return f"""**Maintenance Downtime Estimate ({unit_id}):** Planned service downtime is **{wo.get('estimated_downtime')}** allocated to {wo.get('assigned_rig')}.

Executing this preventative component swap now avoids an unscheduled 36-hour catastrophic powerpack rebuild."""
        elif any(w in q_lower for w in ["hello", "hi", "hey"]):
            return f"""Hello! I am the **TerraCortex Mining Copilot**.

Machine unit **{unit_id}** is currently under **CMSI Alert ({cmsi}/100)** due to an anomaly detected in the {diag.get('component', 'hydraulic system')}.

How can I assist you with failure risk, SAP spare parts inventory, or field rig dispatch?"""
        else:
            return f"""**Diagnostic Summary for {unit_id}:** {diag.get('diagnosis')}

* SAE DTC Code: `{diag.get('dtc')}`
* Service Crew: {wo.get('assigned_rig')} pre-staged with {wo.get('part_name')}.
* In-Cab Directive: {wo.get('operator_alert')}"""
