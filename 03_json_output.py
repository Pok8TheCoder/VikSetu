"""
Lab B, steps 1-3 - making the model speak a format your code can trust.

Run it:  python 03_json_output.py

Why this is the most important script of Day 1
----------------------------------------------
From Day 2 the model's reply is no longer read by a human - it is parsed by
your program to decide which function to call. A reply that is "almost JSON"
is a crash. This script shows three stages:

  Stage 1  Ask politely in prose          -> often fails
  Stage 2  Ask with an explicit schema    -> usually works
  Stage 3  Validate, and retry on failure -> what agents actually do
"""

import json

from llm import ask, ask_json, run, which

REVIEW = ("Shipping took nine days and the box was crushed, but the sensor "
          "itself works perfectly and the price was fair.")

SCHEMA_PROMPT = """Extract structured data from the product review below.

Return ONLY a JSON object, with no commentary and no code fence, exactly in
this shape:

{
  "sentiment": "positive" | "negative" | "mixed",
  "topics": [string, ...],
  "mentions_price": true | false,
  "confidence": number between 0 and 1
}

Review:
\"\"\"%s\"\"\"
"""


def stage1_naive():
    print("STAGE 1 - asking in prose, no schema")
    print("-" * 64)
    text = ask("Summarise the sentiment of this review as JSON: " + REVIEW)
    print(text[:400])
    try:
        json.loads(text)
        print("\n   Parsed cleanly this time. Run it again - it will not always.")
    except json.JSONDecodeError as e:
        print("\n   json.loads() FAILED: %s" % e)
        print("   This is the failure mode that breaks agents. Note what the")
        print("   model added around the JSON - prose, a code fence, or both.")
    print()


def stage2_schema():
    print("STAGE 2 - the same request with an explicit schema")
    print("-" * 64)
    text = ask(SCHEMA_PROMPT % REVIEW, temperature=0.0)
    print(text[:400])
    try:
        json.loads(text)
        print("\n   Parsed cleanly.")
    except json.JSONDecodeError as e:
        print("\n   Still not valid: %s" % e)
        print("   Which is why stage 3 exists.")
    print()


def stage3_validated():
    print("STAGE 3 - validate, retry, and check the fields you rely on")
    print("-" * 64)
    data = ask_json(SCHEMA_PROMPT % REVIEW, attempts=3)
    print(json.dumps(data, indent=2)[:500])

    problems = []
    if data.get("sentiment") not in ("positive", "negative", "mixed"):
        problems.append("sentiment is %r, not one of the three allowed values"
                        % data.get("sentiment"))
    if not isinstance(data.get("topics"), list):
        problems.append("topics is not a list")
    if not isinstance(data.get("mentions_price"), bool):
        problems.append("mentions_price is not a boolean")
    conf = data.get("confidence")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        problems.append("confidence is %r, not a number in 0..1" % conf)

    print()
    if problems:
        print("   Valid JSON, but the CONTENT broke the contract:")
        for p in problems:
            print("     - " + p)
        print("   Valid syntax is not a valid answer. Remember this on Day 2:")
        print("   you validate the arguments before you call a tool with them.")
    else:
        print("   JSON valid AND every field within contract. This is the bar.")
    print()


def main():
    print("Backend:", which())
    print("=" * 64)
    stage1_naive()
    stage2_schema()
    stage3_validated()
    print("=" * 64)
    print("Takeaway: ask_json() in llm.py does stage 3 for you. Read it -")
    print("it is twenty lines, and every agent framework does the same thing.")


if __name__ == "__main__":
    run(main)
