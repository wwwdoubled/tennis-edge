"""
Data source: Jeff Sackmann's tennis_atp / tennis_wta repositories on GitHub.
Public domain. Updated regularly. The de facto standard for tennis match history.

  https://github.com/JeffSackmann/tennis_atp
  https://github.com/JeffSackmann/tennis_wta

We pull CSVs directly from the raw GitHub URLs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator
import csv
import io
import urllib.request

ATP_BASE = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
WTA_BASE = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master"


def players_url(tour: str) -> str:
    base = ATP_BASE if tour == "ATP" else WTA_BASE
    return f"{base}/{tour.lower()}_players.csv"


def matches_url(tour: str, year: int) -> str:
    base = ATP_BASE if tour == "ATP" else WTA_BASE
    return f"{base}/{tour.lower()}_matches_{year}.csv"


def fetch_csv(url: str) -> list[dict]:
    """Download a CSV and return list of row dicts."""
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_int(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _parse_date(v: str | None) -> date | None:
    if not v:
        return None
    v = v.strip()
    # Sackmann uses YYYYMMDD
    if len(v) == 8 and v.isdigit():
        try:
            return datetime.strptime(v, "%Y%m%d").date()
        except ValueError:
            return None
    # Fallback: ISO date
    try:
        return datetime.fromisoformat(v).date()
    except ValueError:
        return None


@dataclass
class PlayerRow:
    player_id: int
    name: str
    country: str | None
    hand: str | None
    height: int | None
    birth_date: date | None
    tour: str


def parse_player(row: dict, tour: str) -> PlayerRow | None:
    pid = _parse_int(row.get("player_id"))
    if pid is None:
        return None
    first = (row.get("name_first") or "").strip()
    last = (row.get("name_last") or "").strip()
    name = f"{first} {last}".strip() or f"Player#{pid}"
    return PlayerRow(
        player_id=pid,
        name=name,
        country=(row.get("ioc") or None),
        hand=(row.get("hand") or None),
        height=_parse_int(row.get("height")),
        birth_date=_parse_date(row.get("dob")),
        tour=tour,
    )


@dataclass
class MatchRow:
    tournament_id: str
    tourney_name: str
    surface: str
    draw_size: int | None
    level: str | None
    start_date: date | None
    match_num: int | None
    match_date: date
    round: str | None
    best_of: int | None
    winner_id: int
    loser_id: int
    score: str | None
    minutes: int | None
    # serve stats
    w_ace: int | None;  w_df: int | None;  w_svpt: int | None
    w_1st_in: int | None;  w_1st_won: int | None;  w_2nd_won: int | None
    w_sv_gms: int | None;  w_bp_saved: int | None;  w_bp_faced: int | None
    l_ace: int | None;  l_df: int | None;  l_svpt: int | None
    l_1st_in: int | None;  l_1st_won: int | None;  l_2nd_won: int | None
    l_sv_gms: int | None;  l_bp_saved: int | None;  l_bp_faced: int | None
    tour: str


def parse_match(row: dict, tour: str) -> MatchRow | None:
    winner_id = _parse_int(row.get("winner_id"))
    loser_id = _parse_int(row.get("loser_id"))
    if winner_id is None or loser_id is None:
        return None

    tourney_id = (row.get("tourney_id") or "").strip()
    if not tourney_id:
        return None

    tourney_date = _parse_date(row.get("tourney_date"))
    # Use tourney_date as the match_date — Sackmann doesn't have per-match date
    # for historical data. Match number gives ordering within the tournament.
    if tourney_date is None:
        return None

    return MatchRow(
        tournament_id=tourney_id,
        tourney_name=(row.get("tourney_name") or "").strip(),
        surface=(row.get("surface") or "Hard").strip() or "Hard",
        draw_size=_parse_int(row.get("draw_size")),
        level=(row.get("tourney_level") or None),
        start_date=tourney_date,
        match_num=_parse_int(row.get("match_num")),
        match_date=tourney_date,
        round=(row.get("round") or None),
        best_of=_parse_int(row.get("best_of")),
        winner_id=winner_id,
        loser_id=loser_id,
        score=(row.get("score") or None),
        minutes=_parse_int(row.get("minutes")),
        w_ace=_parse_int(row.get("w_ace")),     w_df=_parse_int(row.get("w_df")),
        w_svpt=_parse_int(row.get("w_svpt")),    w_1st_in=_parse_int(row.get("w_1stIn")),
        w_1st_won=_parse_int(row.get("w_1stWon")), w_2nd_won=_parse_int(row.get("w_2ndWon")),
        w_sv_gms=_parse_int(row.get("w_SvGms")),
        w_bp_saved=_parse_int(row.get("w_bpSaved")), w_bp_faced=_parse_int(row.get("w_bpFaced")),
        l_ace=_parse_int(row.get("l_ace")),     l_df=_parse_int(row.get("l_df")),
        l_svpt=_parse_int(row.get("l_svpt")),    l_1st_in=_parse_int(row.get("l_1stIn")),
        l_1st_won=_parse_int(row.get("l_1stWon")), l_2nd_won=_parse_int(row.get("l_2ndWon")),
        l_sv_gms=_parse_int(row.get("l_SvGms")),
        l_bp_saved=_parse_int(row.get("l_bpSaved")), l_bp_faced=_parse_int(row.get("l_bpFaced")),
        tour=tour,
    )


def stream_matches(tour: str, years: Iterator[int]) -> Iterator[MatchRow]:
    """Yield parsed MatchRow objects for the given years and tour."""
    for year in years:
        url = matches_url(tour, year)
        try:
            rows = fetch_csv(url)
        except Exception as e:
            print(f"  ⚠ skipping {tour} {year}: {e}")
            continue
        for raw in rows:
            m = parse_match(raw, tour)
            if m is not None:
                yield m
