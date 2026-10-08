"""
server.py — FastAPI Microservice for TerraCortex LangGraph Operations Engine
Exposes REST endpoints on port 8000 for Next.js and Fleet Web Portals.
"""

import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.graph import run_diagnostics_pipeline, ask_copilot_agent

app = FastAPI(
    title="TerraCortex LangGraph Operations Engine",
    description="Multi-Agent Diagnostic & Predictive Operations Service for Heavy Mining Excavators",
    version="1.0.0"
)

# Enable CORS for Next.js local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DiagnoseRequest(BaseModel):
    unit_id: str = "EX-04"
    telemetry: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    unit_id: str = "EX-04"
    query: str

@app.get("/health")
def healthcheck():
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return {
        "status": "healthy",
        "service": "TerraCortex LangGraph Multi-Agent Engine",
        "llm_engine": "Gemini 2.0 Flash (Online)" if gemini_key else "Deterministic Mining Hydraulic Engine (Offline Fallback)",
        "active_graph_nodes": [
            "ingest_telemetry",
            "diagnose_dtc",
            "check_sap_inventory",
            "synthesize_dispatch"
        ]
    }

@app.post("/api/agent/diagnose")
def diagnose_excavator(req: DiagnoseRequest):
    try:
        state = run_diagnostics_pipeline(unit_id=req.unit_id, telemetry=req.telemetry)
        return {
            "success": True,
            "unit_id": state.get("unit_id"),
            "cmsi_score": state.get("cmsi_score"),
            "telemetry": state.get("telemetry"),
            "diagnosis": state.get("diagnosis_findings"),
            "work_order": state.get("work_order_draft"),
            "spare_parts": state.get("spare_parts"),
            "execution_trace": state.get("execution_trace")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent/chat")
def chat_copilot(req: ChatRequest):
    try:
        reply = ask_copilot_agent(unit_id=req.unit_id, query=req.query)
        return {
            "success": True,
            "unit_id": req.unit_id,
            "query": req.query,
            "reply": reply
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
