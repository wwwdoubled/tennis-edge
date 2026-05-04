"use client";

import { useEffect, useState } from "react";

type Row = {
  player_id: number;
  name: string;
  country: string | null;
  tour: string;
  rating: number;
  overall: number;
  matches_played: number;
  last_match_date: string | null;
};

const SURFACES = ["overall", "hard", "clay", "grass"] as const;
type Surface = (typeof SURFACES)[number];

export function RankingsTable() {
  const [tour, setTour] = useState<"ATP" | "WTA">("ATP");
  const [surface, setSurface] = useState<Surface>("overall");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    setError(null);
    fetch(`/api/rankings?tour=${tour}&surface=${surface}&limit=25`)
      .then((r) => r.json())
      .then((j) => {
        if (j.results) setRows(j.results);
        else setError(j.detail || "no data");
      })
      .catch((e) => setError(String(e)));
  }, [tour, surface]);

  // For the "edge bar" we normalize ratings against the top of the visible list.
  const max = rows && rows.length ? Number(rows[0].rating) : 2200;
  const min = rows && rows.length ? Math.min(...rows.map((r) => Number(r.rating))) : 1500;
  const span = Math.max(max - min, 1);

  return (
    <div>
      {/* control row */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex items-center gap-2">
          <span className="label label--muted mr-2">Tour</span>
          {(["ATP", "WTA"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTour(t)}
              data-active={tour === t}
              className="chip"
            >
              {t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="label label--muted mr-2">Surface</span>
          {SURFACES.map((s) => (
            <button
              key={s}
              onClick={() => setSurface(s)}
              data-active={surface === s}
              className="chip"
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* table */}
      <div className="rule-t rule-b">
        <div className="grid grid-cols-[40px_1fr_56px_120px_100px_70px] py-3 label label--muted">
          <div>#</div>
          <div>Player</div>
          <div>IOC</div>
          <div>Rating · {surface}</div>
          <div className="hidden md:block">Overall</div>
          <div className="text-right">Mat.</div>
        </div>

        {error && (
          <div className="py-12 text-center label label--muted">
            could not load rankings — {error}
          </div>
        )}

        {!rows && !error && (
          <div className="py-12 text-center label label--muted">loading…</div>
        )}

        {rows &&
          rows.map((r, i) => {
            const v = Number(r.rating);
            const pct = ((v - min) / span) * 100;
            return (
              <div
                key={r.player_id}
                className="grid grid-cols-[40px_1fr_56px_120px_100px_70px] items-center py-3 border-t border-ink/10 hover:bg-ink/[0.03]"
              >
                <div className="num text-sm text-ash">{String(i + 1).padStart(2, "0")}</div>
                <div className="font-medium">
                  {r.name}
                </div>
                <div className="num text-sm text-ash">{r.country ?? "—"}</div>
                <div>
                  <div className="num text-sm">{v.toFixed(0)}</div>
                  <div className="edge-bar mt-1.5 max-w-[100px]">
                    <span style={{ width: `${Math.max(pct, 4)}%` }} />
                  </div>
                </div>
                <div className="num text-sm text-ash hidden md:block">
                  {Number(r.overall).toFixed(0)}
                </div>
                <div className="num text-sm text-ash text-right">
                  {r.matches_played}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
