import llm

try:
    result = llm.chat(
        [
            {"role": "user", "content": "Reply with the single word pong."},
        ],
        json_mode=False,
        timeout=90,
        max_tokens=32,
    )
    print("OK", result["provider"], result["model"])
    print(result["text"][:500])
except Exception as exc:
    print(type(exc).__name__)
    print(exc)
