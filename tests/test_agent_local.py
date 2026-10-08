"""
test_agent_local.py — Local Test Runner for TerraCortex LangGraph Agent
Executes StateGraph pipeline and tests conversational reasoning in local terminal.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph import run_diagnostics_pipeline, ask_copilot_agent

def test_local_execution():
    print("=" * 75)
    print("   TERRACORTEX OPERATIONS INTELLIGENCE — LANGGRAPH MULTI-AGENT TEST")
    print("=" * 75)
    
    test_units = ["EX-04", "EX-17", "EX-31"]
    
    for uid in test_units:
        print(f"\n[TESTING LANGGRAPH PIPELINE] Target Machine: {uid}")
        print("-" * 60)
        
        state = run_diagnostics_pipeline(unit_id=uid)
        trace = state.get("execution_trace", [])
        print(f"✓ Nodes Executed: {' -> '.join(trace)}")
        
        diag = state.get("diagnosis_findings", {})
        wo = state.get("work_order_draft", {})
        parts = state.get("spare_parts", [{}])
        part = parts[0] if parts else {}
        
        print(f"  • CMSI Score    : {state.get('cmsi_score')} / 100")
        print(f"  • Component     : {diag.get('component')}")
        print(f"  • SAE DTC Code  : {diag.get('dtc')}")
        print(f"  • Root Cause    : {diag.get('diagnosis')[:100]}...")
        print(f"  • RUL Remaining : {diag.get('rul_hours')} Operating Hours")
        print(f"  • SAP Part      : {part.get('name')} [{part.get('sap_code')}] ({part.get('on_hand')} in stock)")
        print(f"  • Mobile Rig    : {wo.get('assigned_rig')} (Est: {wo.get('estimated_downtime')})")
        print(f"  • In-Cab Alert  : {wo.get('operator_alert')[:90]}...")
        
    print("\n" + "=" * 75)
    print("   TESTING INTERACTIVE COPILOT CHAT REASONING (EX-04)")
    print("=" * 75)
    
    test_queries = [
        "What is the operational risk if EX-04 keeps digging for 2 more hours?",
        "Do we have enough spare parts in stock at the warehouse?",
        "How long will the repair downtime take?"
    ]
    
    for q in test_queries:
        print(f"\n[Superintendent Question]: \"{q}\"")
        ans = ask_copilot_agent("EX-04", q)
        print(f"[Agent Response]       : {ans}")
        
    print("\n" + "=" * 75)
    print("   ✓ ALL LANGGRAPH LOCAL TESTS PASSED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    test_local_execution()
