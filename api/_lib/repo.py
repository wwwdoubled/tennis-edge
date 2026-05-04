"""
Idempotent upserts: players, tournaments, matches, ratings.

These are the write-side helpers used by both the seed-history script
(initial bulk load) and the daily incremental update job.
"""

from __future__ import annotations

from typing import Iterable

import psycopg

from .elo import PlayerRating, SURFACES, normalize_surface
from .sackmann import MatchRow, PlayerRow


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

def upsert_players(conn: psycopg.Connection, players: Iterable[PlayerRow]) -> int:
    sql = """
        INSERT INTO players (player_id, name, country, hand, height, birth_date, tour)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (player_id) DO UPDATE SET
            name = EXCLUDED.name,
            country = EXCLUDED.country,
            hand = EXCLUDED.hand,
            height = EXCLUDED.height,
            birth_date = EXCLUDED.birth_date,
            tour = EXCLUDED.tour,
            updated_at = NOW();
    """
    rows = [
        (p.player_id, p.name, p.country, p.hand, p.height, p.birth_date, p.tour)
        for p in players
    ]
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------

def upsert_tournament(conn: psycopg.Connection, m: MatchRow) -> None:
    sql = """
        INSERT INTO tournaments (tournament_id, name, surface, draw_size, level, start_date, tour)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tournament_id) DO UPDATE SET
            name = EXCLUDED.name,
            surface = EXCLUDED.surface,
            draw_size = EXCLUDED.draw_size,
            level = EXCLUDED.level,
            start_date = EXCLUDED.start_date,
            tour = EXCLUDED.tour;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            m.tournament_id, m.tourney_name, normalize_surface(m.surface),
            m.draw_size, m.level, m.start_date, m.tour
        ))


# ---------------------------------------------------------------------------
# Ensure player rows exist (matches reference players that might be new)
# ---------------------------------------------------------------------------

def ensure_player_stub(conn: psycopg.Connection, player_id: int, tour: str) -> None:
    """Insert a placeholder row if a player_id isn't yet in the players table."""
    sql = """
        INSERT INTO players (player_id, name, tour)
        VALUES (%s, %s, %s)
        ON CONFLICT (player_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (player_id, f"Player#{player_id}", tour))


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------

def insert_match(
    conn: psycopg.Connection,
    m: MatchRow,
    pre: tuple[float, float, float, float] | None = None,
) -> int | None:
    """
    Insert a match row. Returns the new match_id or None if conflict.
    `pre` is (winner_overall, loser_overall, winner_surface, loser_surface)
    pre-match Elo snapshots, optional.
    """
    we, le, wse, lse = pre if pre is not None else (None, None, None, None)
    sql = """
        INSERT INTO matches (
            tournament_id, match_num, match_date, round, surface, best_of,
            winner_id, loser_id, score, minutes,
            w_ace, w_df, w_svpt, w_1st_in, w_1st_won, w_2nd_won, w_sv_gms, w_bp_saved, w_bp_faced,
            l_ace, l_df, l_svpt, l_1st_in, l_1st_won, l_2nd_won, l_sv_gms, l_bp_saved, l_bp_faced,
            winner_elo_pre, loser_elo_pre, winner_surface_elo_pre, loser_surface_elo_pre
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (tournament_id, match_num) DO NOTHING
        RETURNING match_id;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            m.tournament_id, m.match_num, m.match_date, m.round,
            normalize_surface(m.surface), m.best_of,
            m.winner_id, m.loser_id, m.score, m.minutes,
            m.w_ace, m.w_df, m.w_svpt, m.w_1st_in, m.w_1st_won, m.w_2nd_won,
            m.w_sv_gms, m.w_bp_saved, m.w_bp_faced,
            m.l_ace, m.l_df, m.l_svpt, m.l_1st_in, m.l_1st_won, m.l_2nd_won,
            m.l_sv_gms, m.l_bp_saved, m.l_bp_faced,
            we, le, wse, lse,
        ))
        row = cur.fetchone()
        return row["match_id"] if row else None


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------

def write_ratings(conn: psycopg.Connection, ratings: dict[int, PlayerRating], last_dates: dict[int, "date | None"]) -> int:
    sql = """
        INSERT INTO ratings (
            player_id, overall, hard, clay, grass, carpet,
            matches_played, matches_hard, matches_clay, matches_grass, matches_carpet,
            last_match_date, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (player_id) DO UPDATE SET
            overall = EXCLUDED.overall,
            hard = EXCLUDED.hard,
            clay = EXCLUDED.clay,
            grass = EXCLUDED.grass,
            carpet = EXCLUDED.carpet,
            matches_played = EXCLUDED.matches_played,
            matches_hard = EXCLUDED.matches_hard,
            matches_clay = EXCLUDED.matches_clay,
            matches_grass = EXCLUDED.matches_grass,
            matches_carpet = EXCLUDED.matches_carpet,
            last_match_date = EXCLUDED.last_match_date,
            updated_at = NOW();
    """
    rows = []
    for pid, r in ratings.items():
        rows.append((
            pid, r.overall, r.hard, r.clay, r.grass, r.carpet,
            r.matches_played,
            r.matches_by_surface.get("Hard", 0),
            r.matches_by_surface.get("Clay", 0),
            r.matches_by_surface.get("Grass", 0),
            r.matches_by_surface.get("Carpet", 0),
            last_dates.get(pid),
        ))
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def load_ratings(conn: psycopg.Connection) -> dict[int, PlayerRating]:
    """Load all current ratings into memory as a dict keyed by player_id."""
    sql = """
        SELECT player_id, overall, hard, clay, grass, carpet,
               matches_played, matches_hard, matches_clay, matches_grass, matches_carpet
        FROM ratings;
    """
    out: dict[int, PlayerRating] = {}
    with conn.cursor() as cur:
        cur.execute(sql)
        for row in cur.fetchall():
            r = PlayerRating(player_id=row["player_id"])
            r.overall = float(row["overall"])
            r.hard = float(row["hard"])
            r.clay = float(row["clay"])
            r.grass = float(row["grass"])
            r.carpet = float(row["carpet"])
            r.matches_played = row["matches_played"]
            r.matches_by_surface = {
                "Hard":  row["matches_hard"],
                "Clay":  row["matches_clay"],
                "Grass": row["matches_grass"],
                "Carpet": row["matches_carpet"],
            }
            out[row["player_id"]] = r
    return out


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

def get_state(conn: psycopg.Connection, key: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT value FROM pipeline_state WHERE key = %s", (key,))
        row = cur.fetchone()
        return row["value"] if row else None


def set_state(conn: psycopg.Connection, key: str, value: str) -> None:
    sql = """
        INSERT INTO pipeline_state (key, value, updated_at) VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
    """
    with conn.cursor() as cur:
        cur.execute(sql, (key, value))
