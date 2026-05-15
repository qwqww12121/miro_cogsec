<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

简洁通用的群体智能引擎，预测万物
</br>
<em>A Simple and Universal Swarm Intelligence Engine, Predicting Anything</em>

[English](./README-EN.md) | [中文文档](./README.md)

</div>

## Repository Positioning

**CogSec** (Cognitive Defense X) is a human-factor cognitive security prediction platform powered by the **MIRO-FISH multi-agent counterfactual inference engine**.

Unlike traditional text-based detection, this system derives its final risk assessment from a full cognitive security mainline:

- **User digital twin initialization** — 18-dimension cognitive profile → `persona_state_vector`
- **Threat-Persona-Context risk graph** — attack strategy chains × human factor weaknesses × environmental constraints
- **WorldState runtime engine** — MIRO-FISH-driven state evolution
- **Dual-branch counterfactual inference** — Fork at irreversible nodes, advancing both high-risk and safe paths
- **Consequence prediction & intervention prescriptions** — final risk comes from trajectory divergence, not text classification

Mainline roles:

- `MIRO-FISH` — primary inference runtime
- `CogSec` — cognitive security orchestration hub
- `T0FastResponder` — sub-second safety guardrail
- `CounterfactualReporter` — mainline result export

## Project Mainlines

### 1. Original MiroFish Prediction Mainline

The product flow is still:

`Graph Building -> Environment Setup -> Simulation -> Report Generation -> Deep Interaction`

Frontend entry and page flow:

- `frontend/src/router/index.js`
- `frontend/src/views/Home.vue`
- `frontend/src/views/MainView.vue`
- `frontend/src/views/SimulationView.vue`
- `frontend/src/views/SimulationRunView.vue`
- `frontend/src/views/ReportView.vue`
- `frontend/src/views/InteractionView.vue`

Backend application entry:

- `backend/run.py`
- `backend/app/__init__.py`

### 2. Graph Building Mainline

This line turns uploaded materials into `project / ontology / graph` state and is the earliest starting point of the system.

Backend entry:

- `backend/app/api/graph.py`

Core services:

- `backend/app/services/ontology_generator.py`
- `backend/app/services/graph_builder.py`
- `backend/app/services/zep_entity_reader.py`
- `backend/app/services/zep_graph_memory_updater.py`

Primary frontend controllers:

- `frontend/src/components/Step1GraphBuild.vue`
- `frontend/src/views/MainView.vue`

### 3. Simulation Mainline

This line creates simulations, prepares the environment, starts and stops execution, and exposes timeline and action logs.

Backend entry:

- `backend/app/api/simulation.py`

Core services:

- `backend/app/services/simulation_config_generator.py`
- `backend/app/services/oasis_profile_generator.py`
- `backend/app/services/simulation_runner.py`
- `backend/app/services/simulation_manager.py`
- `backend/app/services/simulation_ipc.py`

Main capabilities:

- `create / prepare / start / stop`
- `run-status / run-status/detail`
- `timeline / actions / posts / comments`
- `interview / interview history`

Primary frontend controllers:

- `frontend/src/components/Step2EnvSetup.vue`
- `frontend/src/components/Step3Simulation.vue`
- `frontend/src/views/SimulationView.vue`
- `frontend/src/views/SimulationRunView.vue`

### 4. Report Generation and Deep Interaction Mainline

This is the final output line of original MiroFish. It is responsible for report generation, section-level streaming progress, tool-call logs, and post-report interaction.

Backend entry:

- `backend/app/api/report.py`

Core services:

- `backend/app/services/report_agent.py`
- `backend/app/services/zep_tools.py`

Main capabilities:

- report generation and regeneration
- section-level streaming progress
- agent / console log streams
- report chat
- transition from report to interaction

Primary frontend controllers:

- `frontend/src/components/Step4Report.vue`
- `frontend/src/components/Step5Interaction.vue`
- `frontend/src/views/ReportView.vue`
- `frontend/src/views/InteractionView.vue`

### 5. CogSec Enhancement Mainline

CogSec is not a separate replacement workflow. It is an **enhancement line attached to the report page**.

Its actual position in the system is:

`after report generation -> resolve project / simulation / report by report_id -> run cognitive security analysis`

Frontend hook:

- `frontend/src/views/ReportView.vue`
- `frontend/src/components/cogsec/CogSecWorkbench.vue`

Backend entry:

- `backend/app/api/cogsec.py`

Main orchestration:

- `backend/app/services/cogsec_service.py`

Core modules:

- `backend/app/modules/cognitive_profile.py`
- `backend/app/modules/threat_rag.py`
- `backend/app/modules/risk_scorer.py`
- `backend/app/modules/reporter.py`
- `backend/app/modules/t0_fast_responder.py`
- `backend/app/modules/privacy_sanitizer.py`

## Mainline Map

### Frontend Mainline

1. `Home`
2. `/process/:projectId`
3. `/simulation/:simulationId`
4. `/simulation/:simulationId/start`
5. `/report/:reportId`
6. `/interaction/:reportId`

### Backend Mainline

1. `POST /api/graph/ontology/generate`
2. `POST /api/graph/build`
3. `POST /api/simulation/create`
4. `POST /api/simulation/prepare`
5. `POST /api/simulation/start`
6. `POST /api/report/generate`
7. `POST /api/report/chat`
8. `GET /api/cogsec/report/<report_id>` as the report-stage enhancement

## Repository Boundary

The following parts belong to the **formal mainline** of this repository:

- `backend/app/api/graph.py`
- `backend/app/api/simulation.py`
- `backend/app/api/report.py`
- `backend/app/api/cogsec.py`
- `frontend/src/views/*`
- `frontend/src/components/Step*.vue`
- `frontend/src/components/cogsec/*`

The following parts are better treated as **validation, demo, or delivery helpers**, not the public-facing mainline:

- `backend/run_cogsec_demo.py`
- `backend/templates/cogsec_demo.html`
- `backend/static/cogsec_demo.css`
- `backend/static/cogsec_demo.js`
- `backend/static/cogsec_demo_static.html`
- `tests/`
- `scripts/`

## Quick Start

### Prerequisites

| Tool | Version | Description |
|------|---------|-------------|
| Node.js | 18+ | frontend runtime |
| Python | >=3.11, <=3.12 | backend runtime |
| uv | latest | Python package manager |

### 1. Configure Environment Variables

```bash
cp .env.example .env
```

Minimum required values:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
ZEP_API_KEY=your_zep_api_key
```

If you want to enable local CogSec inference, add:

```env
COGSEC_USE_LOCAL_GEMMA=true
COGSEC_LOCAL_MODEL_PATH=./models/google--gemma-4-E2B-it
CHROMA_PATH=./data/chroma_db
FRAUD_CASE_DB_PATH=./data/fraud_cases.json
```

### 2. Install Dependencies

```bash
npm run setup:all
```

Or step by step:

```bash
npm run setup
npm run setup:backend
```

### 3. Start the Mainline

```bash
npm run dev
```

Service URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:5001`

Start individually:

```bash
npm run backend
npm run frontend
```

## Using CogSec

After completing graph building, simulation, and report generation:

1. open `/report/:reportId`
2. switch to `CogSec`
3. inspect T0 response, privacy sanitization, cognitive profile, risk scoring, and counterfactual report

You can also call the APIs directly:

```bash
POST /api/cogsec/analyze
GET /api/cogsec/report/<report_id>
```

## Minimal Demo

If you only want to validate the CogSec minimal chain without running the full mainline:

```bash
cd backend
python run_cogsec_demo.py
```

Then visit:

- `http://127.0.0.1:5052/demo/cogsec`
- `http://127.0.0.1:5052/health`

Note: this is a **validation line**, not the formal business mainline of the repository.

## Tests

```bash
python -m pytest tests/test_cognitive_profiler.py
python -m pytest tests/test_threat_rag.py
python -m pytest tests/test_risk_scorer.py
python -m pytest tests/test_cf_reporter.py
python -m pytest tests
```

## Current Progress

This repository currently implements the full **Layer 2 (Individual Cognitive Counterfactual Engine)** and the original MiroFish simulation pipeline.

### Completed

**CogSec Cognitive Security Engine (Layer 2):**

| Module | Status |
|--------|--------|
| `PrivacySanitizer` — local PII redaction, minimal-necessary, session_only | ✅ |
| `T0FastResponder` — <500ms red-flag guardrail | ✅ |
| `CognitiveProfileExtractor` — 18-dimension profiling | ✅ |
| `PersonaStateVector` — digital twin runtime vector | ✅ |
| `ThreatKnowledgeRAG` — risk graph, attack chains, fork point candidates | ✅ |
| `MiroFishRuntime` — WorldState init, fork selection, Branch A/B evolution | ✅ |
| `RiskScorer` — counterfactual risk aggregation from branch divergence | ✅ |
| `CounterfactualReporter` — digital twin summary, weakness chains, branch comparison, intervention prescriptions | ✅ |
| `CogSecService` — mainline orchestration with unified result structure | ✅ |
| `CogSecWorkbench` — 5-screen frontend display (10 Vue components) | ✅ |
| Core module unit tests (profiler / threat_rag / risk_scorer / cf_reporter) | ✅ |
| Minimal demo validation chain (`run_cogsec_demo.py`) | ✅ |

**MiroFish Original Simulation Pipeline:**

| Module | Status |
|--------|--------|
| Graph building (ontology → Zep knowledge graph → nodes/edges display) | ✅ |
| Multi-agent simulation (OASIS engine → multi-platform → timeline/interviews) | ✅ |
| Report generation & deep interaction (section-streaming report → agent Q&A) | ✅ |

### CogSec API Status

| Endpoint | Status |
|----------|--------|
| `POST /api/cogsec/analyze` | ✅ Implemented |
| `GET /api/cogsec/report/<report_id>` | ✅ Implemented |
| `POST /api/cogsec/mainline/analyze` | ❌ Not implemented |
| `GET /api/cogsec/diagram/master` | ❌ Not implemented |
| `POST /api/cogsec/evaluate` | ❌ Not implemented |

### To Do: Dual-Layer Counterfactual Cognitive Attack Attribution & Intervention Platform

The complete plan is documented in the research directory. The currently implemented CogSec engine is **Layer 2 (Individual Counterfactual)**. The next step is to build **Layer 1 (Macro Propagation Counterfactual)** and connect both layers.

**P0 — Layer 1: Macro Propagation Counterfactual (core new work):**

- [ ] Five platform template system (Zhihu-type / Xiaohongshu-type / Weibo-type / short-video / private-group)
- [ ] Multi-modal narrative gene parser (claims, evidence form, emotional frame, authority symbols, call-to-action, visual triggers)
- [ ] Macro counterfactual experiment automation (Agent removal / platform removal / edge blocking / narrative element replacement / visual element perturbation → re-simulate → compare coverage change)
- [ ] Agent cognitive state parameterization (trusted source preference, emotional threshold, conformity tendency, visual sensitivity, debunking receptivity)
- [ ] Visual element perturbation module (red stamp removal, avatar blur, timestamp deletion, color scheme swap)

**P1 — Two-layer integration & system completion:**

- [ ] Layer 1 → Layer 2 agent locking & handoff (Top-K key spreaders + representative samples from vulnerable population segments)
- [ ] Layer 2 → Layer 1 strategy feedback loop (individual prescriptions aggregated by cognitive profile → differentiated strategy library → injected into Layer 1 blue-team parameters)
- [ ] CogSec API completion (`mainline/analyze`, `diagram/master`, `evaluate`)
- [ ] Frontend: macro propagation dashboard (new) + two-layer interaction + strategy comparison panel

**P2 — Attack scenarios & evaluation (source: research docs):**

- [ ] MCP tool poisoning scenario (multi-agent perspective → cross-agent trust chain contamination)
- [ ] Indirect prompt injection scenario (injection source → Agent A → Agent B → terminal impact chain)
- [ ] Excessive agency analysis sub-module (Pareto frontier: attack blocking rate vs. functionality loss)
- [ ] Optimal human intervention point solver (MDP modeling + greedy selection + alarm fatigue robustness)
- [ ] Benchmark evaluation scripts (FSA / CPA / EAR / FPR / attribution efficacy / micro-layer lift)

**P3 — Demo & defense materials:**

- [ ] Main demo: campus incident fake notice two-layer governance (GPT Image 2-level fake screenshots)
- [ ] Core experiment: five control groups (no-intervention / detect-then-debunk / macro-only / static-centrality / macro+CogSec)
- [ ] Defense presentation slides & video
- [ ] Publication-grade diagrams (dual-layer architecture, counterfactual attribution comparison, intervention window curves)

## Acknowledgments

MiroFish is powered by **[OASIS](https://github.com/camel-ai/oasis)**.

Thanks to the original MiroFish team and the CAMEL-AI team for their open-source work.
