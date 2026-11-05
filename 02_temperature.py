"""
Lab A, step 5 - temperature, and why agents use 0.

Run it:  python 02_temperature.py

The same prompt is sent five times at temperature 0.0 and five times at 1.0.
Count how many distinct answers come back from each.

The point of the exercise
------------------------
An agent decides which tool to call by generating text. If that text is not
reproducible, neither is the agent. Creative writing wants temperature; an
agent choosing an action does not. This is why every tool-calling example from
Day 2 onward pins temperature to 0.

Note: temperature 0 is "as repeatable as possible", not "guaranteed
identical". Hosted models batch requests across users and can still vary. If
your five answers at 0.0 are not all the same, that is a real finding - write
it down, it matters on Day 5 when we build the benchmark.
"""

from llm import chat, run, which

PROMPT = "Give one short name for a project that monitors soil moisture. Name only."
RUNS = 5


def sample(temperature):
    answers = []
    total_latency = 0.0
    for _ in range(RUNS):
        reply = chat([{"role": "user", "content": PROMPT}],
                     temperature=temperature, max_tokens=30)
        answers.append(reply["text"].strip())
        total_latency += reply["latency_s"]
    return answers, total_latency / RUNS


def report(temperature):
    answers, avg = sample(temperature)
    unique = sorted(set(answers))
    print("temperature = %.1f" % temperature)
    for i, a in enumerate(answers, 1):
        print("   %d. %s" % (i, a.replace("\n", " ")[:70]))
    print("   -> %d distinct answer(s) out of %d, average %.2f s"
          % (len(unique), RUNS, avg))
    print()
    return len(unique)


def main():
    print("Backend:", which())
    print("Prompt :", PROMPT)
    print("=" * 64)
    cold = report(0.0)
    hot = report(1.0)

    print("=" * 64)
    print("At 0.0 you saw %d distinct answer(s); at 1.0 you saw %d." % (cold, hot))
    if hot > cold:
        print("That spread is exactly what you do not want when a model is")
        print("choosing which tool to call. Hence temperature=0 from Day 2.")
    else:
        print("No extra spread this time - small models are sometimes stubborn.")
        print("Try a more open-ended prompt and run it again.")


if __name__ == "__main__":
    run(main)
