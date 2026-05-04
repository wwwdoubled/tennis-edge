"""
Initial historical seed (OPTIMIZED).

Strategy:
  1. Download & parse all CSVs into memory first (the slow part is the
     network, not the parsing).
  2. Bulk-insert all tournaments in a single multi-row INSERT.
  3. Bulk-insert all player stubs in a single multi-row INSERT.
  4. Walk matches in chronological order, computing Elo state in memory,
     and flushing inserts to the DB in batches of BATCH_SIZE.
  5. Bulk-insert final ratings.

This collapses ~1M individual roundtrips down to a few hundred — the seed
runs in ~3–8 minutes instead of hours.

Usage:
    DATABASE_URL=postgres://... python -m scripts.seed_history
    DATABASE_URL=postgres://... python -m scripts.seed_history --start 2015 --tour ATP
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
    upsert_players, set_state,
    bulk_upsert_tournaments, bulk_insert_player_stubs,
    bulk_insert_matches, bulk_write_ratings,
)
from api._lib.sackmann import (
    fetch_csv, players_url, parse_player, matches_url, parse_match,
)


DEFAULT_START_YEAR = 2005
BATCH_SIZE = 1000  # matches per roundtrip


def seed_players(conn, tour: str) -> None:
    print(f"[{tour}] downloading player roster…")
    rows = fetch_csv(players_url(tour))
    parsed = [p for p in (parse_player(r, tour) for r in rows) if p is not None]
    n = upsert_players(conn, parsed)
    conn.commit()
    print(f"[{tour}] upserted {n:,} players")


def download_all_matches(tour: str, start_year: int, end_year: int) -> list:
    print(f"[{tour}] downloading {start_year}–{end_year} match CSVs…")
    all_matches = []
    for year in range(start_year, end_year + 1):
        url = matches_url(tour, year)
        try:
            t0 = time.time()
            rows = fetch_csv(url)
            parsed = [m for m in (parse_match(r, tour) for r in rows) if m is not None]
            all_matches.extend(parsed)
            print(f"  {year}: {len(parsed):>5,} matches  ({time.time() - t0:4.1f}s)")
        except Exception as e:
            print(f"  ⚠ {year}: {e}")
    return all_matches


def seed_matches_and_elo(conn, tour: str, start_year: int, end_year: int) -> int:
    matches = download_all_matches(tour, start_year, end_year)

    if not matches:
        print(f"[{tour}] no matches found")
        return 0

    # Sort chronologically. Sackmann's match_num goes high → low within a
    # tournament (final has lowest, qualifying has highest). We want earlier
    # rounds first, so sort by date asc, then match_num desc.
    matches.sort(key=lambda m: (m.match_date, m.tournament_id, -(m.match_num or 0)))
    print(f"[{tour}] {len(matches):,} matches parsed and sorted")

    # ---- Step 1: bulk insert tournaments (deduped) -----------------------
    seen_tournaments = {}
    for m in matches:
        seen_tournaments[m.tournament_id] = m
    print(f"[{tour}] bulk-upserting {len(seen_tournaments):,} tournaments…")
    t0 = time.time()
    bulk_upsert_tournaments(conn, list(seen_tournaments.values()))
    conn.commit()
    print(f"  done in {time.time() - t0:.1f}s")

    # ---- Step 2: bulk insert player stubs (deduped) ----------------------
    player_ids: set[int] = set()
    for m in matches:
        player_ids.add(m.winner_id)
        player_ids.add(m.loser_id)
    print(f"[{tour}] bulk-upserting {len(player_ids):,} player stubs…")
    t0 = time.time()
    bulk_insert_player_stubs(conn, player_ids, tour)
    conn.commit()
    print(f"  done in {time.time() - t0:.1f}s")

    # ---- Step 3: walk matches, compute Elo, insert in batches ------------
    ratings: dict[int, PlayerRating] = {}
    last_seen: dict[int, date] = {}
    batch: list = []
    total = 0
    t0 = time.time()

    print(f"[{tour}] processing matches in batches of {BATCH_SIZE}…")
    for m in matches:
        winner = ratings.get(m.winner_id) or PlayerRating(player_id=m.winner_id)
        loser = ratings.get(m.loser_id) or PlayerRating(player_id=m.loser_id)
        ratings[m.winner_id] = winner
        ratings[m.loser_id] = loser

        surface = normalize_surface(m.surface)

        pre_w = winner.overall
        pre_l = loser.overall
        pre_w_s = winner.surface_rating(surface)
        pre_l_s = loser.surface_rating(surface)

        batch.append((m, (pre_w, pre_l, pre_w_s, pre_l_s)))

        update_after_match(winner, loser, surface)
        last_seen[m.winner_id] = m.match_date
        last_seen[m.loser_id] = m.match_date

        if len(batch) >= BATCH_SIZE:
            bulk_insert_matches(conn, batch)
            total += len(batch)
            elapsed = time.time() - t0
            rate = total / elapsed if elapsed else 0
            eta = (len(matches) - total) / rate if rate else 0
            print(f"  {total:>6,} / {len(matches):,}  ({rate:.0f}/s, ETA {eta:.0f}s)")
            batch = []
            conn.commit()

    if batch:
        bulk_insert_matches(conn, batch)
        total += len(batch)
        conn.commit()

    print(f"[{tour}] inserted {total:,} matches in {time.time() - t0:.1f}s")

    # ---- Step 4: bulk write ratings --------------------------------------
    print(f"[{tour}] writing {len(ratings):,} player ratings…")
    t0 = time.time()
    bulk_write_ratings(conn, ratings, last_seen)
    conn.commit()
    print(f"  done in {time.time() - t0:.1f}s")

    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=DEFAULT_START_YEAR)
    ap.add_argument("--end", type=int, default=date.today().year)
    ap.add_argument("--tour", choices=["ATP", "WTA", "BOTH"], default="BOTH")
    args = ap.parse_args()

    tours = ["ATP", "WTA"] if args.tour == "BOTH" else [args.tour]

    overall_t0 = time.time()
    with connect() as conn:
        for tour in tours:
            seed_players(conn, tour)
            seed_matches_and_elo(conn, tour, args.start, args.end)
            set_state(conn, f"seed_completed_{tour}", date.today().isoformat())

    print(f"✅ seed complete in {time.time() - overall_t0:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
