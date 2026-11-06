"""VikSetu API — geo layers, spend data, chat stub (Gemini via llm.py)."""
from __future__ import annotations

import base64
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parents[1]
GEO = ROOT / "data" / "geo"
SPEND_CSV = ROOT / "data" / "palghar_2024_25" / "derived" / "ps_sector_spend_2024_25.csv"
WORK = ROOT / "agent_workspace"
INBOX = WORK / "inbox"
SCRATCH = WORK / "scratch"
INBOX.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BACKEND_DIR))
from agent_files import file_kind, run_file_action  # noqa: E402
from geo_utils import (  # noqa: E402
    filter_fc_district,
    load_district_fc,
    talukas_for_map,
)

app = FastAPI(title="VikSetu API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise HTTPException(404, f"Missing {path.name}. Run: python scripts/fetch_geo.py")
    return json.loads(path.read_text(encoding="utf-8"))


def load_geojson(name: str) -> dict:
    return load_json(GEO / name)


@app.get("/api/health")
def health():
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    model = None
    vision = False
    try:
        from llm import resolve_model, supports_vision

        provider, model = resolve_model()
        vision = supports_vision(provider, model)
    except Exception:
        pass
    return {
        "status": "ok",
        "service": "viksetu",
        "llm": provider,
        "model": model,
        "vision": vision,
    }


def load_regions() -> dict:
    return load_json(GEO / "regions.json")


def clip_to_district(fc: dict) -> dict:
    try:
        district_fc = load_district_fc(GEO)
    except (OSError, json.JSONDecodeError, KeyError):
        return fc
    return filter_fc_district(fc, district_fc)


@app.get("/api/regions")
def regions():
    return load_regions()


@app.get("/api/geo/talukas")
def geo_talukas():
    path = GEO / "talukas.geojson"
    if not path.is_file():
        raise HTTPException(404, "Missing talukas.geojson. Run: python scripts/fetch_talukas_and_pois.py")
    return talukas_for_map(load_json(path))


@app.get("/api/geo/district")
def geo_district():
    return load_geojson("palghar_district.geojson")


@app.get("/api/geo/bbox")
def geo_bbox():
    path = GEO / "palghar_bbox.geojson"
    if path.is_file():
        return load_json(path)
    reg = load_json(GEO / "regions.json")
    bbox = reg.get("district", {}).get("bbox")
    if not bbox or len(bbox) != 4:
        raise HTTPException(404, "No bbox. Run: python scripts/compute_palghar_bbox.py")
    w, s, e, n = bbox
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Palghar bbox", "bbox": bbox},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                },
            }
        ],
    }


@app.get("/api/geo/layers/{layer_id}")
def geo_layer(layer_id: str):
    allowed = {
        "facilities": "facilities_pois.geojson",
        "development": "development_sites.geojson",
        "government_school": "layer_government_school.geojson",
        "health_facility": "layer_health_facility.geojson",
        "government_facility": "layer_government_facility.geojson",
        "community_poi": "layer_community_poi.geojson",
        "other_poi": "layer_other_poi.geojson",
    }
    if layer_id not in allowed:
        raise HTTPException(404, f"Unknown layer. Choose from: {list(allowed)}")
    path = GEO / allowed[layer_id]
    if not path.is_file() and layer_id != "facilities":
        return {"type": "FeatureCollection", "features": []}
    fc = load_geojson(allowed[layer_id])
    return clip_to_district(fc)


POI_CARDS = GEO / "poi_cards.json"
POI_OVERRIDES = GEO / "poi_overrides.json"


def _load_poi_overrides_doc() -> dict:
    if not POI_OVERRIDES.is_file():
        return {"schema": "viksetu_poi_overrides_v1", "pins": {}}
    return json.loads(POI_OVERRIDES.read_text(encoding="utf-8"))


def _merge_poi_card(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, value in patch.items():
        if value is not None:
            merged[key] = value
    return merged


def _poi_card_merged(pin_id: str) -> dict:
    pins = _load_poi_cards_index()
    if pin_id not in pins:
        raise HTTPException(404, f"Unknown pin_id: {pin_id}")
    overrides = (_load_poi_overrides_doc().get("pins") or {}).get(pin_id) or {}
    return _merge_poi_card(pins[pin_id], overrides)


def _load_poi_cards_index() -> dict:
    if not POI_CARDS.is_file():
        raise HTTPException(
            404,
            "Missing poi_cards.json. Run: python scripts/build_poi_cards.py",
        )
    data = json.loads(POI_CARDS.read_text(encoding="utf-8"))
    return data.get("pins") or {}


@app.get("/api/poi/cards")
def poi_cards_index(q: str | None = None, limit: int = 40):
    """Full card index for agents; optional substring search on name/summary."""
    pins = _load_poi_cards_index()
    if not q:
        return {"pin_count": len(pins), "pins": pins}
    q_l = q.lower()
    matched = {
        pid: card
        for pid, card in pins.items()
        if q_l in card.get("name", "").lower() or q_l in card.get("agent_summary", "").lower()
    }
    items = list(matched.items())[: max(1, min(limit, 200))]
    return {"pin_count": len(matched), "pins": dict(items)}


@app.get("/api/poi/card/{pin_id}")
def poi_card(pin_id: str):
    return _poi_card_merged(pin_id)


class PinPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_summary: str | None = None


@app.patch("/api/poi/card/{pin_id}")
def patch_poi_card(pin_id: str, body: PinPatch):
    pins = _load_poi_cards_index()
    if pin_id not in pins:
        raise HTTPException(404, f"Unknown pin_id: {pin_id}")
    doc = _load_poi_overrides_doc()
    doc.setdefault("pins", {})
    entry = dict(doc["pins"].get(pin_id) or {})
    for field, value in body.model_dump(exclude_none=True).items():
        entry[field] = value
    doc["pins"][pin_id] = entry
    POI_OVERRIDES.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return _poi_card_merged(pin_id)


@app.get("/api/spend")
def spend():
    if not SPEND_CSV.is_file():
        raise HTTPException(404, "Spend CSV missing")
    rows = []
    with SPEND_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    total = next((r for r in rows if r.get("sector_en") == "Total"), None)
    return {"fy": "2024-25", "rows": rows, "total": total}


class ChatRequest(BaseModel):
    message: str
    ui_state: dict = Field(default_factory=dict)


class UIPatch(BaseModel):
    filters: dict = Field(default_factory=dict)
    layers: dict = Field(default_factory=dict)
    map_focus: dict | None = None
    chart: str | None = None


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Simple rule + optional Gemini; returns answer and ui_patch for dashboard."""
    msg = req.message.lower()
    patch = UIPatch()
    answer = ""

    if "school" in msg:
        patch.layers = {"government_school": True}
        answer = "Showing government schools layer from OpenStreetMap."
    elif "health" in msg or "hospital" in msg:
        patch.layers = {"health_facility": True}
        answer = "Showing health facilities layer."
    elif "gov" in msg or "office" in msg:
        patch.layers = {"government_facility": True}
        answer = "Showing government / public facility pins."
    elif "development" in msg or "construction" in msg or "work" in msg:
        patch.layers = {"development": True}
        answer = "Showing sample development / works pins (PS report + planned ZP budget)."
    elif "jawhar" in msg or "dahanu" in msg or "vasai" in msg or "wada" in msg:
        for t in ("jawhar", "dahanu", "vasai", "wada", "mokhada", "talasari", "vikramgad", "palghar"):
            if t in msg:
                patch.map_focus = {"taluka": t, "zoom": 10}
                answer = f"Map focus set to {t.title()} taluka."
                break
    elif "spend" in msg or "budget" in msg:
        patch.chart = "spend_by_sector"
        answer = "Total actual spend FY 2024-25 (PS extract): Rs 19,39,204. Chart updated."
    else:
        try:
            from llm import ask

            answer = ask(
                req.message,
                system=(
                    "You are VikSetu, a civic data assistant for Palghar district. "
                    "Answer briefly in the user's language. Use spend facts: total actual Rs 1939204 FY 2024-25. "
                    "Per-place FY history and summaries live in GET /api/poi/cards and /api/poi/card/{pin_id} "
                    "(data/geo/poi_cards.json). Users can enrich pins via data/geo/poi_overrides.json."
                ),
            )
        except Exception as e:
            answer = f"VikSetu (offline rules): ask about schools, health, gov facilities, development, taluka names, or spend. ({e})"

    return {
        "answer": answer,
        "ui_patch": patch.model_dump(exclude_none=True),
    }


class CanvasChatRequest(BaseModel):
    message: str
    history: list[dict] = Field(default_factory=list)
    canvas: list[dict] = Field(default_factory=list)
    selection: list[dict] = Field(default_factory=list)
    log: list[dict] = Field(default_factory=list)
    map: dict = Field(default_factory=dict)
    cursor: dict | None = None
    step: int = 0
    trace: list[dict] = Field(default_factory=list)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


class FileUpload(BaseModel):
    name: str
    data_b64: str


class PythonRequest(BaseModel):
    code: str


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name).strip("._")
    return (cleaned or "file")[:80]


def _spend_brief() -> list[dict]:
    if not SPEND_CSV.is_file():
        return []
    rows = []
    with SPEND_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("sector_en") == "Total":
                continue
            rows.append(
                {
                    "sector": row.get("sector_en"),
                    "actual_spend_inr": row.get("actual_spend_inr"),
                }
            )
    return rows[:12]


def _workspace_files() -> list[dict]:
    files = []
    for path in sorted(WORK.rglob("*")):
        if not path.is_file() or path.name == "_last_script.py":
            continue
        item = {
            "path": path.relative_to(WORK).as_posix(),
            "bytes": path.stat().st_size,
            "kind": file_kind(path),
        }
        if path.suffix.lower() in {".txt", ".md", ".csv", ".json"} and len(files) < 8:
            item["preview"] = path.read_text(encoding="utf-8", errors="replace")[:1200]
        files.append(item)
        if len(files) >= 50:
            break
    return files


def _inbox_file(file_id: str) -> Path:
    name = _safe_name(file_id)
    path = (INBOX / name).resolve()
    if not str(path).startswith(str(INBOX.resolve())) or not path.is_file():
        raise HTTPException(404, f"Unknown file: {file_id}")
    return path


def _vision_images_from_canvas(req: CanvasChatRequest, limit: int = 4) -> list[str]:
    import mimetypes

    shapes = list(req.canvas or [])
    shapes.sort(key=lambda shape: not shape.get("selected"))
    urls: list[str] = []
    for shape in shapes:
        if shape.get("type") != "viksetu-file":
            continue
        file_id = str(shape.get("fileId") or "").strip()
        if not file_id:
            continue
        kind = str(shape.get("fileKind") or "")
        try:
            path = _inbox_file(file_id)
        except HTTPException:
            continue
        if kind != "image" and path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        urls.append(f"data:{mime};base64,{encoded}")
        if len(urls) >= limit:
            break
    return urls


def _split_file_tools(actions: list) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if not isinstance(action, dict):
            kept.append(action)
            continue
        op = str(action.get("op") or "")
        if op not in {"file-read", "file-list"}:
            kept.append(action)
            continue
        note = run_file_action(WORK, INBOX, action)
        note["op"] = op
        note["fileId"] = action.get("fileId")
        note["path"] = action.get("path")
        note["mode"] = action.get("mode") or action.get("tool")
        notes.append(note)
    return kept, notes


def _pin_cards_for(map_state: dict, message: str) -> dict:
    try:
        pins = _load_poi_cards_index()
    except HTTPException:
        return {}
    cards: dict = {}
    selected = (map_state.get("selected") or {}).get("pinId")
    if selected in pins:
        cards[selected] = pins[selected]
    query = message.lower()
    for item in map_state.get("pins") or []:
        name = str(item.get("name") or "")
        pin_id = item.get("pinId")
        if name and len(name) > 3 and name.lower() in query and pin_id in pins:
            cards[pin_id] = pins[pin_id]
        if len(cards) >= 4:
            break
    if len(cards) < 4:
        for item in map_state.get("hiddenPinSamples") or []:
            name = str(item.get("name") or "")
            pin_id = item.get("pinId")
            if name and len(name) > 3 and name.lower() in query and pin_id in pins:
                cards[pin_id] = pins[pin_id]
            if len(cards) >= 4:
                break
    return cards


def _run_python(code: str) -> dict:
    script = (code or "").strip()
    if not script:
        return {"ok": False, "stdout": "", "stderr": "Empty script.", "code": 1}
    if len(script) > 20000:
        return {"ok": False, "stdout": "", "stderr": "Script is too long.", "code": 1}
    target = WORK / "_last_script.py"
    target.write_text(script, encoding="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, str(target)],
            cwd=str(WORK),
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Stopped after 45 seconds.", "code": 124}
    return {
        "ok": completed.returncode == 0,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-4000:],
        "code": completed.returncode,
    }


def _num(value) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[₹,\s]", "", str(value or ""))
    text = re.sub(r"(?i)(crore|cr|lakh|lac)$", "", text)
    try:
        return float(text)
    except ValueError:
        return 0.0


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in re.split(r"[,|\n]", value) if part.strip()]
    return []


def _chart_pairs(action: dict) -> tuple[list[str], list[float]]:
    bundled = _as_list(action.get("series") or action.get("data") or action.get("points") or action.get("items"))
    labels = []
    values = []
    for item in _as_list(action.get("labels")):
        if isinstance(item, dict):
            labels.append(str(item.get("label") or item.get("name") or item.get("sector") or ""))
        else:
            labels.append(str(item))
    for item in _as_list(action.get("values")):
        if isinstance(item, dict):
            values.append(_num(item.get("value") or item.get("amount") or item.get("y") or item.get("actual_spend_inr")))
        else:
            values.append(_num(item))
    if bundled and any(isinstance(item, dict) for item in bundled) and (not any(values) or not labels):
        labels = []
        values = []
        for item in bundled:
            row = item if isinstance(item, dict) else {}
            labels.append(str(row.get("label") or row.get("name") or row.get("sector") or ""))
            values.append(_num(row.get("value") or row.get("amount") or row.get("y") or row.get("actual_spend_inr")))
    count = max(len(labels), len(values))
    labels = [labels[index] if index < len(labels) and labels[index] else str(index + 1) for index in range(count)]
    values = [values[index] if index < len(values) else 0.0 for index in range(count)]
    return labels, values


def _hydrate_actions(actions: list, message: str) -> list:
    spend = _spend_brief()
    known = {str(row.get("sector") or "").lower(): _num(row.get("actual_spend_inr")) for row in spend}
    hydrated = []
    for action in actions:
        if not isinstance(action, dict) or action.get("op") != "chart":
            hydrated.append(action)
            continue
        labels, values = _chart_pairs(action)
        topic = f"{message} {action.get('title') or ''}".lower()
        about_spend = any(word in topic for word in ("spend", "sector", "budget", "expenditure", "outlay"))
        named = sum(1 for label in labels if label.lower() in known)
        if (not any(values)) and (about_spend or named >= 2) and spend:
            if named >= 2:
                labels = [label for label in labels if label.lower() in known] or [str(row.get("sector") or "") for row in spend]
                values = [known.get(label.lower(), 0.0) for label in labels]
            else:
                labels = [str(row.get("sector") or "") for row in spend]
                values = [_num(row.get("actual_spend_inr")) for row in spend]
            action["title"] = action.get("title") or "Sector-wise spend"
            action["chart"] = action.get("chart") or "bar"
        action["labels"] = labels
        action["values"] = values
        hydrated.append(action)
    return hydrated


def _split_python(actions: list) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if isinstance(action, dict) and action.get("op") == "python":
            script = str(action.get("code") or "")
            note = _run_python(script)
            note["script"] = script[:6000]
            notes.append(note)
        else:
            kept.append(action)
    return kept, notes


def _split_agent_tools(actions: list) -> tuple[list, list, list]:
    actions, file_notes = _split_file_tools(actions)
    actions, python_notes = _split_python(actions)
    return actions, file_notes, python_notes


@app.post("/api/canvas/files")
def upload_canvas_file(req: FileUpload):
    try:
        raw = base64.b64decode(req.data_b64, validate=True)
    except Exception as exc:
        raise HTTPException(400, f"Could not read that file: {exc}") from exc
    if len(raw) > 52_428_800:
        raise HTTPException(400, "File is larger than 50 MB.")
    name = _safe_name(req.name)
    dest = INBOX / name
    dest.write_bytes(raw)
    preview = ""
    kind = file_kind(dest)
    if kind == "text":
        preview = dest.read_text(encoding="utf-8", errors="replace")[:4000]
    elif kind == "image":
        preview = f"[image {dest.suffix.lower()}, {len(raw)} bytes — use file-read or vision when selected on canvas]"
    else:
        preview = f"[binary {dest.suffix.lower() or 'file'}, {len(raw)} bytes — use file-read mode hex or text]"
    return {"fileId": name, "name": name, "bytes": len(raw), "preview": preview, "kind": kind}


@app.get("/api/canvas/files/{file_id}/raw")
def canvas_file_raw(file_id: str):
    path = _inbox_file(file_id)
    return FileResponse(path, filename=path.name)


@app.post("/api/canvas/python")
def canvas_python(req: PythonRequest):
    """Run a script inside agent_workspace (read/write anywhere under that folder)."""
    return _run_python(req.code)


def _parse_canvas_turn(text: str) -> dict:
    thoughts = [part.strip() for part in re.findall(r"<think>(.*?)</think>", text, flags=re.S | re.I)]
    body = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    body = re.sub(r"</?think>", "", body, flags=re.I)
    cleaned = body.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    data: dict = {}
    if start != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            data = {}
    if not data:
        return {"thinking": "\n\n".join(item for item in thoughts if item), "reply": body.strip(), "actions": [], "continue": False}
    reply = data.get("reply")
    actions = data.get("actions")
    if not isinstance(reply, str):
        reply = ""
    if not isinstance(actions, list):
        actions = []
    thinking = data.get("thinking")
    if isinstance(thinking, (list, dict)):
        thinking = json.dumps(thinking, ensure_ascii=False)
    thoughts.append(str(thinking or "").strip())
    if "continue" not in data:
        flag = None
    else:
        flag = data.get("continue")
        if isinstance(flag, str):
            flag = flag.strip().lower() in {"true", "yes", "1"}
        else:
            flag = bool(flag)
    return {
        "thinking": "\n\n".join(item for item in thoughts if item),
        "reply": reply,
        "actions": actions,
        "continue": flag,
    }


CANVAS_SYSTEM = (
    "You are the VikSetu canvas agent. You share one tldraw page with the user. "
    "Every object in Canvas JSON has id, type, x, y, w, h (page position and size), text, detail, and selected. "
    "Selection JSON is exactly what the user currently has selected. When they say this, these, or the selection, use those ids. "
    "Use those coordinates and sizes when you place or refer to an object. "
    "Map JSON lists layerStats (id, enabled, totalPins, visiblePins), enabled pins with layerEnabled true, "
    "hiddenPinSamples for pins on disabled layers (layerEnabled false), and the selected pin. "
    "Pin cards JSON has the full record for the selected pin and any pin the user named. "
    "Use map-layer, map-focus, and map-pin to change the live map without placing a new map shape. "
    "Spend JSON is the real FY 2024-25 extract. Workspace files live in agent_workspace (inbox/, scratch/, any path you create). "
    "Canvas file objects use type viksetu-file with fileId, fileKind (image|text|binary), and name. Drop images on the canvas like any file; "
    "when selected and the model supports vision, image bytes are sent automatically (not via chat). "
    "Reply with JSON only, keys in this order: {\"thinking\": string, \"reply\": string, \"actions\": array, \"continue\": boolean}. "
    "thinking is your visible reasoning for this step, written before you act. "
    "On the first step, restate what the user wants and the plan. On later steps, say what the last result showed and what is next. "
    "Keep it to a few sentences. actions may be empty. "
    "Work in steps like an IDE agent. Each response is one step: think, do the next concrete actions, then stop. "
    "Do one task at a time. If the user asks for several new things (map and chart, chart and note, two charts, etc.), "
    "never create more than one new map, chart, doc, sheet, embed, or file object in the same step. "
    "Finish the first object, set continue to true, then on the next step create the next one using Canvas JSON positions so nothing overlaps. "
    "Set continue to true when you need to see the canvas or Python output before you can finish. "
    "Set continue to false when the user's request is complete. "
    "When placing a chart next to a map, read the map's x, y, w, h from Canvas JSON and set the chart x to map.x + map.w + 48, y to map.y, w at least 480, h at least 320. "
    "On a continuation you see your own earlier thinking and actions for this request, the result of each, and the page after your previous step. "
    "Use those ids to update or connect objects. "
    "new:0 only refers to an object created in the current step. Do not recreate an object that is already on the canvas. "
    "In the step where continue is false, reply is your final answer. Make it detailed: what you created or changed (type, id, position), "
    "the key numbers you used, and anything left undone. Earlier thinking is not kept for later requests, but your final reply is. "
    "In earlier steps reply is a one line status. "
    "Allowed actions: "
    "{\"op\":\"geo\",\"text\":string,\"geo\":\"rectangle|ellipse|diamond|triangle|hexagon\",\"x\":number,\"y\":number,\"w\":number,\"h\":number,"
    "\"color\":\"black|grey|violet|blue|light-blue|yellow|orange|green|red\"}, "
    "{\"op\":\"text\",\"text\":string,\"x\":number,\"y\":number,\"color\":string}, "
    "{\"op\":\"map\",\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"chart\",\"title\":string,\"chart\":\"bar|line|pie\",\"labels\":[string],\"values\":[number],\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"doc\",\"title\":string,\"format\":\"md|text\",\"body\":string,\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"sheet\",\"title\":string,\"columns\":[string],\"rows\":[[string]],\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"file\",\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"embed\",\"title\":string,\"html\":string,\"data\":any,\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"python\",\"code\":string}, "
    "{\"op\":\"file-read\",\"fileId\":string,\"mode\":\"text|hex|meta|parse\",\"offset\":number,\"length\":number,\"max_chars\":number} "
    "or {\"op\":\"file-read\",\"path\":string relative to agent_workspace}, "
    "{\"op\":\"file-list\",\"path\":string optional directory under agent_workspace}, "
    "{\"op\":\"arrow\",\"from\":string,\"to\":string} using an existing id or new:0, "
    "{\"op\":\"delete\",\"ids\":[string]}, {\"op\":\"zoom\"}, "
    "{\"op\":\"map-layer\",\"layer\":string,\"visible\":boolean}, "
    "{\"op\":\"map-focus\",\"pinId\":string} or {\"lng\":number,\"lat\":number,\"zoom\":number}, "
    "{\"op\":\"map-pin\",\"pinId\":string,\"name\":string,\"description\":string,\"agent_summary\":string} "
    "(writes poi_overrides.json; omit fields you do not change). "
    "When the user asks to add, place, create, or make a chart, note, sheet, map, or file, you must include that action. "
    "Cursor JSON is the page point under the pointer, or the last known point. New objects are placed just below it; you may omit x and y. "
    "Pass id on chart, doc, sheet, or embed to update that object instead of creating one. The user can also edit titles, notes, chart rows, and sheet cells. "
    "embed is your own custom object for anything the built-in chart, doc, sheet, file, and map cannot show, such as a gauge, a timeline, a table with bars, "
    "a checklist, a comparison card, or a small calculator. html is a self-contained HTML fragment with inline CSS and JavaScript. "
    "It runs in a sandboxed frame with no network, no external scripts, fonts, or images, and no access to the page. Draw with inline SVG or canvas. "
    "The dark theme background is already applied. data is optional JSON, available in the frame as window.DATA, so put the numbers there and read them in your script. "
    "Prefer the built-in chart, doc, sheet, and map when they fit. Use embed when they do not. To change an embed, resend the whole html with its id. "
    "python runs with cwd agent_workspace for up to 45s. You may read, write, rename, and delete files anywhere under that folder. "
    "Use file-read for a quick text/hex/parse peek; use python for heavier transforms. Results of file-read and file-list return on your next step. "
    "Build charts and sheets from Spend JSON, pin counts, sheet cells, or file previews. Do not invent budget numbers. "
    "A chart action must include labels and values copied from that data. values must be plain numbers, not formatted strings."
)


def _canvas_context(req: CanvasChatRequest) -> str:
    layers = (req.map or {}).get("layers") or {}
    enabled = [name for name, on in layers.items() if on]
    disabled = [name for name, on in layers.items() if not on]
    pins = (req.map or {}).get("pins") or []
    hidden = (req.map or {}).get("hiddenPinSamples") or []
    stats = (req.map or {}).get("layerStats") or []
    vision_note = ""
    vision_images = _vision_images_from_canvas(req)
    if vision_images:
        try:
            from llm import resolve_model, supports_vision

            provider, model = resolve_model()
            if supports_vision(provider, model):
                vision_note = (
                    f"{len(vision_images)} canvas image file(s) attached for vision ({model}). "
                    "Selected file shapes are sent first."
                )
            else:
                vision_note = (
                    f"{len(vision_images)} image file(s) on the canvas but {model} is text-only; "
                    "use file-read or python on inbox/ instead."
                )
        except Exception:
            vision_note = f"{len(vision_images)} image file(s) on the canvas."
    parts = [
            "Cursor JSON:\n" + json.dumps(req.cursor, ensure_ascii=False),
            "Canvas JSON:\n" + json.dumps(req.canvas[:40], ensure_ascii=False),
            "Selection JSON:\n" + json.dumps(req.selection[:20], ensure_ascii=False),
            "Change log JSON:\n" + json.dumps(req.log[-30:], ensure_ascii=False),
            "Map layers enabled: " + json.dumps(enabled),
            "Map layers disabled: " + json.dumps(disabled),
            "Map layer stats JSON:\n" + json.dumps(stats[:20], ensure_ascii=False),
            f"Visible pins ({(req.map or {}).get('enabledCount', len(pins))} on enabled layers, "
            f"{min(len(pins), 180)} listed):\n"
            + json.dumps(pins[:180], ensure_ascii=False),
            f"Hidden-layer pin samples ({min(len(hidden), 120)} listed, layer off so not on map):\n"
            + json.dumps(hidden[:120], ensure_ascii=False),
            "Selected pin:\n" + json.dumps((req.map or {}).get("selected"), ensure_ascii=False),
            "Pin cards JSON:\n" + json.dumps(_pin_cards_for(req.map or {}, req.message), ensure_ascii=False),
            "Spend JSON:\n" + json.dumps(_spend_brief(), ensure_ascii=False),
            "Workspace files:\n" + json.dumps(_workspace_files(), ensure_ascii=False),
        ]
    if vision_note:
        parts.insert(0, vision_note)
    return "\n".join(parts)


def _canvas_messages(req: CanvasChatRequest) -> list[dict]:
    from llm import resolve_model, supports_vision, user_message_content

    provider, model = resolve_model()
    vision = supports_vision(provider, model)
    messages: list[dict] = [{"role": "system", "content": CANVAS_SYSTEM}]
    # Earlier prompts contribute only the user text and the final reply. Their thinking and actions are not sent.
    history = [
        item
        for item in req.history[-12:]
        if str(item.get("text") or "").strip()
    ]
    if not history or history[-1].get("role") != "user" or history[-1].get("text") != req.message:
        history = [*history, {"role": "user", "text": req.message}]
    for index, turn in enumerate(history):
        role = "assistant" if turn.get("role") in ("agent", "assistant") else "user"
        content = str(turn.get("text") or "")
        if not req.trace and index == len(history) - 1 and role == "user":
            content += "\n\n" + _canvas_context(req)
        if role == "user" and index == len(history) - 1:
            imgs = _vision_images_from_canvas(req)
            if imgs and vision:
                messages.append(
                    {
                        "role": "user",
                        "content": user_message_content(content, imgs, vision=True),
                    }
                )
            else:
                messages.append({"role": role, "content": content})
        else:
            messages.append({"role": role, "content": content})
    # This prompt's own steps are sent back in full: what it thought, what it ran, and what happened.
    steps = req.trace[-6:]
    for index, item in enumerate(steps):
        sent = list(item.get("actions") or [])
        for note in item.get("python") or []:
            sent.append({"op": "python", "code": str(note.get("script") or "")})
        for note in item.get("file_tools") or []:
            sent.append(
                {
                    "op": str(note.get("op") or "file-read"),
                    "fileId": note.get("fileId"),
                    "path": note.get("path"),
                    "mode": note.get("mode"),
                }
            )
        messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "thinking": str(item.get("thinking") or "")[:3000],
                        "reply": str(item.get("reply") or ""),
                        "actions": sent,
                        "continue": True,
                    },
                    ensure_ascii=False,
                )[:30000],
            }
        )
        result_note = {
            "step": index + 1,
            "created": item.get("created") or [],
            "error": item.get("error") or None,
            "python": [
                {"ok": note.get("ok"), "stdout": note.get("stdout"), "stderr": note.get("stderr")}
                for note in (item.get("python") or [])
            ],
            "file_tools": [
                {
                    "ok": note.get("ok"),
                    "mode": note.get("mode"),
                    "path": note.get("path"),
                    "error": note.get("error"),
                    "text": str(note.get("text") or "")[:2000],
                    "dump": str(note.get("dump") or "")[:2000],
                    "preview": str(note.get("preview") or "")[:2000],
                }
                for note in (item.get("file_tools") or [])
            ],
        }
        content = "Result of your step " + str(index + 1) + ":\n" + json.dumps(result_note, ensure_ascii=False)[:6000]
        if index == len(steps) - 1:
            content += (
                "\n\nThe page now:\n"
                + _canvas_context(req)
                + "\n\nContinue the original request with the next step. "
                "Set continue to false and give a detailed final reply when it is finished. "
                "Do not recreate objects that already exist."
            )
        messages.append({"role": "user", "content": content})
    return messages


_PLACERS = frozenset({"map", "chart", "doc", "sheet", "embed", "file"})


def _one_placer_per_step(actions: list) -> tuple[list, bool]:
    """Keep at most one new embed object per step so map+chart requests do not overlap."""
    placed = [action for action in actions if isinstance(action, dict) and action.get("op") in _PLACERS]
    if len(placed) <= 1:
        return actions, False
    kept: list = []
    kept_one = False
    for action in actions:
        if not isinstance(action, dict) or action.get("op") not in _PLACERS:
            kept.append(action)
            continue
        if kept_one:
            continue
        kept.append(action)
        kept_one = True
    return kept, True


def _package_turn(req: CanvasChatRequest, text: str, provider, model) -> dict:
    turn = _parse_canvas_turn(text)
    hydrated = _hydrate_actions(turn["actions"], req.message)
    actions, file_notes, python_notes = _split_agent_tools(hydrated)
    actions, deferred = _one_placer_per_step(actions)
    for note in python_notes:
        note["stdout"] = str(note.get("stdout") or "")[-2500:]
        note["stderr"] = str(note.get("stderr") or "")[-800:]
    for note in file_notes:
        for key in ("text", "dump", "preview"):
            if key in note and isinstance(note[key], str):
                note[key] = note[key][:4000]
    asked = turn.get("continue")
    carry_on = True if python_notes or file_notes or deferred else bool(asked)
    return {
        "thinking": turn.get("thinking") or "",
        "reply": turn["reply"],
        "actions": actions,
        "continue": carry_on,
        "python": python_notes,
        "file_tools": file_notes,
        "source": "llm",
        "provider": provider,
        "model": model,
    }


def _error_turn(exc: Exception) -> dict:
    return {
        "reply": f"The model did not answer: {exc}",
        "actions": [],
        "source": "error",
        "provider": os.environ.get("LLM_PROVIDER", "textgen"),
        "model": None,
    }


@app.post("/api/canvas/chat")
def canvas_chat(req: CanvasChatRequest):
    """LLM turn with shapes, sizes, live pins, files, and an optional workspace Python step."""
    try:
        from llm import chat

        result = chat(_canvas_messages(req), temperature=0.2, json_mode=True, timeout=120)
        return _package_turn(req, result["text"], result.get("provider"), result.get("model"))
    except Exception as exc:
        return _error_turn(exc)


@app.post("/api/canvas/chat/stream")
def canvas_chat_stream(req: CanvasChatRequest):
    """Same turn as /api/canvas/chat, sent as lines of JSON: delta chunks while the model writes, then one final."""

    def events():
        try:
            from llm import chat_stream

            for item in chat_stream(_canvas_messages(req), temperature=0.2, timeout=120):
                if item.get("done"):
                    final = _package_turn(req, item["text"], item.get("provider"), item.get("model"))
                    yield json.dumps({"type": "final", **final}, ensure_ascii=False) + "\n"
                else:
                    yield json.dumps({"type": "delta", "text": item["delta"]}, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "final", **_error_turn(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
