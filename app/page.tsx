import { RankingsTable } from "@/components/RankingsTable";
import { HealthBadge } from "@/components/HealthBadge";

export const dynamic = "force-dynamic"; // always fetch fresh

export default function Home() {
  return (
    <main className="relative z-10 max-w-[1240px] mx-auto px-6 md:px-10 pb-24">
      {/* ─── masthead ──────────────────────────────────────────────────── */}
      <header className="rule-b py-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="label">Tennis</span>
          <span className="display text-2xl">·</span>
          <span className="display display-italic text-2xl">Edge</span>
        </div>
        <div className="flex items-center gap-6">
          <span className="label label--muted hidden md:inline">
            Vol. 1 · Issue 01
          </span>
          <HealthBadge />
        </div>
      </header>

      {/* ─── hero ──────────────────────────────────────────────────────── */}
      <section className="pt-16 md:pt-24 pb-16 md:pb-20 grid md:grid-cols-12 gap-8">
        <div className="md:col-span-8 rise rise-1">
          <p className="label label--muted mb-6">
            01 — Foundation · sELO ratings & match predictions
          </p>
          <h1 className="display text-[clamp(3rem,8vw,7.5rem)]">
            Numbers that{" "}
            <span className="display-italic">disagree</span>
            <br />
            with the market.
          </h1>
        </div>
        <div className="md:col-span-4 md:pt-6 rise rise-2">
          <p className="text-[15px] leading-relaxed max-w-[36ch]">
            A surface-aware Elo system tracking every ATP and WTA match since
            2005. Predictions are blended <span className="num">70/30</span>{" "}
            between surface and overall rating, with dynamic K-factors so new
            players move fast and veterans stay stable.
          </p>
          <div className="mt-6 flex gap-3">
            <span className="chip" data-active="true">Hard</span>
            <span className="chip">Clay</span>
            <span className="chip">Grass</span>
          </div>
        </div>
      </section>

      {/* ─── rankings ──────────────────────────────────────────────────── */}
      <section className="rule-t pt-10 rise rise-3">
        <div className="flex items-baseline justify-between mb-8">
          <h2 className="display text-4xl md:text-5xl">
            The <span className="display-italic">leaderboard</span>
          </h2>
          <span className="label label--muted hidden md:inline">
            min. 20 matches · live from the database
          </span>
        </div>
        <RankingsTable />
      </section>

      {/* ─── footer ────────────────────────────────────────────────────── */}
      <footer className="rule-t mt-24 pt-6 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <p className="label label--muted">
          Data: Jeff Sackmann (ATP/WTA, public domain) · No bets are advice.
        </p>
        <p className="label label--muted">
          Built with Next.js · FastAPI · Postgres · Vercel
        </p>
      </footer>
    </main>
  );
}
