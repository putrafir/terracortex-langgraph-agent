"""
state.py — LangGraph Operational State Definition for TerraCortex
Defines the shared state dictionary passed across all nodes in the StateGraph.
"""

from typing import TypedDict, List, Dict, Any, Optional

class AgentOperationalState(TypedDict, total=False):
    # Ingestion Input
    unit_id: str
    telemetry: Dict[str, Any]
    cmsi_score: float
    ml_anomalies: List[Dict[str, Any]]
    
    # Node 2: Diagnostic & DTC Reasoning Output
    diagnosis_findings: Dict[str, Any]
    
    # Node 3: SAP MM Parts Inventory Output
    spare_parts: List[Dict[str, Any]]
    
    # Node 4: Synthesis & Work Order Output
    work_order_draft: Dict[str, Any]
    
    # Node 5: Interactive Chat Messages
    messages: List[Dict[str, str]]
    
    # Graph Execution Metadata
    execution_trace: List[str]
    error: Optional[str]
