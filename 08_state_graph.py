"""
Day 3, Lab B - the same agent, rebuilt as a state graph.

Run it:  python 08_state_graph.py

Identical behaviour to 06 and agent.py. The difference is shape: instead of a
for-loop with if-statements, the agent is three named nodes and two edges. Read
graph.py first - it is seventy lines.

Why anyone bothers
------------------
  * Each node is separately testable: you can call reason() on a fixed state.
  * The control flow is data, so you can draw it, log it, or change it without
    touching the nodes.
  * Adding a human approval step is a new node, not a new branch inside a loop.
  * This is what LangGraph, and the others, are underneath.

What it costs
-------------
  * More moving parts for a three-step agent. For Day 2's loop, overkill.
  * The state dict becomes the contract between nodes, and nothing checks it.

Both facts matter. Pick the loop when the agent is simple; pick the graph when
the flow branches or needs interrupting.
"""

import json

from agent import SYSTEM
try:
    from graph import END, Graph
except ImportError:
    raise SystemExit(
        "\ngraph.py is not in this folder yet.\n\n"
        "You write it yourself in Wednesday's Lab B - about seventy lines -\n"
        "and this script runs on top of it.\n\n"
        "  Already written it? Check it is saved in the same folder as this\n"
        "  file, and that it is called exactly graph.py\n")
from llm import LLMError, ask_json, run, which
from tools import ToolError, run_tool, tool_specs

MAX_STEPS = 6
QUESTION = ("Which day had the lowest soil moisture, and how far below the "
            "monthly average was it?")


# ----------------------------------------------------------------- the nodes

def reason(state):
    """Ask the model for the next action. Writes 'decision' into the state."""
    prompt = "QUESTION: %s\n\n%s" % (state["question"], "\n\n".join(state["history"]))
    try:
        decision = ask_json(prompt, system=state["system"], temperature=0.0,
                            attempts=2)
    except LLMError as e:
        return {**state,
                "decision": None,
                "step": state["step"] + 1,
                "history": state["history"] + [
                    "OBSERVATION: your previous reply was not valid JSON."],
                "log": state["log"] + ["reason: unparseable (%s)"
                                       % str(e).splitlines()[0][:60]]}
    thought = str(decision.get("thought", ""))[:120]
    return {**state,
            "decision": decision,
            "step": state["step"] + 1,
            "log": state["log"] + ["reason: %s" % (thought or "(no thought)")]}


def act(state):
    """Run the tool the model named, and append the observation."""
    decision = state["decision"] or {}
    name = decision.get("tool")
    args = decision.get("args") or {}
    if not name:
        return {**state,
                "history": state["history"] + [
                    "OBSERVATION: your reply had neither 'tool' nor 'answer'."],
                "log": state["log"] + ["act: nothing to do"]}
    try:
        observation = run_tool(name, args)
        note = "act: %s -> %s" % (name, observation[:60])
    except ToolError as e:
        observation = "ERROR: %s" % e
        note = "act: %s REFUSED (%s)" % (name, str(e)[:50])
    return {**state,
            "history": state["history"] + [
                "ACTION: %s(%s)\nOBSERVATION: %s"
                % (name, json.dumps(args), observation)],
            "log": state["log"] + [note]}


def finish(state):
    answer = (state["decision"] or {}).get("answer")
    return {**state, "answer": str(answer) if answer is not None else None,
            "log": state["log"] + ["finish"]}


# ----------------------------------------------------------------- the edges

def after_reason(state):
    """The only branching decision in the whole agent."""
    if state["step"] > MAX_STEPS:
        return "finish"
    decision = state["decision"]
    if decision and "answer" in decision:
        return "finish"
    return "act"


def build(question):
    g = Graph({
        "question": question,
        "system": SYSTEM % tool_specs(),
        "history": [],
        "step": 0,
        "decision": None,
        "answer": None,
        "log": [],
    })
    g.node("reason", reason)
    g.node("act", act)
    g.node("finish", finish)
    g.edge("reason", after_reason)
    g.edge("act", "reason")          # the loop, expressed as an edge
    g.edge("finish", END)
    g.entry("reason")
    return g


def main():
    print("Backend :", which())
    print("Question:", QUESTION)
    print("=" * 72)
    print("\nThe graph:")
    print("    reason --(answer? or out of steps?)--> finish --> END")
    print("       ^                                |")
    print("       |                                v")
    print("       +---------- act <----------------+")
    print("\nRunning:")

    g = build(QUESTION)
    final = g.run(verbose=True)

    print("\n" + "=" * 72)
    print("Node path : %s" % " -> ".join(g.path))
    print("Steps     : %d" % final["step"])
    print("Answer    : %s" % (final["answer"] or "(none - budget reached)"))
    print("\nWhat happened, node by node:")
    for i, entry in enumerate(final["log"], 1):
        print("  %2d. %s" % (i, entry))

    print("\n" + "=" * 72)
    print("Compare with 06_react_loop.py. Same answer, same tools, same model.")
    print("Exercise: add an 'approve' node between reason and act that prints")
    print("the proposed call and waits for you to type y. In the loop version")
    print("that is a new if-statement in the middle of the loop body; here it")
    print("is one node and one changed edge. That difference is the whole")
    print("argument for graphs.")


if __name__ == "__main__":
    run(main)
