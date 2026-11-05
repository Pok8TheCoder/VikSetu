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
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data" / "geo"
SPEND_CSV = ROOT / "data" / "palghar_2024_25" / "derived" / "ps_sector_spend_2024_25.csv"
WORK = ROOT / "viksetu" / "agent_workspace"
INBOX = WORK / "inbox"
INBOX.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT))
from viksetu.backend.geo_utils import (  # noqa: E402
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
        raise HTTPException(404, f"Missing {path.name}. Run: python viksetu/scripts/fetch_geo.py")
    return json.loads(path.read_text(encoding="utf-8"))


def load_geojson(name: str) -> dict:
    return load_json(GEO / name)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "viksetu", "llm": os.environ.get("LLM_PROVIDER", "gemini")}


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
        raise HTTPException(404, "Missing talukas.geojson. Run: python viksetu/scripts/fetch_talukas_and_pois.py")
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
        raise HTTPException(404, "No bbox. Run: python viksetu/scripts/compute_palghar_bbox.py")
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


def _load_poi_cards_index() -> dict:
    if not POI_CARDS.is_file():
        raise HTTPException(
            404,
            "Missing poi_cards.json. Run: python viksetu/scripts/build_poi_cards.py",
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
    pins = _load_poi_cards_index()
    if pin_id not in pins:
        raise HTTPException(404, f"Unknown pin_id: {pin_id}")
    return pins[pin_id]


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
    log: list[dict] = Field(default_factory=list)
    map: dict = Field(default_factory=dict)


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
        item = {"path": path.relative_to(WORK).as_posix(), "bytes": path.stat().st_size}
        if path.suffix.lower() in {".txt", ".md", ".csv", ".json"} and len(files) < 6:
            item["preview"] = path.read_text(encoding="utf-8", errors="replace")[:1200]
        files.append(item)
        if len(files) >= 40:
            break
    return files


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
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "Stopped after 15 seconds.", "code": 124}
    return {
        "ok": completed.returncode == 0,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-4000:],
        "code": completed.returncode,
    }


def _split_python(actions: list) -> tuple[list, list]:
    kept, notes = [], []
    for action in actions:
        if isinstance(action, dict) and action.get("op") == "python":
            notes.append(_run_python(str(action.get("code") or "")))
        else:
            kept.append(action)
    return kept, notes


@app.post("/api/canvas/files")
def upload_canvas_file(req: FileUpload):
    try:
        raw = base64.b64decode(req.data_b64, validate=True)
    except Exception as exc:
        raise HTTPException(400, f"Could not read that file: {exc}") from exc
    if len(raw) > 8_000_000:
        raise HTTPException(400, "File is larger than 8 MB.")
    name = _safe_name(req.name)
    dest = INBOX / name
    dest.write_bytes(raw)
    preview = ""
    if dest.suffix.lower() in {".txt", ".md", ".csv", ".json"}:
        preview = dest.read_text(encoding="utf-8", errors="replace")[:4000]
    return {"fileId": name, "name": name, "bytes": len(raw), "preview": preview}


@app.post("/api/canvas/python")
def canvas_python(req: PythonRequest):
    """Run a script inside viksetu/agent_workspace. It can read inbox/ and write files there."""
    return _run_python(req.code)


def _parse_canvas_turn(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return {"reply": text.strip(), "actions": []}
    data = json.loads(cleaned[start : end + 1])
    reply = data.get("reply")
    actions = data.get("actions")
    if not isinstance(reply, str):
        reply = text.strip()
    if not isinstance(actions, list):
        actions = []
    return {"reply": reply, "actions": actions}


CANVAS_SYSTEM = (
    "You are the VikSetu canvas agent. You share one tldraw page with the user. "
    "Every object in Canvas JSON has id, type, x, y, w, h (page position and size), text, and detail. "
    "Use those coordinates and sizes when you place or refer to an object. "
    "Map JSON lists which layers are enabled or disabled, the enabled pins (pinId, name, category, lng, lat), "
    "and the selected pin. Pin cards JSON has the full record for the selected pin and any pin the user named. "
    "Spend JSON is the real FY 2024-25 extract. Workspace files live in viksetu/agent_workspace, dropped files in inbox/. "
    "Reply with JSON only: {\"reply\": string, \"actions\": array}. actions may be empty. "
    "Allowed actions: "
    "{\"op\":\"geo\",\"text\":string,\"geo\":\"rectangle|ellipse|diamond|triangle|hexagon\",\"x\":number,\"y\":number,\"w\":number,\"h\":number,"
    "\"color\":\"black|grey|violet|blue|light-blue|yellow|orange|green|red\"}, "
    "{\"op\":\"text\",\"text\":string,\"x\":number,\"y\":number,\"color\":string}, "
    "{\"op\":\"map\",\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"chart\",\"title\":string,\"chart\":\"bar|line|pie\",\"labels\":[string],\"values\":[number],\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"doc\",\"title\":string,\"format\":\"md|text\",\"body\":string,\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"sheet\",\"title\":string,\"columns\":[string],\"rows\":[[string]],\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"file\",\"x\":number,\"y\":number,\"w\":number,\"h\":number}, "
    "{\"op\":\"python\",\"code\":string}, "
    "{\"op\":\"arrow\",\"from\":string,\"to\":string} using an existing id or new:0, "
    "{\"op\":\"delete\",\"ids\":[string]}, {\"op\":\"zoom\"}. "
    "Pass id on chart, doc, or sheet to update that object instead of creating one. "
    "python runs in the workspace only, then you are called again with its stdout. "
    "Build charts and sheets from Spend JSON, pin counts, sheet cells, or file previews. Do not invent budget numbers."
)


def _canvas_context(req: CanvasChatRequest) -> str:
    layers = (req.map or {}).get("layers") or {}
    enabled = [name for name, on in layers.items() if on]
    disabled = [name for name, on in layers.items() if not on]
    pins = (req.map or {}).get("pins") or []
    return "\n".join(
        [
            "Canvas JSON:\n" + json.dumps(req.canvas[:40], ensure_ascii=False),
            "Change log JSON:\n" + json.dumps(req.log[-30:], ensure_ascii=False),
            "Map layers enabled: " + json.dumps(enabled),
            "Map layers disabled: " + json.dumps(disabled),
            f"Enabled pins ({(req.map or {}).get('enabledCount', len(pins))} total, {min(len(pins), 180)} listed):\n"
            + json.dumps(pins[:180], ensure_ascii=False),
            "Selected pin:\n" + json.dumps((req.map or {}).get("selected"), ensure_ascii=False),
            "Pin cards JSON:\n" + json.dumps(_pin_cards_for(req.map or {}, req.message), ensure_ascii=False),
            "Spend JSON:\n" + json.dumps(_spend_brief(), ensure_ascii=False),
            "Workspace files:\n" + json.dumps(_workspace_files(), ensure_ascii=False),
        ]
    )


@app.post("/api/canvas/chat")
def canvas_chat(req: CanvasChatRequest):
    """LLM turn with shapes, sizes, live pins, files, and an optional workspace Python step."""
    messages: list[dict] = [{"role": "system", "content": CANVAS_SYSTEM}]
    history = req.history[-12:]
    if not history or history[-1].get("text") != req.message:
        history = [*history, {"role": "user", "text": req.message}]
    for index, turn in enumerate(history):
        role = "assistant" if turn.get("role") in ("agent", "assistant") else "user"
        content = str(turn.get("text") or "")
        if index == len(history) - 1 and role == "user":
            content += "\n\n" + _canvas_context(req)
        messages.append({"role": role, "content": content})
    try:
        from llm import chat

        result = chat(messages, temperature=0.2, json_mode=True, timeout=90)
        turn = _parse_canvas_turn(result["text"])
        actions, python_notes = _split_python(turn["actions"])
        reply = turn["reply"]
        if python_notes:
            messages.append({"role": "assistant", "content": result["text"]})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Python result from the workspace:\n"
                        + json.dumps(python_notes, ensure_ascii=False)
                        + "\nReply with JSON again. Put the result on the canvas with chart, doc, or sheet. Do not use python."
                    ),
                }
            )
            follow = chat(messages, temperature=0.2, json_mode=True, timeout=90)
            second = _parse_canvas_turn(follow["text"])
            actions, _extra = _split_python(second["actions"])
            reply = second["reply"]
            printed = "\n".join(note.get("stdout") or note.get("stderr") or "" for note in python_notes).strip()
            if printed:
                reply = f"{reply}\n\n{printed[:1200]}"
            result = follow
        return {
            "reply": reply,
            "actions": actions,
            "source": "llm",
            "provider": result.get("provider"),
            "model": result.get("model"),
        }
    except Exception as exc:
        return {
            "reply": f"The model did not answer: {exc}",
            "actions": [],
            "source": "error",
            "provider": os.environ.get("LLM_PROVIDER", "textgen"),
            "model": None,
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
