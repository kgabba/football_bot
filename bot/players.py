import csv
import os
from dataclasses import dataclass
from typing import List

# Папка с данными бота (рядом с корнем проекта или в текущей директории)
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYERS_CSV_PATH = os.path.join(BOT_DIR, "data", "players.csv")


@dataclass
class PlayerRecord:
    """Запись из players.csv (полная база игроков)."""
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


def load_players(path: str | None = None) -> List[PlayerRecord]:
    path = path or PLAYERS_CSV_PATH
    if not os.path.exists(path):
        return []
    players: List[PlayerRecord] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rating = int((row.get("rating") or "60").strip())
            except ValueError:
                rating = 60
            try:
                mvp = int((row.get("mvp") or "0").strip())
            except ValueError:
                mvp = 0
            try:
                games = int((row.get("games") or "0").strip())
            except ValueError:
                games = 0
            try:
                goals = int((row.get("goals") or "0").strip())
            except ValueError:
                goals = 0
            try:
                wins = int((row.get("wins") or "0").strip())
            except ValueError:
                wins = 0
            players.append(
                PlayerRecord(
                    name=(row.get("name") or "").strip(),
                    surname=(row.get("surname") or "").strip(),
                    position=(row.get("position") or "").strip().lower(),
                    rating=rating,
                    card_name=(row.get("card_name") or "").strip(),
                    photo_filename=(row.get("photo_filename") or "").strip(),
                    mvp=mvp,
                    games=games,
                    goals=goals,
                    wins=wins,
                )
            )
    return players


def build_lineup_csv(players: List[PlayerRecord], distribution: List[tuple[int, int]]) -> str:
    """
    distribution: list of (player_index, team) where team is 1 or 2.
    players — полный список из load_players(); индексы в distribution ссылаются на него.
    """
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["team", "name", "surname", "position", "rating", "card_name", "photo_filename"])
    for idx, team in distribution:
        p = players[idx]
        w.writerow([team, p.name, p.surname, p.position, p.rating, p.card_name or "", p.photo_filename or ""])
    return buf.getvalue().strip()
