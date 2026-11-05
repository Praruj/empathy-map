# The Empathy Map

A browsable catalog of **empathy in action**: moments in conversation logs where a
distressed or angry person was calmed down, the exact words that did it, and the
psychological technique behind them (Validation, Reflective Summarizing, Radical
Acceptance, Permission to Feel, …). Each card also shows the reply that didn't help
first, so you can see the difference between real validation and toxic positivity.

**Live:** https://praruj.github.io/empathy-map/

**Free and independent:** no paid APIs, no API keys, no server. Everything runs on a
laptop CPU or a free GitHub Actions runner.

## How it works

Inspired by Andrej Karpathy's HackerTube approach: the model is an **offline data
compiler**, not a live service. Nothing runs a model when you load the page.

```
dataset/*.txt ──► scripts/extract_empathy.py ──► public/data/empathy_db.json ──► Next.js static export ──► GitHub Pages
                  (open-source model, CPU)          (committed to the repo)        (output: 'export')
```

1. **Pipeline** (`scripts/extract_empathy.py`)
   - Splits each log into turns. The first speaker is the distressed person.
   - Scores that person's sentiment on every turn with the open-source
     [`cardiffnlp/twitter-roberta-base-sentiment-latest`](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
     model (score = P(positive) − P(negative), from −1 to +1).
   - For each responder reply, measures the change in the person's sentiment from
     just before to just after it. The reply with the largest rise (at least +0.4) is
     the **pivot**; earlier replies that didn't help are kept as **failed attempts**.
   - Names the technique with a transparent cue lexicon (regex phrases per technique),
     and flags dismissive / toxic-positivity cues ("stay positive", "rules are rules") in
     failed replies.
   - Output per entry: `id`, `trigger_state`, `de_escalation_pivot`,
     `psychological_technique`, `explanation`, plus `sentiment_before/after`,
     `secondary_techniques`, `failed_attempts`.
   - Incremental: file hashes are cached in `scripts/.extract_cache.json`, so only new
     or edited logs are processed.
2. **Frontend:** Next.js App Router with `output: 'export'`, Tailwind, client-side
   search over the static JSON.
3. **Engine:** `.github/workflows/deploy.yml` runs the pipeline, commits any new JSON
   back to `main`, builds the export and deploys it to Pages.

## Limits

- The six sample logs in `dataset/` are **synthetic**, written for this demo. Results
  on them show the pipeline works; they are not research findings.
- The technique label comes from phrase matching, so it is explainable but shallow: it
  can miss a technique phrased in unusual words.
- The sentiment model was trained on tweets; short chat turns like "...okay." are noisy.

## Adding data

Drop `.txt` logs in `dataset/` (one `Speaker: text` turn per line) and push. To
re-process everything: **Actions → Compile data and deploy to Pages → Run workflow →
force**.

## Local development

```bash
npm install
npm run dev                                  # http://localhost:3000
pip install -r requirements.txt              # CPU-only PyTorch + transformers
python scripts/extract_empathy.py
```
