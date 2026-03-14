# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FoodDB** is a comprehensive food safety risk assessment platform consisting of two subsystems:

1. **RiskKB** (`riskkb/`) - Food safety risk knowledge base for symptom-to-risk-factor inference
2. **DairyRisk** (`dairyrisk/`) - Dairy supply chain risk assessment system with dual-mode workflow

**System Architecture**:
```
DairyRisk → uses RiskKB for knowledge inference
    ↓
RiskKB (standalone knowledge base)
    ↓
External APIs (MiniMax LLM - optional)
```

## Common Commands

### Development Setup

```bash
# Install RiskKB dependencies
cd riskkb
pip install pyyaml python-dotenv requests

# Install DairyRisk backend
cd ../dairyrisk/backend
pip install fastapi uvicorn pandas pyyaml networkx

# Install DairyRisk frontend
cd ../frontend
npm install
```

### Running the System

```bash
# Start both backend and frontend (recommended)
cd dairyrisk
./start_all.sh

# Manual start - backend
cd dairyrisk/backend
python api.py

# Manual start - frontend (new terminal)
cd dairyrisk/frontend
npm run dev

# Stop all services
./stop_all.sh
```

### Testing

```bash
# Run all tests
cd dairyrisk
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_api_endpoints.py -v

# Run single test
python -m pytest tests/test_engine.py::test_specific_function -v

# Verify system health
curl http://localhost:8000/health
```

### Knowledge Base Operations

```bash
# Query RiskKB directly
cd riskkb
python backend/cli.py "婴幼儿奶粉发热症状"

# Pretty-print output
python backend/cli.py "腹泻、发热" --pretty

# Rebuild GB agent outputs (after modifying standard_txt/)
python backend/gb_agent.py --disable-llm

# Rebuild methods corpus
python backend/methods_layer_rebuilder.py

# Test MiniMax connectivity
python test_minimax.py
```

### Frontend Development

```bash
cd dairyrisk/frontend

# Development server
npm run dev

# Build for production
npm run build

# Run linter
npm run lint

# Start production server
npm start
```

## Architecture

### RiskKB - Knowledge Base (`riskkb/`)

**Layered Knowledge Architecture** (not unified RAG):

1. **Rule Layer** (`knowledge/configs/`)
   - `risk_taxonomy.yaml`: 39 risk factors with symptom mappings
   - `gb_dairy_rules.yaml`: GB 2760-2024 additive rules
   - `stage_rules.yaml`: Risk factor → production stage mappings

2. **Evidence Layer** (`knowledge/corpora/`)
   - `rag_corpus_standard_txt.jsonl`: 4056 GB standard chunks
   - `rag_corpus_methods_standards_v2.jsonl`: 959 test methods
   - `rag_corpus_management_v2.jsonl`: 110 control measures

3. **Core Class**: `LayeredFoodRiskKB` (`backend/router.py`)
   - `analyze_query()`: Extract symptoms/products/test items
   - `infer_risk_factors()`: Score candidates using taxonomy
   - `infer_stages()`: Map risks to production stages
   - `retrieve_evidence()`: Search corpora for GB evidence

### DairyRisk - Assessment System (`dairyrisk/`)

**Dual-Mode Workflow**:

```
Mode A (Supply Chain)          Mode B (Symptom-Driven)
    ↓                                  ↓
Enterprise/Batch ID    →      Symptom description
    ↓                                  ↓
Risk scoring                    Risk factor inference
    ↓                                  ↓
Propagation analysis            Enterprise linking
    ↓                                  ↓
Report generation               Report generation
```

**Mode A+B (Linked Workflow)**:
```
Symptom → Risk Hypothesis → Enterprise Verification → Combined Report
```

**Key Modules**:

| Module | File | Purpose |
|--------|------|---------|
| Workflow | `agent/workflow.py` | Mode A assessment orchestration |
| Symptom Router | `agent/symptom_router.py` | Mode B inference logic |
| Orchestrator | `agent/orchestrator.py` | Mode A+B linked workflow |
| Retriever | `agent/retriever.py` | Data access layer |
| LLM Client | `agent/llm_client.py` | MiniMax API integration |
| API | `backend/api.py` | FastAPI endpoints |

**Data Flow**:
```
Frontend (Next.js) → FastAPI → Agent → RiskKB (optional)
                          ↓
                   DataRetriever → data/merged/*.csv
```

## Key File Locations

### Configuration
- `dairyrisk/.env` - API keys (MiniMax, etc.)
- `riskkb/.env` - Knowledge base API keys
- `dairyrisk/.env.example` - Template for environment variables
- `riskkb/.env.example` - Template for knowledge base config

### Data
- `dairyrisk/data/merged/` - Main dataset (30 enterprises, 110 batches)
- `riskkb/knowledge/configs/` - Risk taxonomy and rules
- `riskkb/knowledge/corpora/` - GB standard text corpora
- `riskkb/knowledge/standard_txt/` - 69 raw GB standard files

### Tests
- `dairyrisk/tests/test_api_endpoints.py` - API endpoint tests
- `dairyrisk/tests/test_engine.py` - Scoring engine tests

## API Endpoints

### Mode A - Supply Chain
- `POST /assess` - Risk assessment
- `POST /assess_stream` - Streaming assessment (SSE)
- `GET /enterprises` - List enterprises
- `GET /batches` - List batches

### Mode B - Symptom-Driven
- `POST /symptom/assess` - Symptom risk assessment
- `GET /symptom/risk_factors` - Risk factor library
- `GET /symptom/symptom_library` - Symptom library

### Mode A+B - Linked
- `POST /linked_workflow` - Full linked assessment
- `POST /linked_workflow_stream` - Streaming linked workflow

## Data Schemas

### Enterprise (`enterprise_master.csv`)
```python
{
  "enterprise_id": "ENT-XXXX",
  "enterprise_name": "企业名称",
  "node_type": "牧场|乳企|物流|仓储|零售",
  "credit_rating": "A|B|C|D",
  "historical_violation_count": int
}
```

### Batch (`batch_records.csv`)
```python
{
  "batch_id": "BATCH-XXXX",
  "enterprise_id": "ENT-XXXX",
  "product_type": "pasteurized|UHT|yogurt|powder",
  "production_date": "YYYY-MM-DD"
}
```

## Environment Variables

### DairyRisk (`dairyrisk/.env`)
```env
MINIMAX_API_KEY=your_key          # Optional, for LLM enhancement
MINIMAX_MODEL=MiniMax-M2.5
MINIMAX_TEMPERATURE=0.3
USE_MOCK_LLM=true                 # Force mock mode if no API key
```

### RiskKB (`riskkb/.env`)
```env
minimaxi-api-key=sk-...           # MiniMax API key
url=https://api.minimax.chat/v1
PubMed-API-KEY=...                # Optional
openFDA-API-KEY=...               # Optional
```

## Important Patterns

### JSONL Handling
All corpus files use JSONL format:
```python
# Read
with open("file.jsonl") as f:
    rows = [json.loads(line) for line in f if line.strip()]

# Write
with open("file.jsonl", "w") as f:
    for row in rows:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
```

### Path Constants
```python
# In riskkb backend modules
ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
CONFIG_DIR = KNOWLEDGE_DIR / "configs"
CORPUS_DIR = KNOWLEDGE_DIR / "corpora"
```

### RiskKB Integration in DairyRisk
```python
# SymptomRouter automatically loads RiskKB via StandaloneKBWrapper
from agent.symptom_router import get_symptom_router

router = get_symptom_router()
result = router.assess("腹泻、发热")
# Returns: symptoms, risk_factors, stages, linked_enterprises
```

## Development Notes

- **No unified RAG**: Uses layered routing (rule → config → corpus)
- **GB Agent is deterministic**: Core processing uses regex/rules; LLM is optional
- **Methods v2 preferred**: Router auto-uses `rag_corpus_methods_standards_v2.jsonl`
- **Test set**: `known_risk_testset_formal/` (76 cases) is the quality benchmark
- **Data dependency**: DairyRisk depends on RiskKB being in parent directory or sibling directory

## Related Documentation

- `dairyrisk/API_CONTRACT.md` - API specification
- `riskkb/README.md` - Knowledge base documentation
- `dairyrisk/README.md` - Assessment system documentation
