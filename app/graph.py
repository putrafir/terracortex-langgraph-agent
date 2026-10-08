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

def run_diagnostics_pipeline(unit_id: str = "EX-04", telemetry: Optional[Dict[str, Any]] = None) -> AgentOperationalState:
    """Convenience executor to run the complete LangGraph pipeline for a target excavator."""
    initial_state: AgentOperationalState = {
        "unit_id": unit_id,
        "telemetry": telemetry or {},
        "execution_trace": []
    }
    result = compiled_graph.invoke(initial_state)
    return result

def ask_copilot_agent(unit_id: str, query: str, state: Optional[AgentOperationalState] = None) -> str:
    """Conversational interface allowing superintendents to ask follow-up questions to the agent."""
    if not state or not state.get("work_order_draft"):
        state = run_diagnostics_pipeline(unit_id)
    return chat_reasoning_engine(query, state)
