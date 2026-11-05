"""
Day 3, Lab A - budgets, retries and the trace.

Run it:  python 07_robust_agent.py

Day 2's loop worked when things went well. This shows the five additions in
agent.py doing their job, including a budget deliberately set too low so you
can watch it stop the agent.

By the end of this script you should be able to answer: when my agent gives a
wrong answer, which line of the trace do I look at first?
"""

from agent import Budget, run_agent
from llm import run, which

QUESTION = ("By how many degrees did the hottest day in September exceed "
            "the coldest day?")


def part1_normal():
    print("\n" + "=" * 72)
    print("PART 1 - a normal run, with the full trace")
    print("=" * 72)
    trace = run_agent(QUESTION, verbose=True)
    return trace


def part2_tight_budget():
    print("\n" + "=" * 72)
    print("PART 2 - the same question with a budget of 2 steps")
    print("=" * 72)
    print("This question needs three or four steps. Watch it get cut off.\n")
    trace = run_agent(QUESTION, budget=Budget(steps=2), verbose=True)
    print()
    if trace.answer is None:
        print("Stopped because: %s. No answer, and that is correct behaviour -" %
              trace.stopped_because)
        print("a truncated agent should return nothing rather than guess.")
    else:
        print("It answered inside two steps. Lower the budget to 1 and try again.")
    return trace


def part3_bad_arguments():
    print("\n" + "=" * 72)
    print("PART 3 - forcing the model into a tool error")
    print("=" * 72)
    print("Asking for a metric that does not exist. The tool refuses, the")
    print("refusal goes back as an observation, and the model should recover.\n")
    trace = run_agent("What was the total rainfall in September?", verbose=True)
    print()
    print("tool_errors recorded: %d" % trace.tool_errors)
    if trace.tool_errors:
        print("Good - the dispatcher refused and the model saw why.")
        print("Did it then recover, or keep trying the same bad call?")
    else:
        print("No tool error. The model may have answered from the schema alone,")
        print("which is the right behaviour. Read the trace and decide.")
    return trace


def part4_only_one_tool():
    print("\n" + "=" * 72)
    print("PART 4 - the same question with the calculator taken away")
    print("=" * 72)
    print("Tools restricted to the sensor ones. The model must now either do")
    print("arithmetic itself (which we told it not to) or admit it cannot.\n")
    trace = run_agent(QUESTION, tools=["sensor_query", "sensor_schema_info"],
                      verbose=True)
    print()
    print("If it produced a number, check it by hand. An agent doing its own")
    print("arithmetic is a very common source of confidently wrong answers.")
    return trace


def main():
    print("Backend:", which())
    traces = [part1_normal(), part2_tight_budget(),
              part3_bad_arguments(), part4_only_one_tool()]

    print("\n" + "=" * 72)
    print("COMPARISON")
    print("=" * 72)
    print("%-26s %-9s %-7s %-7s %-7s %s"
          % ("part", "answered", "steps", "tools", "errors", "seconds"))
    labels = ["1 normal", "2 tight budget", "3 bad arguments", "4 no calculator"]
    for label, t in zip(labels, traces):
        s = t.summary()
        print("%-26s %-9s %-7d %-7d %-7d %.1f"
              % (label, s["answered"], s["steps"], s["tool_calls"],
                 s["tool_errors"], s["seconds"]))

    print()
    print("Record this table. On Saturday you will run it again after hardening")
    print("the agent, and the difference is your evidence that you improved it.")


if __name__ == "__main__":
    run(main)