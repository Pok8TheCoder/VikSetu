"""
Day 2, Lab A - one tool call, chosen by the model.

Run it:  python 05_tool_call_once.py

Not an agent yet. One question, one decision, one tool call, stop. Get this
reliable before you add a loop, because a loop built on an unreliable step just
fails repeatedly and more expensively.

What to watch
-------------
  * The model does NOT run anything. It returns a name and arguments. Your
    dispatcher decides whether to honour that.
  * Try the questions at the bottom. Some pick the right tool, some do not.
    Note which, and why.
"""

import json

from llm import ask_json, run, which
from tools import ToolError, run_tool, tool_specs

SYSTEM = """You are the decision step of a tool-using agent.

You have these tools:

%s

Reply with ONLY a JSON object, no prose and no code fence, in one of two forms:

  To use a tool:   {"tool": "<name>", "args": {<arguments>}}
  To answer:       {"answer": "<your answer>"}

Rules:
  - Never do arithmetic yourself. Use the calculator tool.
  - Never guess what is in the dataset. Call sensor_schema_info first.
  - Use only the argument names listed above.
"""

QUESTIONS = [
    "What is 847 multiplied by 36?",
    "What was the average soil moisture in September?",
    "What is in the sensor dataset?",
    "What is the capital of France?",
]


def decide(question):
    """Ask the model for one decision and return the parsed object."""
    system = SYSTEM % tool_specs()
    return ask_json(question, system=system, temperature=0.0)


def main():
    print("Backend:", which())
    print("=" * 70)

    for question in QUESTIONS:
        print("\nQ: %s" % question)
        print("-" * 70)
        try:
            decision = decide(question)
        except Exception as e:
            print("   the model did not return usable JSON: %s" % e)
            continue

        print("   model returned: %s" % json.dumps(decision))

        if "answer" in decision:
            print("   -> answered directly, no tool used")
            print("   -> %s" % decision["answer"])
            continue

        if "tool" not in decision:
            print("   -> neither a tool nor an answer. This is failure mode 3")
            print("      from Day 1: valid JSON, wrong shape.")
            continue

        name = decision["tool"]
        args = decision.get("args", {})
        try:
            observation = run_tool(name, args)
        except ToolError as e:
            print("   -> dispatcher REFUSED the call: %s" % e)
            print("      Note that your code caught this, not the model.")
            continue

        print("   -> ran %s(%s)" % (name, json.dumps(args)))
        print("   -> observation: %s" % observation[:200])

    print("\n" + "=" * 70)
    print("Questions to answer in your notebook:")
    print("  1. Which question made the model answer without a tool? Was it right to?")
    print("  2. Did it ever call sensor_query without checking the schema first?")
    print("  3. One observation came back. Who turns that into a final answer?")
    print("     Nobody, yet. That is what the loop in 06 is for.")


if __name__ == "__main__":
    run(main)
