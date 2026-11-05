"use client";

import { useEffect, useMemo, useState } from "react";

type Insight = {
  id: string;
  trigger_state: string;
  de_escalation_pivot: string;
  psychological_technique: string;
  explanation: string;
  source_file?: string;
};

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export default function Home() {
  const [data, setData] = useState<Insight[] | null>(null);
  const [error, setError] = useState(false);
  const [query, setQuery] = useState("");
  const [technique, setTechnique] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE_PATH}/data/empathy_db.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const techniques = useMemo(() => {
    const counts = new Map<string, number>();
    for (const d of data ?? [])
      counts.set(d.psychological_technique, (counts.get(d.psychological_technique) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [data]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter(
      (d) =>
        (!technique || d.psychological_technique === technique) &&
        (!q ||
          d.trigger_state.toLowerCase().includes(q) ||
          d.psychological_technique.toLowerCase().includes(q)),
    );
  }, [data, query, technique]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:py-16">
      <header className="mb-10">
        <p className="font-mono text-xs uppercase tracking-widest text-muted">
          De-escalation database
        </p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight sm:text-5xl">
          The Empathy Map
        </h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-muted">
          The exact words that turned an angry or distressed person around, pulled from
          conversation logs by an offline LLM pass and tagged with the technique that made
          them work. Compare them with the failed replies that came first.
        </p>
      </header>

      <div className="sticky top-0 z-10 -mx-4 bg-background/90 px-4 py-3 backdrop-blur">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a situation or technique — e.g. grief, airline, validation"
          aria-label="Search by trigger state or technique"
          className="w-full rounded-xl border border-border bg-card px-4 py-3 text-base outline-none transition focus:border-accent"
        />
        {techniques.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <Chip active={technique === null} onClick={() => setTechnique(null)}>
              All · {data?.length}
            </Chip>
            {techniques.map(([t, n]) => (
              <Chip key={t} active={technique === t} onClick={() => setTechnique(technique === t ? null : t)}>
                {t} · {n}
              </Chip>
            ))}
          </div>
        )}
      </div>

      <section className="mt-6 space-y-5">
        {error && <p className="text-muted">Couldn&apos;t load the catalog.</p>}
        {!data && !error && <p className="text-muted">Loading…</p>}
        {data && filtered.length === 0 && (
          <p className="text-muted">No moments match “{query}”.</p>
        )}
        {filtered.map((d) => (
          <Card key={d.id} insight={d} />
        ))}
      </section>

      <footer className="mt-16 border-t border-border pt-6 text-sm text-muted">
        Static site, no live inference. Data compiled offline with Claude and rebuilt by GitHub
        Actions. Sample conversations are synthetic.
      </footer>
    </main>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3 py-1 text-sm transition ${
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-card text-muted hover:border-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function Card({ insight }: { insight: Insight }) {
  return (
    <article className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="border-l-4 border-accent bg-accent-soft px-5 py-4">
        <p className="font-mono text-[11px] uppercase tracking-widest text-accent">Tension</p>
        <p className="mt-1 leading-relaxed">{insight.trigger_state}</p>
      </div>
      <div className="border-l-4 border-calm bg-calm-soft px-5 py-4">
        <p className="font-mono text-[11px] uppercase tracking-widest text-calm">The pivot</p>
        <blockquote className="mt-1 text-lg leading-relaxed font-medium">
          “{insight.de_escalation_pivot}”
        </blockquote>
      </div>
      <div className="px-5 py-4">
        <span className="inline-block rounded-full bg-foreground px-3 py-1 text-xs font-medium text-background">
          {insight.psychological_technique}
        </span>
        <p className="mt-3 text-sm leading-relaxed text-muted">{insight.explanation}</p>
      </div>
    </article>
  );
}
