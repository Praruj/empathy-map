"""Offline compiler: raw conversation logs -> public/data/empathy_db.json.

Free and self-contained: no API keys, no paid services. Runs on a laptop CPU or
a free GitHub Actions runner.

How a pivot is found
  1. Parse each log into turns ("Speaker: text"). The first speaker is the
     distressed person; everyone else is a responder. Replies with dismissive
     cues ("be patient", "stay positive") can't be the pivot.
  2. Score the person's sentiment on every turn with an open-source model
     (cardiffnlp/twitter-roberta-base-sentiment-latest; score = P(pos) - P(neg)).
  3. For each responder reply, compare the person's lowest sentiment so far
     with their next turn. The first reply that lifts it by MIN_SHIFT or more
     is the pivot; replies before it are kept as the "failed attempts".
  4. Name the technique with a transparent cue lexicon (regex phrases per
     technique), and flag dismissive / toxic-positivity cues in failed replies.

Incremental: each processed file's hash (with PIPELINE_VERSION) is cached in
scripts/.extract_cache.json, so unchanged logs are skipped.

Usage:
    python scripts/extract_empathy.py
    python scripts/extract_empathy.py --force      # re-process everything
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "dataset"
OUT_PATH = ROOT / "public" / "data" / "empathy_db.json"
CACHE_PATH = ROOT / "scripts" / ".extract_cache.json"

PIPELINE_VERSION = "4"  # bump to re-process every file after changing the method
SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MIN_SHIFT = 0.4  # smallest sentiment rise that counts as a de-escalation

# Ordered: on a tie the earlier, more specific technique wins.
TECHNIQUES: dict[str, list[str]] = {
    "Radical Acceptance": [
        r"not going to (argue|defend)", r"won'?t argue", r"both things can be true",
        r"i hear how (angry|upset|hurt)",
    ],
    "Reflective Summarizing": [
        r"let me make sure i'?ve got", r"(is that|did i get that) (right|the full picture)",
        r"full picture", r"so what i'?m hearing", r"if i understand",
    ],
    "Permission to Feel": [
        r"(it'?s|it is) okay (that|to)", r"you don'?t have to", r"whatever you'?re (actually )?feeling",
        r"allowed to (feel|be)", r"right.? reaction",
    ],
    "Naming the Emotion": [
        r"\b(frightening|terrifying|exhausting|overwhelming|scary|painful|infuriating)\b",
        r"you('?re| are) (scared|afraid|angry|furious|upset|hurt|exhausted)",
        r"anger makes sense",
    ],
    "Validation": [
        r"you'?re right", r"makes sense", r"i'?d be (furious|upset|angry|frustrated)",
        r"that'?s (fair|understandable|valid)", r"you deserve", r"anyone would",
        r"(this|that) is (serious|a real loss|real)",
    ],
    "Collaborative Problem-Solving": [
        r"can i (show|ask)", r"(let'?s|we can) (figure|work|look)", r"you tell me",
        r"so we can",
    ],
    "Concrete Action": [
        r"i'?m (holding|reversing|lifting|escalating|booking)", r"in the next \w+ minutes",
        r"i can (verify|lift|fix|book|reverse)", r"right now",
    ],
    "Ownership / Apology": [r"\bi'?m sorry\b", r"\bmy (fault|mistake)\b", r"\bwe got (this|it) wrong\b"],
}

DISMISSIVE = [
    r"be patient", r"stay positive", r"good vibes", r"turn out fine", r"everything happens for a reason",
    r"\bat least\b", r"rules are rules", r"read the (tos|rules|faq)", r"calm down", r"have you (checked|tried)",
]

TURN_RE = re.compile(r"^([A-Za-z][\w .'-]{0,30}?):\s+(.*)$")


def parse_turns(text: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = TURN_RE.match(line)
        if m:
            turns.append((m.group(1).strip(), m.group(2).strip()))
        elif turns:  # continuation of the previous turn
            turns[-1] = (turns[-1][0], turns[-1][1] + " " + line)
    return turns


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", text) if s.strip()]


def match_cues(text: str, patterns: list[str]) -> list[str]:
    low = text.lower()
    return [m.group(0) for p in patterns if (m := re.search(p, low))]


def classify(text: str) -> tuple[str, list[str], dict[str, list[str]]]:
    hits = {t: match_cues(text, ps) for t, ps in TECHNIQUES.items()}
    hits = {t: h for t, h in hits.items() if h}
    if not hits:
        return "Unclassified", [], {}
    ranked = sorted(hits, key=lambda t: (-len(hits[t]), list(TECHNIQUES).index(t)))
    return ranked[0], ranked[1:], hits


def pivot_quote(text: str, cues: list[str]) -> str:
    """The sentences of the reply that carry the technique cues."""
    keep = [s for s in sentences(text) if any(c in s.lower() for c in cues)]
    return " ".join(keep) if keep else " ".join(sentences(text)[:2])


class Sentiment:
    def __init__(self) -> None:
        from transformers import pipeline

        self.pipe = pipeline("text-classification", model=SENTIMENT_MODEL, top_k=None, truncation=True)

    def __call__(self, texts: list[str]) -> list[float]:
        out = []
        for scores in self.pipe(texts):
            p = {s["label"].lower(): s["score"] for s in scores}
            out.append(round(p.get("positive", 0.0) - p.get("negative", 0.0), 2))
        return out


def analyze(name: str, text: str, sentiment: Sentiment) -> list[dict]:
    turns = parse_turns(text)
    if len(turns) < 3:
        return []
    person = turns[0][0]
    person_idx = [i for i, (s, _) in enumerate(turns) if s == person]
    scores = dict(zip(person_idx, sentiment([turns[i][1] for i in person_idx])))

    # For each responder reply: the person's lowest sentiment so far vs. their next turn.
    candidates = []
    for i, (speaker, reply) in enumerate(turns):
        if speaker == person:
            continue
        before = [j for j in person_idx if j < i]
        after = [j for j in person_idx if j > i]
        if not before or not after:
            continue
        b, a = min(scores[j] for j in before), scores[after[0]]
        candidates.append({
            "i": i, "reply": reply, "before": b, "after": a, "shift": round(a - b, 2),
            # Ignore quoted phrases: a reply that criticizes "turn out fine" isn't dismissive.
            "dismissive": match_cues(re.sub(r"[\"“][^\"”]*[\"”]", "", reply), DISMISSIVE),
        })

    # The pivot is the first non-dismissive reply after which the person clearly calms.
    # Dismissive replies are excluded because sentiment models read sarcasm
    # ("Wow. Great. Customer service of the year.") as positive.
    best = next((c for c in candidates if not c["dismissive"] and c["shift"] >= MIN_SHIFT), None)
    if best is None:
        return []

    technique, secondary, hits = classify(best["reply"])
    cues = [c for h in hits.values() for c in h]
    failed = [
        {"reply": c["reply"], "shift": c["shift"], "dismissive_cues": c["dismissive"]}
        for c in candidates
        if c["i"] < best["i"]
    ]
    opening = " ".join(sentences(turns[0][1])[:2])

    why = [f"{person}'s sentiment moved from {best['before']:+.2f} to {best['after']:+.2f} after this reply."]
    if cues:
        why.append("Cue phrases: " + ", ".join(f"“{c}”" for c in cues[:4]) + ".")
    if failed:
        f = failed[0]
        if f["dismissive_cues"]:
            why.append(f"The earlier reply “{f['reply'][:80]}” used a dismissive cue (“{f['dismissive_cues'][0]}”).")
        else:
            why.append(f"The earlier reply “{f['reply'][:80]}” moved it only {f['shift']:+.2f}.")

    return [
        {
            "id": f"{Path(name).stem}-1",
            "trigger_state": opening,
            "de_escalation_pivot": pivot_quote(best["reply"], cues),
            "psychological_technique": technique,
            "explanation": " ".join(why),
            "secondary_techniques": secondary,
            "sentiment_before": best["before"],
            "sentiment_after": best["after"],
            "failed_attempts": failed,
            "source_file": name,
        }
    ]


def file_key(text: str) -> str:
    return hashlib.sha256((PIPELINE_VERSION + "\n" + text).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="re-process unchanged files too")
    args = parser.parse_args()

    files = sorted(DATASET_DIR.glob("*.txt"))
    db = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else []
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

    texts = {p.name: p.read_text(encoding="utf-8") for p in files}
    todo = [n for n, t in texts.items() if args.force or cache.get(n) != file_key(t)]
    db = [e for e in db if e["source_file"] in texts and e["source_file"] not in todo]

    if todo:
        sentiment = Sentiment()
        for name in todo:
            entries = analyze(name, texts[name], sentiment)
            db.extend(entries)
            cache[name] = file_key(texts[name])
            print(f"{name}: {len(entries)} pivot(s)")

    cache = {k: v for k, v in cache.items() if k in texts}
    db.sort(key=lambda e: e["id"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(db, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")
    print(f"{len(db)} entries from {len(files)} files ({len(todo)} processed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
