"""
check_setup.py - run this FIRST, on every machine, before the lab starts.

It checks both backends and tells you exactly what is wrong, in order of what
to fix first. Run it yourself on your own machine, then have every student run
it in the first fifteen minutes of Day 1. It is the single highest-value five
minutes of the week: it catches a missing model, a blocked firewall or an unset
API key while there is still time to fix them.

    python check_setup.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

import llm

OK = "  [ OK ]  "
NO = "  [FAIL]  "
INFO = "  [ -- ]  "

results = {}


def line(status, label, detail=""):
    print(status + label + (("  " + detail) if detail else ""))


def check_python():
    v = sys.version_info
    good = v >= (3, 8)
    line(OK if good else NO, "Python %d.%d.%d" % (v.major, v.minor, v.micro),
         "" if good else "need 3.8 or newer")
    results["python"] = good


def check_ollama_server():
    url = llm.OLLAMA_BASE.rstrip("/").replace("/v1", "") + "/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        names = [m.get("name", "?") for m in data.get("models", [])]
        line(OK, "Ollama is running", "at " + llm.OLLAMA_BASE)
        if not names:
            line(NO, "Ollama has no models installed",
                 "run:  ollama pull " + llm.OLLAMA_MODEL)
            results["ollama"] = False
            return
        line(INFO, "Models installed", ", ".join(names[:6]))
        wanted = llm.OLLAMA_MODEL
        family = [n for n in names if n.split(":")[0] == wanted.split(":")[0]]
        if wanted in names:
            line(OK, "Required model present", wanted)
            results["ollama"] = True
        elif family:
            # A family match is NOT a usable model. Ollama resolves tags
            # exactly, so asking for llama3.2:3b while holding
            # llama3.2:latest is a hard 404 - and reporting OK here would
            # hand the student a green tick followed by a crash. Name the
            # tag they actually have, and both ways out.
            line(NO, "Required model missing",
                 "you have %s, not %s" % (", ".join(family), wanted))
            line(INFO, "Fix (either one)",
                 "ollama pull %s   OR   set OLLAMA_MODEL=%s" % (wanted, family[0]))
            results["ollama"] = False
        else:
            line(NO, "Required model missing", "run:  ollama pull " + wanted)
            results["ollama"] = False
    except (urllib.error.URLError, OSError) as e:
        line(NO, "Ollama not reachable", str(getattr(e, "reason", e)))
        line(INFO, "Fix", "open a terminal and run:  ollama serve")
        results["ollama"] = False


def check_generation(provider):
    try:
        reply = llm.chat(
            [{"role": "user", "content": "Reply with exactly the word: ready"}],
            provider=provider, temperature=0.0, max_tokens=20, timeout=90)
        got = reply["text"].strip().lower()
        good = "ready" in got
        line(OK if good else INFO,
             "%s generated text" % provider,
             "%.2fs, model=%s, reply=%r" % (reply["latency_s"], reply["model"],
                                            reply["text"][:40]))
        if not good:
            line(INFO, "  note", "model replied but not as instructed - fine for now")
        results[provider + "_gen"] = True
    except llm.LLMError as e:
        line(NO, "%s could not generate" % provider)
        for ln in str(e).splitlines():
            print("           " + ln)
        results[provider + "_gen"] = False


def check_gemini_key():
    if os.environ.get("GOOGLE_API_KEY", "").strip():
        line(OK, "GOOGLE_API_KEY is set")
        results["gemini_key"] = True
    else:
        line(INFO, "GOOGLE_API_KEY is not set",
             "only needed for the hosted backend")
        results["gemini_key"] = False


def main():
    print()
    print("=" * 68)
    print("  Agentic AI Systems - setup check")
    print("=" * 68)

    print("\n1. Python")
    check_python()

    print("\n2. Ollama (local model)")
    check_ollama_server()
    if results.get("ollama"):
        check_generation("ollama")

    print("\n3. Google Gemini (hosted model)")
    check_gemini_key()
    if results.get("gemini_key"):
        check_generation("gemini")

    print("\n" + "=" * 68)
    local = results.get("ollama_gen", False)
    hosted = results.get("gemini_gen", False)

    if local and hosted:
        print("  READY - both backends work. You can run every lab this week.")
    elif local:
        print("  READY - the local Ollama backend works.")
        print("  The hosted backend is not set up. That is fine for Day 1;")
        print("  set GOOGLE_API_KEY before the Day 1 comparison exercise.")
    elif hosted:
        print("  READY - the hosted Gemini backend works.")
        print("  Ollama is not available, so run the labs with:")
        print("      set LLM_PROVIDER=gemini      (Windows)")
        print("      export LLM_PROVIDER=gemini   (mac/Linux)")
    else:
        print("  NOT READY - neither backend works. Fix the [FAIL] lines above.")
        print("  Fastest route to a working lab: get a free key from")
        print("  https://aistudio.google.com/apikey and set GOOGLE_API_KEY.")
    print("=" * 68)
    print("  Active default backend:", llm.which())
    print()
    return 0 if (local or hosted) else 1


if __name__ == "__main__":
    sys.exit(main())
