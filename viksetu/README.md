# VikSetu dashboard

Map-first civic analytics for Palghar (extendable). **LLM: cloud API** (`LLM_PROVIDER=gemini` + `GOOGLE_API_KEY`).

## Layout

```
viksetu/
  backend/main.py       FastAPI — geo, spend, canvas agent, file tools
  backend/llm.py        LLM client (gemini / textgen / ollama)
  backend/agent_files.py  Workspace file-read helpers for the agent
  canvas/               tldraw canvas + agent panel
  web/                  React + MapLibre dashboard
  agent_workspace/      Agent sandbox (inbox/, scratch/, python cwd)
  scripts/              Geo fetch, POI cards, probes
data/geo/               GeoJSON layers + regions manifest
data/palghar_2024_25/   Spend CSV and source PDFs
```

## Quick start

### 1. Geo data

```powershell
python viksetu/scripts/fetch_geo.py
```

Creates `data/geo/regions.json`, `palghar_district.geojson`, POI layers, `development_sites.geojson`.

If Overpass times out, demo **seed pins** are written (replace by re-running when online).

### 2. API

```powershell
pip install -r viksetu/backend/requirements.txt
set LLM_PROVIDER=gemini
set GOOGLE_API_KEY=your_key
cd viksetu/backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

### 3. Web

```powershell
cd viksetu/web
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to **:8001** (port 8000 is often taken on Windows).

## regions.json

Defines district center, **8 talukas** (id, name, centroid) for labels/fly-to, and layer colors. Extend with `shading_metric` and polygon URLs per taluka when you import real boundaries.

Run anytime: `python viksetu/scripts/clip_pois_to_district.py`

### Pin detail cards (UI + agent)

```powershell
python viksetu/scripts/build_poi_cards.py
```

Writes `data/geo/poi_cards.json` (582+ cards with FY history, descriptions, Google Maps links).  
Edit `data/geo/poi_overrides.json` to add real past-year rows, then re-run the builder.

API: `GET /api/poi/card/{pin_id}` · `GET /api/poi/cards?q=hospital`

## Map layers

| Layer | Source |
|-------|--------|
| District shading | `palghar_district.geojson` (OSM MultiPolygon R9531818) |
| Bbox (data only) | `palghar_bbox.geojson` + `regions.json` — not drawn on map |
| Schools | OSM or `layer_government_school` |
| Health | `layer_health_facility` |
| Govt / public | `layer_government_facility` |
| Development | `development_sites.geojson` (PS + planned) |

## Chat

`POST /api/chat` returns `ui_patch` (layers, map_focus). Set Gemini for full NL; rules work offline for keywords.

## Note on Google Maps

This stack uses **MapLibre + Carto basemap + OSM pins** (no Google API key). Swap basemap or add Google Maps JS later if required.
