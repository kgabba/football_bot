import csv
import io
import os
from dataclasses import dataclass
from typing import List

import httpx

# Берём URL CSV-экспорта Google Sheets из env, по умолчанию — твоя таблица (gid=0)
PLAYERS_SHEET_CSV_URL = os.environ.get(
    "PLAYERS_SHEET_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1osDxnnQ-7MUvS3cUpZBdW7ess6fLcQtiRZqzhMlvgRc/export?format=csv&gid=0",
)


@dataclass
class PlayerRecord:
    """Запись из Google Sheets (игрок с полем tg для привязки к Telegram)."""
    name: str
    surname: str
    position: str
    rating: int
    card_name: str
    photo_filename: str
    mvp: int
    games: int
    goals: int
    wins: int
    tg: str  # ник в Telegram без @, для матча с проголосовавшими


def load_players(csv_url: str | None = None) -> List[PlayerRecord]:
    """
    Загружает игроков из Google Sheets (CSV-экспорт первой страницы).
    Лишние столбцы в таблице не мешают, берём только нужные.
    """
    url = csv_url or PLAYERS_SHEET_CSV_URL
    if not url:
        return []
    players: List[PlayerRecord] = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            # Декодируем явно UTF-8 (utf-8-sig убирает BOM, если Google его подставил)
            text = resp.content.decode("utf-8-sig")
    except Exception:
        return []

    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            rating = int((row.get("rating") or row.get("Рейтинг") or "60").strip())
        except ValueError:
            rating = 60
        try:
            mvp = int((row.get("mvp") or row.get("MVP") or "0").strip())
        except ValueError:
            mvp = 0
        try:
            games = int((row.get("games") or row.get("Игры") or "0").strip())
        except ValueError:
            games = 0
        try:
            goals = int((row.get("goals") or row.get("Голы") or "0").strip())
        except ValueError:
            goals = 0
        try:
            wins = int((row.get("wins") or row.get("Победы") or "0").strip())
        except ValueError:
            wins = 0
        tg_raw = (row.get("tg") or row.get("TG") or "").strip().lower()
        tg = tg_raw.lstrip("@") if tg_raw else ""
        players.append(
            PlayerRecord(
                name=(row.get("name") or row.get("Имя") or "").strip(),
                surname=(row.get("surname") or row.get("Фамилия") or "").strip(),
                position=(row.get("position") or row.get("Позиция") or "").strip().lower(),
                rating=rating,
                card_name=(row.get("card_name") or row.get("card") or "").strip(),
                photo_filename=(row.get("photo_filename") or row.get("photo") or "").strip(),
                mvp=mvp,
                games=games,
                goals=goals,
                wins=wins,
                tg=tg,
            )
        )
    return players


def get_match_player_indices(players: List[PlayerRecord], voted_usernames: set[str]) -> List[int]:
    """
    Индексы игроков из таблицы, чей tg совпадает с кем-то из voted_usernames.
    voted_usernames — ники без @, в любом регистре.
    """
    normalized = {u.lstrip("@").lower() if u else "" for u in voted_usernames if u}
    return [i for i, p in enumerate(players) if p.tg and p.tg.lower() in normalized]


def build_lineup_csv(players: List[PlayerRecord], distribution: List[tuple[int, int]]) -> str:
    """
    distribution: list of (player_index, team) where team is 1 or 2.
    players — полный список из load_players(); индексы в distribution ссылаются на него.
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["team", "name", "surname", "position", "rating", "card_name", "photo_filename"])
    for idx, team in distribution:
        p = players[idx]
        w.writerow([team, p.name, p.surname, p.position, p.rating, p.card_name or "", p.photo_filename or ""])
    return buf.getvalue().strip()
