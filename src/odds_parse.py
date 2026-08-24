"""Parse Odds API event-odds payloads into odds_snapshots rows."""

from __future__ import annotations

import sqlite3
from typing import Any

from src.logging_setup import setup_logging
from src.odds_http import _iso_utc

logger = setup_logging()

def parse_event_odds_rows(
    event_payload: dict[str, Any],
    *,
    captured_at_utc: str,
    configured_market: str,
) -> list[dict[str, Any]]:
    """Flatten one event-odds response into odds_snapshots row dicts."""
    rows: list[dict[str, Any]] = []
    game_id = str(event_payload.get("id") or "")
    if not game_id:
        logger.warning("Event payload missing id; skipping")
        return rows

    bookmakers = event_payload.get("bookmakers")
    if not bookmakers:
        logger.info("Game %s has no bookmakers/props posted", game_id)
        return rows
    if not isinstance(bookmakers, list):
        logger.error("Malformed bookmakers for game %s", game_id)
        return rows

    for book in bookmakers:
        if not isinstance(book, dict):
            logger.error("Malformed bookmaker entry for game %s", game_id)
            continue
        book_key = str(book.get("key") or book.get("title") or "unknown")
        markets = book.get("markets") or []
        if not isinstance(markets, list):
            logger.error("Malformed markets for book %s game %s", book_key, game_id)
            continue

        matched = False
        for market in markets:
            if not isinstance(market, dict):
                continue
            market_key = str(market.get("key") or "")
            # Accept exact market or its _alternate sibling when configured base matches.
            base = configured_market.removesuffix("_alternate")
            if market_key != configured_market and market_key != f"{base}_alternate":
                continue
            matched = True
            is_alternate = market_key.endswith("_alternate")
            outcomes = market.get("outcomes") or []
            if not isinstance(outcomes, list):
                logger.error(
                    "Malformed outcomes for book=%s market=%s game=%s",
                    book_key,
                    market_key,
                    game_id,
                )
                continue

            # Group Over/Under by (player, line).
            grouped: dict[tuple[str, float | None], dict[str, Any]] = {}
            for outcome in outcomes:
                if not isinstance(outcome, dict):
                    continue
                side = str(outcome.get("name") or "").strip().lower()
                player = outcome.get("description")
                if player is None:
                    # Some books put the player in name for non O/U; skip unknown shapes.
                    logger.warning(
                        "Outcome missing description (player) book=%s market=%s",
                        book_key,
                        market_key,
                    )
                    continue
                player_name = str(player)
                point = outcome.get("point")
                line: float | None
                try:
                    line = float(point) if point is not None else None
                except (TypeError, ValueError):
                    line = None
                price = outcome.get("price")
                key = (player_name, line)
                slot = grouped.setdefault(
                    key,
                    {
                        "player_name_raw": player_name,
                        "line": line,
                        "over_price": None,
                        "under_price": None,
                        "market": market_key,
                        "is_alternate": int(is_alternate),
                    },
                )
                if side == "over":
                    slot["over_price"] = price
                elif side == "under":
                    slot["under_price"] = price
                else:
                    logger.warning(
                        "Unexpected outcome side %r book=%s player=%s",
                        side,
                        book_key,
                        player_name,
                    )

            for slot in grouped.values():
                rows.append(
                    {
                        "captured_at_utc": captured_at_utc,
                        "game_id": game_id,
                        "book": book_key,
                        "market": slot["market"],
                        "player_name_raw": slot["player_name_raw"],
                        "line": slot["line"],
                        "over_price": slot["over_price"],
                        "under_price": slot["under_price"],
                        "is_alternate": slot["is_alternate"],
                    }
                )

        if not matched:
            logger.info(
                "Book %s missing market %s for game %s",
                book_key,
                configured_market,
                game_id,
            )

    return rows


def parse_raw_payload(payload: dict[str, Any], configured_market: str) -> list[dict[str, Any]]:
    captured = str(payload.get("captured_at_utc") or _iso_utc())
    event_odds = payload.get("event_odds") or []
    rows: list[dict[str, Any]] = []

    if isinstance(event_odds, dict):
        # Map of event_id -> payload
        items = list(event_odds.values())
    elif isinstance(event_odds, list):
        items = event_odds
    else:
        logger.error("Malformed event_odds in raw payload")
        return []

    for item in items:
        if item is None:
            continue
        if not isinstance(item, dict):
            logger.error("Skipping malformed event_odds item")
            continue
        # Nested under "data" for historical-style wrappers (not used live).
        event_body = item.get("data") if "data" in item and "bookmakers" not in item else item
        if not isinstance(event_body, dict):
            logger.error("Skipping malformed event body")
            continue
        try:
            rows.extend(
                parse_event_odds_rows(
                    event_body,
                    captured_at_utc=captured,
                    configured_market=configured_market,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed parsing event odds: %s", exc)
            continue
    return rows


def insert_snapshots(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO odds_snapshots (
            captured_at_utc, game_id, book, market,
            player_name_raw, line, over_price, under_price, is_alternate
        ) VALUES (
            :captured_at_utc, :game_id, :book, :market,
            :player_name_raw, :line, :over_price, :under_price, :is_alternate
        )
        """,
        rows,
    )
    conn.commit()
    return len(rows)
