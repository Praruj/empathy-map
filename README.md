# The Empathy Map

A browsable catalog of **empathy in action**: moments in conversation logs where a
distressed or angry person was calmed down, the exact words that did it, and the
psychological technique behind them (Validation, Reflective Summarizing, Radical
Acceptance, Permission to Feel, …). Each card also notes what failed first, so you can
see the difference between real validation and toxic positivity.

**Live:** https://praruj.github.io/empathy-map/

## How it works

Inspired by Andrej Karpathy's HackerTube approach: the LLM is an **offline data
compiler**, not a live service. Nothing calls a model when you load the page.

```
dataset/*.txt ──► scripts/extract_empathy.py ──► public/data/empathy_db.json ──► Next.js static export ──► GitHub Pages
                  (Claude, structured output)       (committed to the repo)        (output: 'export')
```

1. **Pipeline** — `scripts/extract_empathy.py` sends each conversation log to Claude
   with a JSON schema and gets back the pivot(s): `id`, `trigger_state`,
   `de_escalation_pivot` (verbatim quote), `psychological_technique`, `explanation`.
   File hashes are cached in `scripts/.extract_cache.json`, so only new or edited logs
   cost API calls.
2. **Frontend** — Next.js App Router with `output: 'export'`, Tailwind, client-side
   search over the static JSON.
3. **Engine** — `.github/workflows/deploy.yml` runs the pipeline, commits any new JSON
   back to `main`, builds the export and deploys it to Pages.

## Adding data

Drop `.txt` conversation logs in `dataset/` and push. To enable extraction in CI, add
an `ANTHROPIC_API_KEY` repository secret (Settings → Secrets and variables → Actions).
Without it the pipeline step is a no-op and the site serves the committed JSON.
Run with **Actions → Compile data and deploy to Pages → Run workflow → force** to
re-extract everything.

The six sample logs in `dataset/` are **synthetic**, written for this demo. The seed
`empathy_db.json` was compiled from them by Claude during development; the CI pipeline
produces the same schema.

## Local development

```bash
npm install
npm run dev                                  # http://localhost:3000
pip install -r requirements.txt
ANTHROPIC_API_KEY=... python scripts/extract_empathy.py
```
