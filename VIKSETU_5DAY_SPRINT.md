# VikSetu — 5-Day Sprint + UI Reference (from dashboard mocks)

**Constraints (locked):** Local LLM primary (`llm.py` / Ollama or textgen); cloud API optional fallback; **submission in 5 days**; **React frontend** + **Node or Python API**; pilot data: Palghar FY 2024–25 assets already in `data/palghar_2024_25/`.

**UI references:** `images/WhatsApp Image 2026-11-03*.jpeg` (Toronto, Ambato, Maple Grove, Lima, Charlottesville, RERA analytics, Apex, Berlin RIWIS, Kelowna, land-use comparison, UK planning).

---

## 1. What the references have in common (your target look)

| Pattern | Example in mocks | VikSetu equivalent |
|---------|------------------|-------------------|
| **Map hero** | Toronto bubbles, Ambato heat, Charlottesville pins | Palghar taluka choropleth + facility/work pins |
| **KPI strip** | Total apps 76k, investment $106M, 85% progress | Total budget, actual spend, utilization %, scheme count |
| **Filters** | Date, status, type, postal/ZIP | FY, taluka, sector, status (completed / planned / no spend) |
| **Time series** | Applications 2008–2022 bars | Optional: multi-FY when you have CSV; **v1: single FY bar by sector** |
| **Status breakdown** | Pie: complete / construction / approved | Works + spend by status (green/amber/gray) |
| **Linked brushing** | “Metrics relate to map — select to update” | Shared React state; chat sends same `ui_patch` |
| **Project list** | OPM codes, addresses | Scheme rows from DB (source doc, village, amount) |
| **Map popup** | Permit ID, subtype | Taluka stats or facility name + sector spend |
| **Tabs** | Housing / Population / Infrastructure | **v1:** Spend · Map · Facilities · Chat (4 tabs max) |
| **Table + map** | Berlin bottom grid | Sortable `works` / `spend_lines` table |

**Visual direction for demo:** Dark header (like Ambato/Lima), light or dark map (Carto Voyager), 2–3 charts max—not all widgets from all mocks.

---

## 2. What the agent can do **autonomously** vs what you **build once**

In 5 days the agent **does not** generate the whole React app. It **does** drive behavior on top of a fixed dashboard.

### Autonomous at runtime (agent + tools) — **in scope**

| Capability | Tool / behavior | Mock analogue |
|------------|-----------------|---------------|
| Answer spend questions with **exact numbers** | `query_spend` → SQLite | KPI indicators |
| **Filter map & charts** | `set_filters({ taluka, sector, fy, status })` | All dropdowns |
| **Fly to taluka / highlight** | `map_focus` | Urban centre selector |
| **Toggle layers** | `set_layers({ health, schools, works })` | Layer panel |
| **Pick chart view** | `set_chart({ id: "spend_by_sector" \| "status_pie" })` | Pie/bar widgets |
| **List matching schemes** | `list_works` | Project list / RERA table |
| **Explain narrative** | Optional RAG on PS PDF chunks | — |
| **Classify upload** | Pipeline: language, region, needs OCR | Ingest sidebar |
| **Organize workspace** | Manifest: type, region_guess, fy | — |

### Pipeline semi-auto (on file drop) — **minimal v1**

| Step | Automation | Human fallback |
|------|------------|----------------|
| Digital PDF (PS report) | PyMuPDF → parse known table → CSV | Fix CSV once if parse fails |
| Scanned PDF (ZP budget) | Flag `needs_ocr`; show in UI; **use pre-built sample rows for demo** | Slide: “OCR node ready” |
| CSV / GeoJSON | Auto-load | — |
| Region | Rule + LLM classify “Palghar” | Dropdown override |

### Not autonomous in 5 days — **defer / fake gently**

| Mock feature | v1 approach |
|--------------|-------------|
| Heatmap from 76k points | Taluka choropleth only |
| Dual land-use comparison maps | Single map |
| 3D / satellite parcel polygons | Taluka boundaries + pins |
| Live portal sync (MGNREGA) | Static GeoJSON + CSV |
| Agent writes new React components | Fixed widget set |

---

## 3. Architecture (local-first + cloud backup)

```text
React (Vite) ──REST/WS──► FastAPI or Express API
                              ├── SQLite (spend, works, facilities)
                              ├── geo/*.geojson
                              ├── agent (Python: extend agent.py)
                              │     LLM_PROVIDER=ollama|textgen
                              │     fallback: gemini if OLLAMA_FAIL=1
                              └── pipeline/ (upload → classify → extract)
```

**Recommendation:** **React + Vite + MapLibre** frontend; **FastAPI** backend (reuse `llm.py`, `agent.py`, `tools.py` without rewriting in Node). Optional Node only if team insists—duplicate agent logic is wasted in 5 days.

**Local models (pick one stack):**

| Task | Local | Cloud backup |
|------|-------|--------------|
| Chat + tool routing | Ollama `llama3.2` / Qwen2.5 7B | Gemini Flash |
| Marathi classify | Same | Gemini |
| Scan tables | Tesseract `mar+eng` + rules; optional vision call | Gemini vision 1–2 pages |

---

## 4. Five-day schedule (submission-critical path)

### Day 1 — Data + API skeleton
- [ ] SQLite: load `ps_sector_spend_2024_25.csv` + seed `works` (3–5 rows from PS narrative, manual OK)
- [ ] FastAPI: `GET /spend`, `GET /geo/talukas`, `GET /facilities` (facilities can be empty stub)
- [ ] Download **Palghar taluka GeoJSON** → `geo/talukas_8.geojson`
- [ ] React app shell: header **VikSetu**, layout (map 60%, right KPI + chart)

### Day 2 — Map + charts (static, no chat)
- [ ] MapLibre: taluka fill by spend (join CSV aggregated **or** placeholder per-taluka split)
- [ ] ECharts/Recharts: bar spend by sector; pie status (completed/planned/no spend)
- [ ] Filters in UI (FY, taluka) → update map + charts (React context)
- [ ] Project table: sortable spend lines

### Day 3 — Agent + UI tools
- [ ] VikSetu tools: `query_spend`, `set_filters`, `map_focus`, `set_layers`, `set_chart`
- [ ] `POST /chat` → `run_agent` → return `{ answer, ui_patch, trace_id }`
- [ ] Chat panel wired: 10 **scripted** demo questions work end-to-end
- [ ] `LLM_PROVIDER` local; env flag for Gemini fallback

### Day 4 — Upload + pipeline demo
- [ ] Drop zone → save to `workspace/inbox` → run classify + PS extract (existing script)
- [ ] Progress UI: Classify → Extract → Load DB (stepper, not full node editor)
- [ ] Optional: 5–10 OSM or static health pins JSON for “Facilities” layer
- [ ] Polish: dark theme, legend, source citations on KPIs

### Day 5 — Report, rehearse, record
- [ ] 2-page report: architecture, data sources, agent vs RAG, limitations
- [ ] Screenshot deck matching friend’s mocks (label what VikSetu implements)
- [ ] Demo video 3–5 min: upload → map → chat changes view
- [ ] Freeze dependencies; README run instructions

---

## 5. React page structure (one dashboard route)

```text
┌─────────────────────────────────────────────────────────────┐
│ VikSetu    [FY ▼] [Taluka ▼] [Sector ▼]     [Upload]        │
├──────────────────────────────┬──────────────────────────────┤
│                              │  KPI: Budget | Spent | Util% │
│         MAP (MapLibre)       │  Chart (bar/pie)             │
│                              │  Table (schemes/spend)       │
├──────────────────────────────┴──────────────────────────────┤
│ Chat: "Focus Jawhar" / "Show health layer" / "Why edu 0?"   │
└─────────────────────────────────────────────────────────────┘
```

**Chat → site:** Frontend reducer applies `ui_patch` from `/chat` (same as manual filters).

---

## 6. Demo script (for viva)

1. Open dashboard — Palghar talukas, sector spend chart, **₹19,39,204** total actual (PS).  
2. Filter **Works** — map/table highlight.  
3. Chat: *“Which sectors had zero spend?”* → table + answer.  
4. Chat: *“Focus Palghar taluka”* (or Jawhar) → map flies.  
5. Upload PS PDF → pipeline runs → “Reloaded from document” (even if same data).  
6. Mention ZP scan → OCR path + cloud backup for table repair.

---

## 7. Honest scope statement (put in report)

> VikSetu implements a **map-linked civic analytics dashboard** with a **tool-using local LLM** that controls filters and queries structured data extracted from government documents. UI patterns follow modern development dashboards (references in appendix). Full autonomous OCR of all Marathi scans and live MGNREGA sync are **designed** but **partially implemented** in the pilot timeline.

---

## 8. Image → feature checklist (appendix for report)

| Ref (file time) | Steal for VikSetu |
|-----------------|-------------------|
| 3.35 Toronto | Bubble/count map → taluka labels with spend totals |
| 3.36 Ambato | Dark theme + KPI money + progress gauge → utilization % |
| 3.36 Maple Grove | Pie status + “charts relate to map” subtitle |
| 3.36 Lima | Sidebar nav + heat → later; v1: choropleth only |
| 3.37 Charlottesville | Color pins by status + summary table |
| 3.37 RERA | Filter sidebar + district pie → taluka pie |
| 3.37 Apex | Donut type/status + dev table tabs |
| 3.37 Berlin | Table sync with map filters |
| 3.38 Kelowna | Map popup + bottom chart dock |
| 3.38 Land use | Skip dual map v1 |
| 3.38 UK planning | Pipeline bar in sidebar → optional mini chart |

---

*End — prioritize Day 1–3; Days 4–5 are demo polish, not new architecture.*
