"""
llm.py - minimal LLM client for Indus Training labs.

Backends (OpenAI-compatible /chat/completions):
  textgen  text-generation-webui on localhost (default here)
  ollama   local Ollama
  gemini   Google Gemini (hosted)

    set LLM_PROVIDER=textgen|ollama|gemini

Environment variables
---------------------
    LLM_PROVIDER       default "textgen"
    TEXTGEN_BASE_URL   default "http://127.0.0.1:5000/v1"
    TEXTGEN_MODEL      optional; else uses the model loaded in the UI
    TEXTGEN_API_KEY    default "none"
    OLLAMA_MODEL       default "llama3.2:3b"
    OLLAMA_BASE        default "http://localhost:11434/v1"
    GOOGLE_API_KEY     required for gemini
    GEMINI_MODEL       default "gemini-2.0-flash"
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TEXTGEN_BASE = os.environ.get("TEXTGEN_BASE_URL", "http://127.0.0.1:5000/v1")
TEXTGEN_MODEL = os.environ.get("TEXTGEN_MODEL", "").strip() or None
TEXTGEN_API_KEY = os.environ.get("TEXTGEN_API_KEY", "none")

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

GEMINI_BASE = os.environ.get(
    "GEMINI_BASE",
    "https://generativelanguage.googleapis.com/v1beta/openai",
)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "textgen").strip().lower()

_textgen_loaded_model = None
_TOKENS_USED = 0


def tokens_used():
    return _TOKENS_USED


class LLMError(RuntimeError):
    """Raised with a message a student can act on."""


def _get_json(url, headers, timeout):
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url, payload, headers, timeout):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _textgen_model_name():
    global _textgen_loaded_model
    if TEXTGEN_MODEL:
        return TEXTGEN_MODEL
    if _textgen_loaded_model:
        return _textgen_loaded_model
    base = TEXTGEN_BASE.rstrip("/")
    info = _get_json(
        base + "/internal/model/info",
        {"Authorization": "Bearer " + TEXTGEN_API_KEY},
        timeout=30,
    )
    name = info.get("model_name")
    if not name:
        raise LLMError(
            "No model loaded in text-generation-webui.\n"
            "  Load a model in the UI, or set TEXTGEN_MODEL."
        )
    _textgen_loaded_model = name
    return name


def _endpoint(provider):
    if provider == "textgen":
        return (
            TEXTGEN_BASE.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + TEXTGEN_API_KEY},
            _textgen_model_name(),
        )
    if provider == "ollama":
        return OLLAMA_BASE.rstrip("/") + "/chat/completions", {}, OLLAMA_MODEL
    if provider == "gemini":
        key = os.environ.get("GOOGLE_API_KEY", "").strip()
        if not key:
            raise LLMError(
                "GOOGLE_API_KEY is not set.\n"
                "  1. Get a free key at https://aistudio.google.com/apikey\n"
                "  2. Windows:  set GOOGLE_API_KEY=your_key_here\n"
                "     mac/Linux: export GOOGLE_API_KEY=your_key_here\n"
                "  Never paste the key into a .py file you will commit."
            )
        return (
            GEMINI_BASE.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + key},
            GEMINI_MODEL,
        )
    raise LLMError(
        "Unknown provider %r. Use 'textgen', 'ollama', or 'gemini'." % provider
    )


def chat(messages, provider=None, model=None, temperature=0.0,
         max_tokens=None, json_mode=False, timeout=120):
    provider = (provider or DEFAULT_PROVIDER).strip().lower()
    url, headers, default_model = _endpoint(provider)
    model = model or default_model

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    # text-generation-webui often 500s on response_format; prompt still asks for JSON.
    if json_mode and provider != "textgen":
        payload["response_format"] = {"type": "json_object"}

    started = time.time()
    try:
        data = _post_json(url, payload, headers, timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        if json_mode and ("response_format" in detail or e.code == 400):
            payload.pop("response_format", None)
            started = time.time()
            data = _post_json(url, payload, headers, timeout)
        elif e.code in (401, 403):
            raise LLMError(
                "%s rejected the API key (HTTP %d).\n%s"
                % (provider, e.code, detail)
            )
        elif e.code == 404:
            raise LLMError(
                "%s has no model called %r (HTTP 404).\n"
                "  textgen: load a model in the UI or set TEXTGEN_MODEL\n"
                "  Ollama:  ollama pull %s\n%s"
                % (provider, model, OLLAMA_MODEL, detail)
            )
        elif e.code == 429:
            raise LLMError(
                "%s rate limit reached (HTTP 429). Wait a minute, or switch "
                "provider with LLM_PROVIDER.\n%s" % (provider, detail)
            )
        else:
            raise LLMError("%s returned HTTP %d.\n%s" % (provider, e.code, detail))
    except urllib.error.URLError as e:
        if provider == "textgen":
            raise LLMError(
                "Cannot reach text-generation-webui at %s (%s).\n"
                "  1. Is it running with the OpenAI API enabled (--api)?\n"
                "  2. Is the default port 5000? Set TEXTGEN_BASE_URL if not.\n"
                "  3. Or switch:  set LLM_PROVIDER=ollama  or  gemini"
                % (TEXTGEN_BASE, e.reason)
            )
        if provider == "ollama":
            raise LLMError(
                "Cannot reach Ollama at %s (%s).\n"
                "  1. Is it running?  ollama serve\n"
                "  2. Model installed?  ollama pull %s\n"
                "  3. Or switch:  set LLM_PROVIDER=textgen"
                % (OLLAMA_BASE, e.reason, OLLAMA_MODEL)
            )
        raise LLMError(
            "Cannot reach %s (%s). Check the network and the firewall."
            % (provider, e.reason)
        )

    latency = time.time() - started

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError(
            "Unexpected response shape from %s:\n%s"
            % (provider, json.dumps(data)[:600])
        )

    usage = data.get("usage") or {}

    global _TOKENS_USED
    _TOKENS_USED += usage.get("total_tokens") or 0

    return {
        "text": (text or "").strip(),
        "provider": provider,
        "model": data.get("model", model),
        "latency_s": round(latency, 2),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "raw": data,
    }


def ask(prompt, system=None, **kwargs):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, **kwargs)["text"]


def ask_json(prompt, system=None, attempts=3, **kwargs):
    kwargs.setdefault("json_mode", True)
    kwargs.setdefault("temperature", 0.0)
    last = ""
    for attempt in range(1, attempts + 1):
        last = ask(prompt, system=system, **kwargs)
        cleaned = last.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
            if cleaned.lstrip().lower().startswith("json"):
                cleaned = cleaned.lstrip()[4:]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == attempts:
                break
    raise LLMError(
        "Model did not return valid JSON after %d attempts.\n"
        "Last reply was:\n%s" % (attempts, last[:600])
    )


def run(main_fn):
    try:
        main_fn()
    except LLMError as e:
        print()
        print("-" * 64)
        print("SETUP PROBLEM - the code is fine, the backend is not reachable")
        print("-" * 64)
        print(str(e))
        print("-" * 64)
        print("For a full diagnosis run:  python check_setup.py")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)


def which():
    p = DEFAULT_PROVIDER
    if p == "textgen":
        model = TEXTGEN_MODEL or "(loaded in UI)"
        return "textgen  model=%s  base=%s" % (model, TEXTGEN_BASE)
    if p == "ollama":
        return "ollama  model=%s  base=%s" % (OLLAMA_MODEL, OLLAMA_BASE)
    return "gemini  model=%s  key=%s" % (
        GEMINI_MODEL,
        "set" if os.environ.get("GOOGLE_API_KEY") else "MISSING",
    )


if __name__ == "__main__":
    print("Active backend:", which())
    print("Reply:", ask("Reply with exactly the word: ready"))
