from dotenv import load_dotenv
load_dotenv()
"""
main.py — Entrypoint for TerraCortex LangGraph Operations Engine Service
Starts Uvicorn server on port 8000.
"""

import uvicorn
from app.server import app

if __name__ == "__main__":
    print("=" * 65)
    print(" TerraCortex LangGraph Operations Intelligence Agent Service")
    print(" Microservice Endpoint: http://127.0.0.1:8000")
    print(" Health Endpoint       : http://127.0.0.1:8000/health")
    print("=" * 65)
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=True)
