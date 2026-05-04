"""
FastAPI app served as Vercel serverless functions.

Routes:
    GET /api/health
    GET /api/players?q=djokovic&tour=ATP&limit=20
    GET /api/rankings?tour=ATP&surface=overall&limit=50
    GET /api/predict?p1=104925&p2=206173&surface=Clay
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from _lib.db import fetch_all, fetch_one
from _lib.elo import PlayerRating, predict, blended_rating, prob_to_fair_odds


app = FastAPI(title="Tennis Edge API", version="0.1.0")

# CORS — Next.js on Vercel calls these via /api/* same-origin in production,
# but we allow localhost for development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this once you have a real prod domain
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    try:
        row = fetch_one("SELECT NOW() AS now, COUNT(*) AS n FROM matches")
        return {
            "status": "ok",
            "db_time": row["now"].isoformat() if row else None,
            "matches_in_db": row["n"] if row else 0,
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


# ---------------------------------------------------------------------------
# Players: search by name
# ---------------------------------------------------------------------------

@app.get("/api/players")
def players(
    q: str = Query("", description="search query (name)"),
    tour: str = Query("ATP", regex="^(ATP|WTA)$"),
    limit: int = Query(20, ge=1, le=100),
):
    if q:
        rows = fetch_all(
            """
            SELECT p.player_id, p.name, p.country, p.hand, p.tour,
                   r.overall, r.matches_played
            FROM players p
            LEFT JOIN ratings r ON r.player_id = p.player_id
            WHERE p.tour = %s AND LOWER(p.name) LIKE %s
            ORDER BY r.overall DESC NULLS LAST
            LIMIT %s
            """,
            (tour, f"%{q.lower()}%", limit),
        )
    else:
        rows = fetch_all(
            """
            SELECT p.player_id, p.name, p.country, p.hand, p.tour,
                   r.overall, r.matches_played
            FROM players p
            JOIN ratings r ON r.player_id = p.player_id
            WHERE p.tour = %s AND r.matches_played >= 20
            ORDER BY r.overall DESC
            LIMIT %s
            """,
            (tour, limit),
        )
    return {"results": rows}


# ---------------------------------------------------------------------------
# Rankings: top N on a surface (or overall)
# ---------------------------------------------------------------------------

VALID_SURFACES = {"overall", "hard", "clay", "grass", "carpet"}


@app.get("/api/rankings")
def rankings(
    tour: str = Query("ATP", regex="^(ATP|WTA)$"),
    surface: str = Query("overall"),
    limit: int = Query(50, ge=1, le=200),
):
    surface = surface.lower()
    if surface not in VALID_SURFACES:
        raise HTTPException(400, f"surface must be one of {sorted(VALID_SURFACES)}")

    rating_col = surface  # safe — already validated against allow-list
    rows = fetch_all(
        f"""
        SELECT p.player_id, p.name, p.country, p.tour,
               r.{rating_col} AS rating,
               r.overall, r.matches_played, r.last_match_date
        FROM ratings r
        JOIN players p ON p.player_id = r.player_id
        WHERE p.tour = %s AND r.matches_played >= 20
        ORDER BY r.{rating_col} DESC
        LIMIT %s
        """,
        (tour, limit),
    )
    return {"surface": surface, "tour": tour, "results": rows}


# ---------------------------------------------------------------------------
# Predict: head-to-head probability for two player IDs
# ---------------------------------------------------------------------------

@app.get("/api/predict")
def predict_match(
    p1: int = Query(..., description="player 1 id"),
    p2: int = Query(..., description="player 2 id"),
    surface: str = Query("Hard", regex="^(Hard|Clay|Grass|Carpet)$"),
):
    rows = fetch_all(
        """
        SELECT r.player_id, p.name, p.country, p.tour,
               r.overall, r.hard, r.clay, r.grass, r.carpet, r.matches_played
        FROM ratings r
        JOIN players p ON p.player_id = r.player_id
        WHERE r.player_id IN (%s, %s)
        """,
        (p1, p2),
    )
    by_id = {r["player_id"]: r for r in rows}
    if p1 not in by_id or p2 not in by_id:
        raise HTTPException(404, "one or both players not found")

    def to_rating(r) -> PlayerRating:
        pr = PlayerRating(player_id=r["player_id"])
        pr.overall = float(r["overall"])
        pr.hard = float(r["hard"])
        pr.clay = float(r["clay"])
        pr.grass = float(r["grass"])
        pr.carpet = float(r["carpet"])
        pr.matches_played = r["matches_played"]
        return pr

    r1 = to_rating(by_id[p1])
    r2 = to_rating(by_id[p2])

    p1_win = predict(r1, r2, surface)

    return {
        "surface": surface,
        "p1": {
            "id": p1, "name": by_id[p1]["name"], "country": by_id[p1]["country"],
            "rating_overall": float(by_id[p1]["overall"]),
            "rating_surface": float(by_id[p1][surface.lower()]),
            "rating_blended": blended_rating(r1, surface),
            "win_probability": p1_win,
            "fair_odds": prob_to_fair_odds(p1_win),
        },
        "p2": {
            "id": p2, "name": by_id[p2]["name"], "country": by_id[p2]["country"],
            "rating_overall": float(by_id[p2]["overall"]),
            "rating_surface": float(by_id[p2][surface.lower()]),
            "rating_blended": blended_rating(r2, surface),
            "win_probability": 1.0 - p1_win,
            "fair_odds": prob_to_fair_odds(1.0 - p1_win),
        },
    }
