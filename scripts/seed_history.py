"""
Initial historical seed.

Downloads all of Sackmann's match history for ATP and WTA from a chosen
start year through to the most recent year, and:
  1. inserts players + tournaments + matches
  2. computes Elo ratings chronologically (with surface tracking)
  3. writes the final rating snapshot to the `ratings` table

Run this once on a fresh database. After that, use update_data.py daily.

Usage:
    DATABASE_URL=postgres://... python -m scripts.seed_history
    DATABASE_URL=postgres://... python -m scripts.seed_history --start 2010 --tour ATP
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

# Make sibling 'api' package importable when running as a script
sys.path.insert(0, ".")

from api._lib.db import connect
from api._lib.elo import PlayerRating, update_after_match, normalize_surface
from api._lib.repo import (
    upsert_players, upsert_tournament, ensure_player_stub,
    insert_match, write_ratings, set_state,
)
from api._lib.sackmann import fetch_csv, players_url, parse_player, stream_matches


DEFAULT_START_YEAR = 2005


def seed_players(conn, tour: str) -> None:
    print(f"[{tour}] downloading player roster…")
    rows = fetch_csv(players_url(tour))
    parsed = [p for p in (parse_player(r, tour) for r in rows) if p is not None]
    n = upsert_players(conn, parsed)
    print(f"[{tour}] upserted {n:,} players")


def seed_matches_and_elo(conn, tour: str, start_year: int, end_year: int) -> int:
    """
    Stream matches in chronological order and build Elo state in memory.
    Inserts each match with pre-match Elo snapshot.
    Returns total matches processed.
    """
    print(f"[{tour}] streaming matches {start_year}–{end_year}…")
    ratings: dict[int, PlayerRating] = {}
    last_seen: dict[int, date] = {}

    def get_or_create(pid: int) -> PlayerRating:
        r = ratings.get(pid)
        if r is None:
            r = PlayerRating(player_id=pid)
            ratings[pid] = r
        return r

    total = 0
    t0 = time.time()
    years = range(start_year, end_year + 1)

    # Sort each year's matches by match_num within the tournament so the order is stable.
    # Sackmann's CSVs are already roughly chronological (by tourney_date then match_num).
    for m in stream_matches(tour, iter(years)):
        # Make sure player FK rows exist (some matches reference players not in
        # the players.csv yet, especially recent qualifiers).
        ensure_player_stub(conn, m.winner_id, tour)
        ensure_player_stub(conn, m.loser_id, tour)

        upsert_tournament(conn, m)

        winner = get_or_create(m.winner_id)
        loser = get_or_create(m.loser_id)
        surface = normalize_surface(m.surface)

        # Take pre-match snapshot
        pre_w = winner.overall
        pre_l = loser.overall
        pre_w_s = winner.surface_rating(surface)
        pre_l_s = loser.surface_rating(surface)

        insert_match(conn, m, pre=(pre_w, pre_l, pre_w_s, pre_l_s))

        # Update ratings
        update_after_match(winner, loser, surface)
        last_seen[m.winner_id] = m.match_date
        last_seen[m.loser_id] = m.match_date

        total += 1
        if total % 5000 == 0:
            elapsed = time.time() - t0
            print(f"  …{total:,} matches processed ({total/elapsed:.0f}/s)")
            conn.commit()  # flush periodically so memory stays bounded server-side

    print(f"[{tour}] writing {len(ratings):,} player ratings…")
    write_ratings(conn, ratings, last_seen)

    print(f"[{tour}] done — {total:,} matches in {time.time() - t0:.1f}s")
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=DEFAULT_START_YEAR)
    ap.add_argument("--end", type=int, default=date.today().year)
    ap.add_argument("--tour", choices=["ATP", "WTA", "BOTH"], default="BOTH")
    args = ap.parse_args()

    tours = ["ATP", "WTA"] if args.tour == "BOTH" else [args.tour]

    with connect() as conn:
        for tour in tours:
            seed_players(conn, tour)
            seed_matches_and_elo(conn, tour, args.start, args.end)
            set_state(conn, f"seed_completed_{tour}", date.today().isoformat())

    print("✅ seed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
