# VikSetu — Implementation Plan (5 Pages)

**Project:** VikSetu — Civic data ingestion, multi-AI pipeline, Palghar geospatial analytics, and map-native web experience  
**Version:** 1.0  
**Status:** Planning  
**Pilot region:** Palghar district (Maharashtra); architecture is region-agnostic for future districts.

---

## Page 1 — Vision, Scope, and Success Criteria

### 1.1 What VikSetu is

VikSetu is an **end-to-end civic analytics product**: users drop raw government material (PDFs, CSVs, exports, images) into a **workspace**; a **multi-stage AI pipeline** classifies, extracts, and normalizes data; results land in a **structured store** tied to **administrative geography**; a **map-first website** visualizes spend, schemes, facilities, and development status; a **site-connected chatbot** answers questions and **drives the UI** (filters, layers, charts, focus regions) via safe tool calls—not by hallucinating numbers.

VikSetu is a **decision-support helper**, not a replacement for auditors or RTI. Every KPI and map action must be **traceable** to a source file and extraction step.

### 1.2 In scope (v1)

| Area | Deliverable |
|------|-------------|
| **Workspace ingest** | Drag-and-drop upload; auto file typing; manifest per batch |
| **Multi-AI pipeline** | Configurable node graph: classify → extract (text / OCR / vision) → normalize → geocode → load DB |
| **Languages** | English, Hindi, Marathi (Devanagari) in documents and UI/chat |
| **Image / scan handling** | Scanned budgets, charters, tables (e.g. ZP PDFs with no text layer) |
| **Palghar map stack** | District + 8 taluka boundaries; facility pins; choropleths; work/scheme points when geocoded |
| **Analytics** | Budget vs spend, sector/taluka views, facility density, development status layers |
| **Web app** | Interactive map dashboard + linked charts + chat panel |
| **Agent** | ReAct-style orchestrator (extend existing `agent.py` / `tools.py` pattern) with **UI tools** |

### 1.3 Out of scope (v1 — defer)

- Real-time sync with all gov portals (batch ingest only; scheduled refresh optional later)
- Mobile native apps
- Full PMGSY / GatiShakti line-network ingestion
- Legal RTI workflow automation
- Multi-district production deployment (design for it; ship Palghar pilot)

### 1.4 Success criteria (demo-ready)

1. Upload **≥3 real source types** (e.g. text PDF, scanned PDF, CSV) → workspace organizes them and shows **detected region = Palghar** (or “unknown” with user confirm).
2. **PS-style spend table** available in SQLite/CSV without manual copy-paste.
3. **Map** shows talukas + at least one choropleth + one POI layer (e.g. health/schools).
4. Chat: *“Show works spend by sector”* → chart updates; *“Focus Jawhar taluka”* → map zooms/filters; *“Why is education spend zero?”* → numeric answer from DB + optional narrative from document chunks.
5. **Trace log**: each chat action links to query/tool name and source rows.

### 1.5 Open decisions (need your input)

| # | Question | Default if silent |
|---|----------|-------------------|
| A | Hosted API (Gemini) allowed for viva/demo, or **local-only** (Ollama/textgen)? | Hybrid: local extract + optional Gemini for Marathi table repair |
| B | Team size & timeline (weeks until submission)? | 8–10 week phased plan below |
| C | Frontend preference: **React + MapLibre** (polished) vs **Streamlit** (fast MVP)? | React for final site; Streamlit optional for internal pipeline QA |
| D | Must the drag-drop pipeline be **visual** (node editor) in v1, or config YAML + upload UI first? | Upload UI + fixed pipeline v1; visual editor v1.5 |

---

## Page 2 — Multi-Language & Multi-Modal AI Strategy

### 2.1 Can one LLM handle English, Hindi, Marathi **and** images?

**Partially.** One **strong multilingual model** can:

- Classify document type and language
- Parse messy text and JSON tool outputs
- Summarize and answer user chat in EN/HI/MR
- Perform **light** OCR correction on short snippets

One model **alone** is **weak** for:

- **Reliable numbers** from large scanned tables (hallucination risk)
- **Bulk OCR** of 60-page Marathi scans (cost, latency, inconsistency)
- **GIS operations** (must be code/SQL, not LLM)

**Recommendation: 1 primary “brain” LLM + deterministic specialists (not necessarily a second chat LLM).**

| Role | Component | Notes |
|------|-----------|--------|
| **Orchestrator** | 1× multilingual LLM | Routing, chat, tool selection, Marathi/HI/EN user messages |
| **Vision / table repair** | Same LLM **with vision** *or* dedicated VLM step | Only on pages flagged `scan` / low text yield |
| **OCR** | Tesseract (`mar`+`eng`+`hin`) or PaddleOCR | Bulk text from scanned PDFs; cheap, reproducible |
| **Numbers & maps** | Python + SQLite + GeoPandas | **Never** trust LLM for sums/joins |
| **Optional RAG** | Chunk store on narrative PDF text | Explanations & quotes only |

### 2.2 When to use a **second** LLM

Use **two LLMs** only if:

- Local model lacks Marathi quality → **Orchestrator local + table extraction cloud** (e.g. Gemini Flash with vision), **or**
- Policy requires on-prem → **small local router** + **specialized OCR VLM** self-hosted (heavier ops).

**VikSetu v1 default architecture:**

```text
[Upload] → Classifier (LLM #1, text-only, cheap)
              ├─ digital PDF → pdf text extract (no LLM)
              ├─ scan PDF    → OCR engine → Table Parser (LLM #1 vision OR rules)
              └─ CSV/GeoJSON → schema infer (code + LLM validate)
           → Normalizer (mostly code; LLM for column mapping suggestions)
           → Geocoder (LGD village join + fuzzy match; LLM only for disambiguation)
           → SQLite + GeoJSON exports
           → Chat Orchestrator (same LLM #1 + tools + optional RAG)
```

**Language policy:** Internal canonical schema **English** (`sector`, `taluka`, `amount_inr`, `fy`, `status`); display labels localized EN/HI/MR in UI; store `source_text_mr` where needed for audit.

### 2.3 Pipeline stages (logical nodes for drag-and-drop)

Each node has **inputs**, **outputs**, and **config** (region hint, FY, languages).

| Node ID | Name | Input | Output | AI? |
|---------|------|-------|--------|-----|
| N0 | **Ingest** | Raw files | `manifest.json` blobs | No |
| N1 | **Classify** | File + sample text/image | `doc_type`, `lang`, `region_guess`, `needs_ocr` | LLM |
| N2 | **Extract Text** | PDF/digital | `.txt` per doc | No |
| N3 | **OCR** | Scan PDF/images | `.txt` + page images | OCR |
| N4 | **Table Extract** | Text/OCR/vision | `rows.csv` | LLM vision or rules |
| N5 | **Normalize** | rows.csv | unified schema | Code + LLM assist |
| N6 | **Region Bind** | text + metadata | `district`, `taluka`, `village` | LLM + gazetteer |
| N7 | **Geocode** | places | points/layers GeoJSON | Code |
| N8 | **Load Store** | tables + geo | SQLite + `geo/` | No |
| N9 | **Insights** | DB | `insights.json` | Code |
| N10 | **Publish** | store | API + map tiles/layers | No |

**Drag-and-drop UX (v1):** Pre-wired chain N0→N1→…→N10; user drops files into **workspace**; pipeline runs automatically; **v1.5** exposes node canvas to enable/disable OCR or second-pass VLM.

### 2.4 Evaluation gate (before locking models)

Run a **10-document benchmark** (already have Palghar PS text PDF + ZP scan + 1 CSV):

| Metric | Target |
|--------|--------|
| Language ID accuracy | ≥95% |
| Region = Palghar detection | ≥90% on district docs |
| PS sector table F1 vs manual CSV | ≥90% numeric match |
| ZP scan: any usable table rows | ≥1 page with correct totals order-of-magnitude |
| Chat numeric QA vs SQLite | 100% on 20 canned questions |

If single LLM fails ZP scan, enable **N4 vision** only for `needs_ocr=true` pages.

---

## Page 3 — Data Model, Palghar Map, and Analytics Layer

### 3.1 Workspace & organization

**Workspace** = one project folder (or S3 prefix) per deployment:

```text
workspace/
  inbox/           # raw uploads (immutable)
  manifest.json    # file_id, hash, uploaded_at, pipeline_status
  staging/         # per-node outputs
  derived/         # canonical CSV, insights
  geo/             # boundaries, facilities, works
  db/viksetu.sqlite
  traces/          # agent + pipeline logs
```

**Auto-organization rules (N1 + N6):**

- Filename/URL hints: `palghar`, `zppalghar`, `जिल्हा परिषद पालघर`
- Content: district name, taluka list (Jawhar, Mokhada, Talasari, Vasai, Vikramgad, Palghar, Dahanu, Wada)
- User override in UI: “Assign region” dropdown if guess is low confidence

### 3.2 Canonical tables (SQLite)

| Table | Purpose |
|-------|---------|
| `documents` | Provenance: path, type, lang, fy, hash |
| `spend_lines` | sector, taluka?, budget, allocation, actual, fy, document_id |
| `works` | scheme, description, village, taluka, amount, status, geo_id? |
| `facilities` | type, name, lat, lon, source, operational_status |
| `taluka_metrics` | population, area, tribal_pct, … for choropleth |
| `insights` | precomputed KPIs JSON blob |

All agent/chart/map queries go through **views** (e.g. `v_spend_by_sector_fy`).

### 3.3 Palghar map assets (v1 load list)

| Layer | Source | Use |
|-------|--------|-----|
| `palghar_district` | Datameet / GADM / bharatlas filter | Mask & context |
| `talukas_8` | Same, 8 polygons | Choropleth, click filter |
| `villages` (optional v1.1) | Census/datameet simplified | Village centroids |
| `facilities_health` | MRSAC Health GIS export / OSM fallback | Pins + “proposed” styling |
| `facilities_education` | OSM + later UDISE | Pins |
| `works_points` | MGNREGA + geocoded PDF works | Status-colored pins |
| `basemap` | MapLibre + Carto dark/voyager | Visual polish |

**Centroid:** ~19.69°N, 72.76°E; default zoom district-level.

### 3.4 Analytics & map implementations (roadmap)

| Feature | Map | Chart | Data |
|---------|-----|-------|------|
| Spend by sector | — | Bar | `spend_lines` |
| Utilization % | Taluka choropleth | Gauge/table | aggregated |
| Zero-spend sectors | Highlight taluka sidebar | Alert list | PS/ZP rules |
| PMAY / scheme counts | GP/taluka bubbles | Stacked bar | extracted works |
| Facility access | Pin density hex | Histogram | facilities + population |
| Development status | 3-color works layer | Timeline (v2) | works.status |
| Population / tribal % | Choropleth | Small multiples | taluka_metrics |

**Linking:** Shared filter state `{ fy, taluka, sector, status }` in frontend store; chat tools mutate this state.

### 3.5 Existing assets (already in repo)

- `data/palghar_2024_25/raw/` — PS report, ZP budget scan, charters  
- `derived/ps_sector_spend_2024_25.csv` — gold sample for N4/N5 testing  
- `agent.py`, `tools.py`, `llm.py` — orchestrator pattern to extend  

---

## Page 4 — Web Application & Site-Connected Chatbot

### 4.1 Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  Browser (React + MapLibre GL JS + chart library)        │
│  ┌──────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Chat panel   │  │ Map + layers    │  │ Charts/KPIs │ │
│  └──────┬───────┘  └────────▲────────┘  └──────▲──────┘ │
│         │                    │ shared UI state │          │
└─────────┼────────────────────┼─────────────────┼────────┘
          │ WebSocket or REST  │                  │
┌─────────▼────────────────────▼──────────────────▼────────┐
│  API (FastAPI)                                              │
│  /workspace/upload  /pipeline/run  /geo/layers  /query/*   │
│  /chat  → VikSetu Agent (tools)                             │
└─────────┬──────────────────────────────────────────────────┘
          │
┌─────────▼──────────┐   ┌─────────────┐   ┌──────────────┐
│ SQLite + geo files │   │ LLM provider│   │ Pipeline jobs│
│ (viksetu.sqlite)   │   │ (llm.py)    │   │ (async queue)│
└────────────────────┘   └─────────────┘   └──────────────┘
```

### 4.2 UI layout (map-native)

- **Hero:** full-width map (60–70% viewport height on desktop)
- **Left drawer:** layer toggles (Talukas, Spend intensity, Health, Schools, Works)
- **Right drawer:** KPI cards + active chart
- **Bottom or floating:** chat with language auto-detect (EN/HI/MR)
- **Top bar:** FY selector, region badge (Palghar pilot), upload to workspace

**Visual direction:** dark basemap, muted polygon fills, category-colored pins, green/amber/gray for work status; Marathi labels optional toggle.

### 4.3 Chatbot ↔ site interaction (tool contract)

The chatbot **does not** freely edit HTML. It calls **UI tools** implemented server-side that return **state patches**:

| Tool | Effect |
|------|--------|
| `query_spend` | Returns data; may set `chart.type = bar`, `chart.metric = sector` |
| `set_filters` | `{ taluka, sector, fy, status }` → map + charts refresh |
| `map_focus` | `{ bbox or taluka }` → flyTo + highlight |
| `set_layers` | `{ health: true, works: true, … }` |
| `explain_metric` | RAG optional over document chunks |
| `show_source` | Open provenance panel for document_id |

Frontend subscribes to `ui_state` from `/chat` responses:

```json
{
  "answer": "…",
  "ui_patch": {
    "filters": { "taluka": "Jawhar", "fy": "2024-25" },
    "layers": { "works": true },
    "map": { "flyToTaluka": "Jawhar" },
    "chart": { "id": "spend_by_sector" }
  },
  "trace_id": "…"
}
```

Extend existing `run_agent()` with `Budget(steps=8, …)` and register VikSetu tools alongside calculator/sensor tools.

### 4.4 Security & trust (minimal v1)

- Upload size limits; virus scan optional
- No arbitrary code exec from LLM
- Read-only SQL views for agent queries
- Display **“Sources”** chip on every numeric answer

---

## Page 5 — Phased Delivery, Tech Stack, and Milestones

### 5.1 Recommended stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Pipeline | Python 3.11, PyMuPDF, Tesseract/PaddleOCR, pandas, GeoPandas | Matches training repo |
| DB | SQLite → Postgres optional later | Simple demo |
| API | FastAPI | Async jobs, OpenAPI |
| Frontend | React + Vite + MapLibre GL + TanStack Query | Interactive map + state |
| Charts | Apache ECharts or Plotly.js | Linked brushing |
| Agent | `agent.py` + `llm.py` providers | Already in Indus_Training |
| Jobs | Background thread or Celery (later) | Pipeline on upload |

### 5.2 Phase plan

| Phase | Weeks | Goals |
|-------|-------|--------|
| **P0 — Foundation** | 1–2 | Repo structure `viksetu/`; workspace + manifest; load PS CSV to SQLite; CLI query |
| **P1 — Pipeline core** | 2–3 | N0–N2, N5, N8 on PS PDF; classifier node; pipeline trace logs |
| **P2 — OCR / scan path** | 3–4 | N3–N4 on ZP budget sample; benchmark table; Marathi OCR tuning |
| **P3 — Geo** | 4–5 | taluka GeoJSON; facility layer; choropleth from spend aggregates |
| **P4 — API + MVP site** | 5–7 | FastAPI; map renders layers; charts from API |
| **P5 — Chat + UI tools** | 7–8 | Agent tools → `ui_patch`; 20 demo questions scripted |
| **P6 — Polish** | 8–10 | Upload UX, loading states, EN/HI/MR UI strings, report + video |

### 5.3 Drag-and-drop pipeline UI

| Version | UX |
|---------|-----|
| **v1** | Drop zone → progress stepper (Classify → Extract → Normalize → Map) |
| **v1.5** | React Flow / similar: nodes N0–N10, edges fixed presets (“Full gov PDF”, “CSV only”) |
| **v2** | Save custom graphs per workspace |

### 5.4 Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Scanned PDF quality | OCR + vision table repair; manual correction UI for one page |
| Village name mismatch | Taluka-level map first; fuzzy gazetteer |
| OSM sparse in tribal areas | Prioritize Health GIS / gov exports |
| LLM hallucination in chat | Tools-only for numbers; answer template cites SQL row |
| Scope creep | Ship Palghar + 3 source types before new districts |

### 5.5 Documentation deliverables (submission)

1. This implementation plan  
2. Architecture diagram + data dictionary  
3. User guide: upload → map → chat  
4. Evaluation sheet (benchmark in §2.4)  
5. Ethics note: public data, no PII, helper not authority  

### 5.6 Immediate next steps (Week 1 checklist)

- [ ] Confirm answers to open decisions **A–D** (Page 1)  
- [ ] Create `viksetu/` package: `workspace`, `pipeline`, `store`, `api` stubs  
- [ ] Import `ps_sector_spend_2024_25.csv` → SQLite + single REST `/query/spend`  
- [ ] Download Palghar taluka GeoJSON → `geo/talukas_8.geojson`  
- [ ] Run LLM benchmark on 3 files (classify + extract PS table)  
- [ ] Wire one chat tool: `set_filters` mock in CLI before React  

---

**Document end.**  
*VikSetu — structured civic data, map-native insight, agent as conductor.*
