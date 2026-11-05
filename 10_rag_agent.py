"""
Day 4, Lab B - retrieval as a tool the agent can choose to use.

Run it:
    python 10_rag_agent.py                       uses the keyword index
    python 10_rag_agent.py --vector              uses the embedding index
    python 10_rag_agent.py "your question here"

Build an index first with 09_build_index.py.

The idea
--------
Retrieval is not a special mode. It is one more tool. The agent decides whether
a question needs the documents, the sensor numbers, the calculator, or several
of them - and that decision is the interesting part.

Watch for the question that needs BOTH the documents and the data. That is
where a retrieval pipeline stops being enough and an agent starts to earn its
cost.
"""

import argparse
import os
import sys

import tools
from agent import Budget, run_agent
from llm import run, which
from store import load_index

HERE = os.path.dirname(os.path.abspath(__file__))
INDEXES = {
    False: os.path.join(HERE, "data", "index_keyword.json"),
    True: os.path.join(HERE, "data", "index_vector.json"),
}

QUESTIONS = [
    # documents only
    "Why might a probe read wetter than the soil really is?",
    # data only
    "What was the lowest soil moisture reading in September?",
    # BOTH - this is the one to watch
    "Soil moisture hit its lowest point in September. According to the "
    "irrigation policy, should that have been treated as a dry spell or as a "
    "fault, and what does the maintenance log say the cause was?",
]


def register_search_tool(index):
    """Add a search_docs tool to the registry at run time."""

    def search_docs(query):
        hits = index.search(query, k=3)
        if not hits:
            return "no matching passages"
        return "\n\n".join(
            "[%s] (score %.3f)\n%s" % (source, score, " ".join(text.split()))
            for score, source, text in hits)

    tools.TOOLS["search_docs"] = {
        "fn": search_docs,
        "description": "Search the station documentation (field guide, "
                       "maintenance log, irrigation policy) and return the "
                       "three most relevant passages, each labelled with its "
                       "source file. Use this for anything about procedure, "
                       "policy, causes or history.",
        "parameters": {
            "query": {"type": "string", "required": True,
                      "description": "What to look for, in your own words"},
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", default=None)
    ap.add_argument("--vector", action="store_true")
    args = ap.parse_args()

    path = INDEXES[args.vector]
    if not os.path.exists(path):
        print("No index at %s" % os.path.basename(path))
        print("Build one first:")
        print("    python 09_build_index.py%s" % (" --vector" if args.vector else ""))
        sys.exit(1)

    index = load_index(path)
    register_search_tool(index)

    print("Backend:", which())
    print("Index  : %s, %d chunks" % (index.kind, len(index.chunks)))
    print("Tools  : %s" % ", ".join(tools.TOOLS))

    questions = [args.question] if args.question else QUESTIONS

    results = []
    for i, q in enumerate(questions, 1):
        print("\n" + "=" * 72)
        print("Q%d: %s" % (i, q))
        print("=" * 72)
        trace = run_agent(q, budget=Budget(steps=8), verbose=True)
        results.append((q, trace))

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print("%-4s %-9s %-7s %-7s %s" % ("q", "answered", "steps", "tools", "which tools"))
    for i, (q, t) in enumerate(results, 1):
        used = [e["tool"] for e in t.events if e["kind"] == "action"]
        s = t.summary()
        print("%-4d %-9s %-7d %-7d %s"
              % (i, s["answered"], s["steps"], s["tool_calls"],
                 ", ".join(dict.fromkeys(used)) or "-"))

    print()
    print("The question to answer in your notebook:")
    print("  On Q3, did the agent use search_docs AND sensor_query? If it used")
    print("  only one, its answer is incomplete even if it sounds confident.")
    print("  That is the failure a retrieval pipeline cannot make, because the")
    print("  pipeline always does the same thing - and the failure an agent")
    print("  can make, because it chooses. Both properties come from the same")
    print("  design decision.")


if __name__ == "__main__":
    run(main)