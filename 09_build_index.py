"""
Day 4, Lab A - chunk the documents and build a searchable index.

Run it:
    python 09_build_index.py                  keyword index, needs nothing
    python 09_build_index.py --vector         embeddings (needs an embed model)
    python 09_build_index.py --vector --size 300 --overlap 0

Then compare. The exercise is not "build a vector store"; it is "find out when
embeddings beat keywords and when they do not".
"""

import argparse
import os
import sys

from llm import run, which
from store import (KeywordIndex, StoreError, VectorIndex, chunk_text,
                   read_docs)

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "data", "docs")
OUT_VECTOR = os.path.join(HERE, "data", "index_vector.json")
OUT_KEYWORD = os.path.join(HERE, "data", "index_keyword.json")

PROBE_QUERIES = [
    "why would the probe read wetter than the soil actually is",
    "what should I do if moisture drops below 12 per cent",
    "when is the dry reference out of tolerance",
    "what happened on the 24th",
]


def build(use_vector, size, overlap):
    docs = read_docs(DOCS)
    print("Documents: %d" % len(docs))

    index = VectorIndex() if use_vector else KeywordIndex()
    total = 0
    for name, text in docs:
        pieces = chunk_text(text, size=size, overlap=overlap)
        print("  %-28s %6d chars -> %2d chunks" % (name, len(text), len(pieces)))
        for piece in pieces:
            index.add(name, piece)
            total += 1
    print("Chunks indexed: %d  (kind: %s)" % (total, index.kind))
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vector", action="store_true",
                    help="use embeddings instead of keyword scoring")
    ap.add_argument("--size", type=int, default=600)
    ap.add_argument("--overlap", type=int, default=120)
    args = ap.parse_args()

    print("Backend:", which())
    print("Chunking: size=%d overlap=%d" % (args.size, args.overlap))
    print("=" * 72)

    try:
        index = build(args.vector, args.size, args.overlap)
    except StoreError as e:
        print("\nCould not build the index:")
        for line in str(e).splitlines():
            print("  " + line)
        if args.vector:
            print("\nRun it without --vector to use the keyword index, which")
            print("needs no model at all, and come back to embeddings later.")
        sys.exit(1)

    out = OUT_VECTOR if args.vector else OUT_KEYWORD
    index.save(out)
    print("Saved: %s" % os.path.basename(out))

    print("\n" + "=" * 72)
    print("Four test queries. Judge each result yourself - is it the chunk you")
    print("would have wanted?")
    for q in PROBE_QUERIES:
        print("\nQ: %s" % q)
        print("-" * 72)
        for score, source, text in index.search(q, k=2):
            snippet = " ".join(text.split())[:150]
            print("  %7.4f  %-26s %s" % (score, source, snippet))

    print("\n" + "=" * 72)
    print("Record, in your notebook, for each of the four queries:")
    print("  did the top chunk actually contain the answer?  yes / partly / no")
    print()
    print("Then run these three and compare the table:")
    print("  python 09_build_index.py --size 300 --overlap 0")
    print("  python 09_build_index.py --size 600 --overlap 120")
    print("  python 09_build_index.py --vector --size 600 --overlap 120")
    print()
    print("Query 4 is the interesting one. 'What happened on the 24th' contains")
    print("almost no distinctive words, so keyword scoring struggles, while an")
    print("embedding may or may not do better. Find out rather than assume.")


if __name__ == "__main__":
    run(main)