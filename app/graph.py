"""
graph.py — StateGraph Assembly and Orchestration for TerraCortex
Builds the LangGraph compiled pipeline:
START -> Ingest -> Diagnose & DTC -> Check SAP Inventory -> Synthesize Dispatch -> END
"""

from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from app.state import AgentOperationalState
from app.nodes import (
    ingest_telemetry_node,
    diagnose_dtc_node,
    check_sap_inventory_node,
    synthesize_dispatch_node,
    chat_reasoning_engine
)

def build_operations_graph():
    """Constructs and compiles the TerraCortex Operations StateGraph."""
    workflow = StateGraph(AgentOperationalState)
    
    # Register 4 sequential nodes
    workflow.add_node("ingest_telemetry", ingest_telemetry_node)
    workflow.add_node("diagnose_dtc", diagnose_dtc_node)
    workflow.add_node("check_sap_inventory", check_sap_inventory_node)
    workflow.add_node("synthesize_dispatch", synthesize_dispatch_node)
    
    # Establish edges
    workflow.add_edge(START, "ingest_telemetry")
    workflow.add_edge("ingest_telemetry", "diagnose_dtc")
    workflow.add_edge("diagnose_dtc", "check_sap_inventory")
    workflow.add_edge("check_sap_inventory", "synthesize_dispatch")
    workflow.add_edge("synthesize_dispatch", END)
    
    return workflow.compile()

# Global compiled graph instance
compiled_graph = build_operations_graph()

# Memory cache to avoid re-diagnosing every time user asks a chat question
_STATE_CACHE: Dict[str, AgentOperationalState] = {}

def run_diagnostics_pipeline(unit_id: str = "EX-04", telemetry: Optional[Dict[str, Any]] = None) -> AgentOperationalState:
    """Convenience executor to run the complete LangGraph pipeline for a target excavator."""
    initial_state: AgentOperationalState = {
        "unit_id": unit_id,
        "telemetry": telemetry or {},
        "execution_trace": []
    }
    result = compiled_graph.invoke(initial_state)
    _STATE_CACHE[unit_id] = result
    return result

def ask_copilot_agent(unit_id: str, query: str, state: Optional[AgentOperationalState] = None, context: Optional[Dict[str, Any]] = None) -> str:
    """Conversational interface allowing superintendents to ask follow-up questions to the agent."""
    if context:
        is_no_service = bool(
            context.get("no_service_needed") or
            (context.get("assigned_rig") and "no rig" in str(context.get("assigned_rig")).lower()) or
            (context.get("dtc") and ("0x00" in str(context.get("dtc")) and "workload" in str(context.get("dtc")).lower())) or
            (float(context.get("cmsi", 0.0) or 0.0) < 85 and "0x00" in str(context.get("dtc", "")))
        )
        diag = {
            "component": context.get("component") or ("Ground Penetration Load (Hard Basalt Strata)" if is_no_service else "Hydraulic Component"),
            "diagnosis": context.get("diagnosis", ""),
            "dtc": context.get("dtc") or ("0x00 (Operational High Workload)" if is_no_service else "SPN 520204 / FMI 14"),
            "confidence": context.get("confidence", 98),
            "rul_hours": context.get("rul_hours") or (1200 if is_no_service else 28),
            "severity": "WARNING" if is_no_service else "CRITICAL",
            "no_service_needed": is_no_service,
            "shift_window": context.get("shift_window", "Tetap Bekerja (Tanpa Interupsi Jadwal Bengkel)")
        }
        wo = {
            "unit": unit_id,
            "model": context.get("model", "XCMG XE4000 Mining Shovel"),
            "diagnosis": context.get("diagnosis", ""),
            "dtc": diag["dtc"],
            "component": diag["component"],
            "part_name": context.get("part_name", "No Replacement Parts Required (Bukan Kerusakan)" if is_no_service else "OEM Service Kit"),
            "part_sap_code": context.get("part_sap_code", "N/A" if is_no_service else "SAP-GEN-KIT"),
            "inventory_location": context.get("inventory_location", "Excavator Active on Pit Face" if is_no_service else "Warehouse Bay 03"),
            "part_stock": context.get("part_stock", "Operational" if is_no_service else "In Stock"),
            "assigned_rig": context.get("assigned_rig", "No Rig Required (Hanya Derate Operasional Operator)" if is_no_service else "Mobile Rig Alpha"),
            "estimated_downtime": context.get("estimated_downtime", "0.0 Hours (Unit Tetap Bekerja di Pit)" if is_no_service else "2.5 Hours"),
            "operator_alert": context.get("operator_alert", ""),
            "shift_window": diag["shift_window"],
            "no_service_needed": is_no_service,
            "stockout_critical": context.get("stockout_critical", False),
            "is_substituted": context.get("is_substituted", False),
            "emergency_po": context.get("emergency_po")
        }
        state = {
            "unit_id": unit_id,
            "cmsi_score": float(context.get("cmsi", 72.0 if is_no_service else 94.0)),
            "telemetry": context.get("telemetry", {}),
            "diagnosis_findings": diag,
            "work_order_draft": wo,
            "spare_parts": [],
            "no_service_needed": is_no_service,
            "execution_trace": ["context_hydration"]
        }
        _STATE_CACHE[unit_id] = state

    if not state or not state.get("work_order_draft"):
        state = _STATE_CACHE.get(unit_id) or run_diagnostics_pipeline(unit_id)
    return chat_reasoning_engine(query, state)
