"""
Lab B, steps 4-6 - measure the prompt instead of trusting it.

Run it:  python 04_classify_eval.py

Twenty labelled reviews, one classification prompt, one accuracy number. Then
change the prompt and see the number move. This is the whole idea of Day 5
introduced on Day 1 with twenty rows instead of a benchmark suite.

Try these, in order, and record the accuracy each time:
  1. PROMPT_BARE      - no guidance at all
  2. PROMPT_LABELLED  - names the three allowed labels
  3. PROMPT_DEFINED   - defines what "neutral" actually means
and then write a fourth of your own that beats all three.
"""

import csv
import os
import sys
from collections import Counter

from llm import ask, run, which

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "reviews.csv")

LABELS = ("positive", "negative", "neutral")

PROMPT_BARE = """What is the sentiment of this review?

Review: %s"""

PROMPT_LABELLED = """Classify the sentiment of the review below.
Answer with exactly one word: positive, negative, or neutral.

Review: %s"""

PROMPT_DEFINED = """Classify the sentiment of the review below.

Answer with exactly one word, chosen from:
  positive - the reviewer is satisfied overall
  negative - the reviewer is dissatisfied overall
  neutral  - the reviewer states facts without approval or complaint,
             or is equally positive and negative

Answer with the single word only, no punctuation, no explanation.

Review: %s"""

PROMPTS = {
    "1-bare": PROMPT_BARE,
    "2-labelled": PROMPT_LABELLED,
    "3-defined": PROMPT_DEFINED,
}


def load_rows():
    if not os.path.exists(DATA):
        sys.exit("Cannot find %s - run this script from the code/ folder." % DATA)
    with open(DATA, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalise(reply):
    """Pull a label out of whatever the model said."""
    low = reply.strip().lower()
    for label in LABELS:
        if label in low:
            return label
    return "unparsed"


def evaluate(name, template, rows):
    correct = 0
    unparsed = 0
    mistakes = []
    for row in rows:
        want = row["label"].strip().lower()
        raw = ask(template % row["text"], temperature=0.0, max_tokens=20)
        got = normalise(raw)
        if got == "unparsed":
            unparsed += 1
        if got == want:
            correct += 1
        else:
            mistakes.append((row["id"], want, got, row["text"]))
    acc = correct / len(rows) * 100
    print("  %-12s accuracy %5.1f%%  (%d/%d)   unparsable replies: %d"
          % (name, acc, correct, len(rows), unparsed))
    return acc, mistakes


def main():
    rows = load_rows()
    print("Backend:", which())
    print("Cases  :", len(rows))
    print("=" * 68)
    print("Accuracy by prompt")
    print("-" * 68)

    results = {}
    all_mistakes = {}
    for name, template in PROMPTS.items():
        acc, mistakes = evaluate(name, template, rows)
        results[name] = acc
        all_mistakes[name] = mistakes

    print("=" * 68)
    best = max(results, key=results.get)
    worst = min(results, key=results.get)
    print("Best: %s at %.1f%%   Worst: %s at %.1f%%   Spread: %.1f points"
          % (best, results[best], worst, results[worst],
             results[best] - results[worst]))
    print()
    print("Same model, same data. The only thing that changed was the prompt.")
    print()

    print("Where the best prompt still got it wrong")
    print("-" * 68)
    if not all_mistakes[best]:
        print("  Nothing. Write a harder test set - twenty easy rows flatter a prompt.")
    else:
        for rid, want, got, text in all_mistakes[best]:
            print("  #%s  expected %-8s got %-9s  %s" % (rid, want, got, text[:44]))
        confused = Counter((w, g) for _, w, g, _ in all_mistakes[best])
        print()
        print("  Most common confusion: %s"
              % ", ".join("%s read as %s (x%d)" % (w, g, n)
                          for (w, g), n in confused.most_common(3)))
        print()
        print("  Look at those rows. Is the model wrong, or is the LABEL wrong?")
        print("  Disagreeing with your own test set is a normal Day 1 discovery.")


if __name__ == "__main__":
    run(main)
