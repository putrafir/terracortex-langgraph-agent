# TerraCortex LangGraph Operations Intelligence Agent

Autonomous Multi-Agent Service for Heavy Mining Excavators operations, Condition-Based Monitoring (CBM), SAE J1939 Diagnostic Trouble Code (DTC) cross-matching, SAP MM spare parts verification, and automated Work Order generation.

## Architecture

```
START -> ingest_telemetry -> diagnose_dtc -> check_sap_inventory -> synthesize_dispatch -> END
```

1. **`ingest_telemetry_node`**: Ingests sensor streams (hydraulic pressure, cavitation frequency, manifold temp, vibration, rock strata).
2. **`diagnose_dtc_node`**: Root-cause diagnostic reasoning via Google Gemini (with deterministic offline engineering fallback).
3. **`check_sap_inventory_node`**: Live inventory check against Supabase `sap_inventory`.
4. **`synthesize_dispatch_node`**: Mobile Workshop Rig assignment, RUL estimation, work order creation, and in-cab operator directives.
5. **Conversational Copilot Q&A**: Real-time interactive technical consultation for fleet superintendents.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Local CLI Tests
```bash
python3 tests/test_agent_local.py
```

### 3. Start Microservice (Port 8000)
```bash
python3 main.py
```
