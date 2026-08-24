"""Feature column registry for player_game_features (phase 4)."""

from __future__ import annotations

# Numeric feature columns stored on player_game_features (excluding keys).
FEATURE_COLUMNS: list[str] = [
    # Player form (per-40, as-of)
    "pts_p40_l3",
    "pts_p40_l5",
    "pts_p40_l10",
    "pts_p40_ewm",
    "pts_p40_std",
    "reb_p40_l3",
    "reb_p40_l5",
    "reb_p40_l10",
    "reb_p40_ewm",
    "reb_p40_std",
    "ast_p40_l3",
    "ast_p40_l5",
    "ast_p40_l10",
    "ast_p40_ewm",
    "ast_p40_std",
    "fg3m_p40_l3",
    "fg3m_p40_l5",
    "fg3m_p40_l10",
    "fg3m_p40_ewm",
    "fg3m_p40_std",
    "games_played",
    "player_form_prior_weight",
    # Role
    "usage_rate_shrunk",
    "started",
    "start_rate_l10",
    "minutes_share_l5",
    "three_rate_std",
    "two_rate_std",
    "ft_rate_std",
    # Team (shrunk)
    "team_pace_shrunk",
    "team_off_rtg_shrunk",
    "team_def_rtg_shrunk",
    "team_games_played",
    "team_prior_weight",
    # Opponent (shrunk hard)
    "opp_pace_shrunk",
    "opp_def_rtg_shrunk",
    "opp_pos_def_shrunk",
    "opp_games_played",
    "opp_prior_weight",
    # Situational
    "days_rest",
    "rest_long_break",
    "is_b2b",
    "is_home",
    "tz_hours_crossed",
    "game_number",
    # Teammate availability
    "minutes_vacated",
    "same_pos_minutes_vacated",
    "primary_bh_out",
]

KEY_COLUMNS: list[str] = [
    "game_id",
    "player_id",
    "game_date",
    "season",
    "team_id",
    "opponent_id",
    "position",
]


def features_ddl() -> str:
    cols = [
        "game_id TEXT NOT NULL",
        "player_id TEXT NOT NULL",
        "game_date TEXT",
        "season INTEGER",
        "team_id TEXT",
        "opponent_id TEXT",
        "position TEXT",
    ]
    cols.extend(f"{c} REAL" for c in FEATURE_COLUMNS)
    cols.append("PRIMARY KEY (game_id, player_id)")
    body = ",\n    ".join(cols)
    return f"CREATE TABLE IF NOT EXISTS player_game_features (\n    {body}\n);\n"
