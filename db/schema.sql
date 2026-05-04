-- ============================================================================
-- Tennis Edge — Database Schema
-- Postgres (Neon-compatible)
-- ============================================================================

-- Players (from Jeff Sackmann's atp_players.csv / wta_players.csv)
CREATE TABLE IF NOT EXISTS players (
    player_id      INTEGER     PRIMARY KEY,
    name           VARCHAR(255) NOT NULL,
    country        CHAR(3),
    hand           CHAR(1),
    height         INTEGER,
    birth_date     DATE,
    tour           CHAR(3)     NOT NULL DEFAULT 'ATP',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_players_tour ON players(tour);
CREATE INDEX IF NOT EXISTS idx_players_name ON players(LOWER(name));

-- Tournaments
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id  VARCHAR(50)  PRIMARY KEY,
    name           VARCHAR(255) NOT NULL,
    surface        VARCHAR(20)  NOT NULL,
    draw_size      INTEGER,
    level          VARCHAR(20),
    start_date     DATE,
    tour           CHAR(3)      NOT NULL DEFAULT 'ATP'
);
CREATE INDEX IF NOT EXISTS idx_tournaments_date ON tournaments(start_date DESC);
CREATE INDEX IF NOT EXISTS idx_tournaments_tour ON tournaments(tour);

-- Matches (historical and current)
CREATE TABLE IF NOT EXISTS matches (
    match_id            BIGSERIAL    PRIMARY KEY,
    tournament_id       VARCHAR(50)  REFERENCES tournaments(tournament_id),
    match_num           INTEGER,
    match_date          DATE         NOT NULL,
    round               VARCHAR(10),
    surface             VARCHAR(20),
    best_of             INTEGER,
    winner_id           INTEGER      REFERENCES players(player_id),
    loser_id            INTEGER      REFERENCES players(player_id),
    score               VARCHAR(64),
    minutes             INTEGER,
    -- Serve/return stats (from Sackmann)
    w_ace INTEGER, w_df INTEGER, w_svpt INTEGER, w_1st_in INTEGER,
    w_1st_won INTEGER, w_2nd_won INTEGER, w_sv_gms INTEGER,
    w_bp_saved INTEGER, w_bp_faced INTEGER,
    l_ace INTEGER, l_df INTEGER, l_svpt INTEGER, l_1st_in INTEGER,
    l_1st_won INTEGER, l_2nd_won INTEGER, l_sv_gms INTEGER,
    l_bp_saved INTEGER, l_bp_faced INTEGER,
    -- Pre-match rating snapshots (filled by Elo pipeline)
    winner_elo_pre              NUMERIC(8,3),
    loser_elo_pre               NUMERIC(8,3),
    winner_surface_elo_pre      NUMERIC(8,3),
    loser_surface_elo_pre       NUMERIC(8,3),
    -- Constraint: a tournament can't have two matches with same number
    UNIQUE (tournament_id, match_num)
);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date DESC);
CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner_id);
CREATE INDEX IF NOT EXISTS idx_matches_loser ON matches(loser_id);
CREATE INDEX IF NOT EXISTS idx_matches_surface ON matches(surface);

-- Current ratings (one row per player — latest snapshot)
CREATE TABLE IF NOT EXISTS ratings (
    player_id        INTEGER     PRIMARY KEY REFERENCES players(player_id),
    overall          NUMERIC(8,3) NOT NULL DEFAULT 1500,
    hard             NUMERIC(8,3) NOT NULL DEFAULT 1500,
    clay             NUMERIC(8,3) NOT NULL DEFAULT 1500,
    grass            NUMERIC(8,3) NOT NULL DEFAULT 1500,
    carpet           NUMERIC(8,3) NOT NULL DEFAULT 1500,
    matches_played   INTEGER     NOT NULL DEFAULT 0,
    matches_hard     INTEGER     NOT NULL DEFAULT 0,
    matches_clay     INTEGER     NOT NULL DEFAULT 0,
    matches_grass    INTEGER     NOT NULL DEFAULT 0,
    matches_carpet   INTEGER     NOT NULL DEFAULT 0,
    last_match_date  DATE,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ratings_overall ON ratings(overall DESC);
CREATE INDEX IF NOT EXISTS idx_ratings_clay ON ratings(clay DESC);
CREATE INDEX IF NOT EXISTS idx_ratings_grass ON ratings(grass DESC);
CREATE INDEX IF NOT EXISTS idx_ratings_hard ON ratings(hard DESC);

-- Pipeline state — track what's been processed (idempotent loads)
CREATE TABLE IF NOT EXISTS pipeline_state (
    key         VARCHAR(64) PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Helper view: top-N players per surface
CREATE OR REPLACE VIEW v_rankings_overall AS
SELECT
    r.player_id,
    p.name,
    p.country,
    p.tour,
    r.overall,
    r.matches_played,
    r.last_match_date,
    ROW_NUMBER() OVER (PARTITION BY p.tour ORDER BY r.overall DESC) AS rank
FROM ratings r
JOIN players p ON p.player_id = r.player_id
WHERE r.matches_played >= 20;
