"use client";

import { useEffect, useState } from "react";

export function HealthBadge() {
  const [status, setStatus] = useState<"loading" | "ok" | "down">("loading");
  const [matches, setMatches] = useState<number | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((j) => {
        if (j.status === "ok") {
          setStatus("ok");
          setMatches(j.matches_in_db ?? 0);
        } else {
          setStatus("down");
        }
      })
      .catch(() => setStatus("down"));
  }, []);

  const dot =
    status === "ok"
      ? "bg-edge"
      : status === "down"
      ? "bg-ink"
      : "bg-ash animate-pulse";

  return (
    <div className="flex items-center gap-2">
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} aria-hidden />
      <span className="label label--muted">
        {status === "ok" && matches != null
          ? `${matches.toLocaleString()} matches`
          : status === "down"
          ? "db offline"
          : "checking…"}
      </span>
    </div>
  );
}
