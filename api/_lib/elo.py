"""
Surface-aware Elo rating system for tennis.

Implements:
- Standard Elo with FiveThirtyEight-style dynamic K-factor
  K = 250 / (matches_played + 5)^0.4
  → newer players move faster, established players are stable

- Separate ratings per surface (Hard, Clay, Grass, Carpet) plus an overall rating
- Predictions blend surface-specific rating with overall:
  blended = α * surface_rating + (1-α) * overall_rating
  with α = 0.7 (tunable, see SURFACE_WEIGHT)

References:
- 538's tennis Elo: https://fivethirtyeight.com/features/serena-williams-and-the-difference-between-all-time-great-and-greatest-of-all-time/
- Tennis Abstract on sELO: http://www.tennisabstract.com/blog/2019/12/03/an-introduction-to-tennis-elo/
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Tuple

INITIAL_RATING: float = 1500.0
SURFACE_WEIGHT: float = 0.7  # How much to weight surface-specific rating vs overall
SURFACES = ("Hard", "Clay", "Grass", "Carpet")


def normalize_surface(s: str | None) -> str:
    """Normalize surface string. Default to Hard for unknowns."""
    if not s:
        return "Hard"
    s = s.strip().capitalize()
    return s if s in SURFACES else "Hard"


@dataclass
class PlayerRating:
    """In-memory representation of a player's current rating state."""
    player_id: int
    overall: float = INITIAL_RATING
    hard: float = INITIAL_RATING
    clay: float = INITIAL_RATING
    grass: float = INITIAL_RATING
    carpet: float = INITIAL_RATING
    matches_played: int = 0
    matches_by_surface: Dict[str, int] = field(default_factory=lambda: {s: 0 for s in SURFACES})

    def surface_rating(self, surface: str) -> float:
        return getattr(self, normalize_surface(surface).lower())

    def set_surface_rating(self, surface: str, value: float) -> None:
        setattr(self, normalize_surface(surface).lower(), value)

    def matches_on_surface(self, surface: str) -> int:
        return self.matches_by_surface.get(normalize_surface(surface), 0)


# ---------------------------------------------------------------------------
# Core formulae
# ---------------------------------------------------------------------------

def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Standard Elo expected score for player A vs player B.
    Returns P(A wins) given the two ratings.
    """
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def k_factor(matches_played: int, base: float = 250.0, offset: int = 5, exponent: float = 0.4) -> float:
    """
    Dynamic K-factor (FiveThirtyEight style).

    matches_played=0   → K ≈ 109   (huge swings for first matches)
    matches_played=20  → K ≈ 60
    matches_played=100 → K ≈ 31
    matches_played=500 → K ≈ 16
    """
    return base / math.pow(matches_played + offset, exponent)


def blended_rating(player: PlayerRating, surface: str, alpha: float = SURFACE_WEIGHT) -> float:
    """Blend surface-specific rating with overall rating."""
    surface = normalize_surface(surface)
    return alpha * player.surface_rating(surface) + (1.0 - alpha) * player.overall


# ---------------------------------------------------------------------------
# Match update & prediction
# ---------------------------------------------------------------------------

def predict(p1: PlayerRating, p2: PlayerRating, surface: str, alpha: float = SURFACE_WEIGHT) -> float:
    """
    Predicted probability that p1 beats p2 on the given surface.
    Uses the blended rating (surface-weighted).
    """
    return expected_score(blended_rating(p1, surface, alpha), blended_rating(p2, surface, alpha))


def update_after_match(
    winner: PlayerRating,
    loser: PlayerRating,
    surface: str,
) -> Tuple[float, float, float, float]:
    """
    Mutate `winner` and `loser` in place after a match result.

    Updates BOTH the overall rating and the surface-specific rating.
    Each player updates with their own K-factor (asymmetric — common practice).

    Returns the pre-match ratings (winner_overall, loser_overall,
    winner_surface, loser_surface) for snapshot/audit purposes.
    """
    surface = normalize_surface(surface)

    # ---- Snapshot pre-match values ----
    w_overall_pre = winner.overall
    l_overall_pre = loser.overall
    w_surface_pre = winner.surface_rating(surface)
    l_surface_pre = loser.surface_rating(surface)

    # ---- Overall rating update ----
    expected_w_overall = expected_score(w_overall_pre, l_overall_pre)
    k_w = k_factor(winner.matches_played)
    k_l = k_factor(loser.matches_played)

    winner.overall = w_overall_pre + k_w * (1.0 - expected_w_overall)
    loser.overall = l_overall_pre - k_l * (1.0 - expected_w_overall)

    # ---- Surface rating update ----
    expected_w_surface = expected_score(w_surface_pre, l_surface_pre)
    k_w_s = k_factor(winner.matches_on_surface(surface))
    k_l_s = k_factor(loser.matches_on_surface(surface))

    winner.set_surface_rating(surface, w_surface_pre + k_w_s * (1.0 - expected_w_surface))
    loser.set_surface_rating(surface, l_surface_pre - k_l_s * (1.0 - expected_w_surface))

    # ---- Match counters ----
    winner.matches_played += 1
    loser.matches_played += 1
    winner.matches_by_surface[surface] = winner.matches_on_surface(surface) + 1
    loser.matches_by_surface[surface] = loser.matches_on_surface(surface) + 1

    return w_overall_pre, l_overall_pre, w_surface_pre, l_surface_pre


# ---------------------------------------------------------------------------
# Utility: convert prob ⇄ fair odds, edge calculation
# ---------------------------------------------------------------------------

def prob_to_fair_odds(p: float) -> float:
    """Convert probability to fair decimal odds (no margin)."""
    return 1.0 / p if p > 0 else float("inf")


def edge(model_prob: float, market_odds: float) -> float:
    """
    Expected value per €1 staked.
    edge > 0  → +EV bet (according to model)
    edge = model_prob * market_odds - 1
    """
    return model_prob * market_odds - 1.0


def devig_two_way(odds_a: float, odds_b: float) -> Tuple[float, float]:
    """
    Remove the bookmaker margin from a two-way market using the
    multiplicative (proportional) method.

    Returns (fair_prob_a, fair_prob_b).
    For more accuracy on lopsided markets use Shin's method (TODO).
    """
    p_a_raw = 1.0 / odds_a
    p_b_raw = 1.0 / odds_b
    total = p_a_raw + p_b_raw
    return p_a_raw / total, p_b_raw / total
