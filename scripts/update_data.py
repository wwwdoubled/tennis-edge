"""
Daily incremental update.

Pulls the current year's matches from Sackmann and processes any matches
not yet in the database (matched on tournament_id + match_num).

Designed to be idempotent — running it multiple times a day is safe.

Run via GitHub Actions cron:
    DATABASE_URL=postgres://... python -m scripts.update_data
"""

from __future__ import annotations

import sys
import time
from datetime import date

sys.path.insert(0, ".")

from api._lib.db import connect
from api._lib.elo import PlayerRating, update_after_match, normalize_surface
from api._lib.repo import (
    upsert_tournament, ensure_player_stub, insert_match,
    write_ratings, load_ratings, set_state,
)
from api._lib.sackmann import stream_matches


def process_recent(conn, tour: str, year: int) -> int:
    print(f"[{tour}] checking {year} for new matches…")

    # Load current rating state — ratings stored in DB reflect ALL matches
    # already processed.
    ratings: dict[int, PlayerRating] = load_ratings(conn)
    last_seen: dict[int, date] = {}

    new_matches = 0
    t0 = time.time()

    for m in stream_matches(tour, iter([year])):
        ensure_player_stub(conn, m.winner_id, tour)
        ensure_player_stub(conn, m.loser_id, tour)
        upsert_tournament(conn, m)

        winner = ratings.get(m.winner_id) or PlayerRating(player_id=m.winner_id)
        loser = ratings.get(m.loser_id) or PlayerRating(player_id=m.loser_id)
        ratings[m.winner_id] = winner
        ratings[m.loser_id] = loser

        surface = normalize_surface(m.surface)
        pre = (winner.overall, loser.overall,
               winner.surface_rating(surface), loser.surface_rating(surface))

        # insert_match returns None on conflict (already exists) — in that case
        # we do NOT update ratings, otherwise we'd double-count.
        match_id = insert_match(conn, m, pre=pre)
        if match_id is None:
            continue

        update_after_match(winner, loser, surface)
        last_seen[m.winner_id] = m.match_date
        last_seen[m.loser_id] = m.match_date
        new_matches += 1

    if new_matches:
        # Only rewrite ratings for players who actually played
        affected = {pid: ratings[pid] for pid in last_seen}
        write_ratings(conn, affected, last_seen)

    print(f"[{tour}] {new_matches} new matches in {time.time() - t0:.1f}s")
    return new_matches


def main() -> int:
    year = date.today().year
    with connect() as conn:
        for tour in ("ATP", "WTA"):
            process_recent(conn, tour, year)
        set_state(conn, "last_update", date.today().isoformat())
    print("✅ update complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
