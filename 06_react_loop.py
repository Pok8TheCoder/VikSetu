"""
Day 2, Lab B - the ReAct loop: reason, act, observe, repeat.

Run it:  python 06_react_loop.py

05_tool_call_once.py stops after one tool call. The model never turns the
observation into a final answer. This script runs the same kind of questions
through agent.run_agent(), which feeds each tool result back until the model
replies with {"answer": "..."} or the step budget runs out.
"""

from agent import run_agent
from llm import run, which

QUESTIONS = [
    "What is 847 multiplied by 36?",
    "What was the average soil moisture in September?",
    "By how many degrees did the hottest day in September exceed the coldest?",
]


def main():
    print("Backend:", which())
    print("=" * 70)

    for question in QUESTIONS:
        print()
        trace = run_agent(question, verbose=True)
        if trace.answer is None:
            print("   (no final answer — check the trace above)")
        print("-" * 70)

    print()
    print("Compare with 05: there each question got at most one tool call and")
    print("no loop. Here the history after each OBSERVATION is what lets the")
    print("model finish in a second step.")


if __name__ == "__main__":
    run(main)
