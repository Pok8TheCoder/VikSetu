# VikSetu

Map-first civic analytics for Palghar (extendable). **LLM:** `LLM_PROVIDER=gemini` + `GOOGLE_API_KEY` (or textgen / ollama).

## Layout

```
backend/           FastAPI — geo, spend, canvas agent, file tools
backend/llm.py     LLM client
canvas/            tldraw canvas + agent panel
web/               React + MapLibre dashboard
agent_workspace/   Agent sandbox (inbox/, scratch/, python cwd)
scripts/           Geo fetch, POI cards
data/geo/          GeoJSON + poi cards
data/palghar_2024_25/  Spend CSV and PDFs
```

## Quick start

### 1. Geo data

```powershell
python scripts/fetch_geo.py
```

### 2. Map API (port 8001)

```powershell
pip install -r backend/requirements.txt
set LLM_PROVIDER=gemini
set GOOGLE_API_KEY=your_key
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

### 3. Map web (port 5173)

```powershell
cd web
npm install
npm run dev
```

### 4. Canvas API (port 8002) + UI (5175)

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

```powershell
cd canvas
npm install
npm run dev
```

Vite proxies `/api` to the ports above.

### POI cards

```powershell
python scripts/build_poi_cards.py
python scripts/clip_pois_to_district.py
```

Edit `data/geo/poi_overrides.json`, then re-run the builder.
