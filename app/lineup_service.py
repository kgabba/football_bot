import csv
import os
from dataclasses import dataclass
from typing import List, Tuple, Dict

from PIL import Image, ImageDraw, ImageFont, ImageChops


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CARDS_DIR = os.path.join(ASSETS_DIR, "cards")
PLAYERS_DIR = os.path.join(ASSETS_DIR, "players")
FIELD_IMAGE_PATH = os.path.join(ASSETS_DIR, "field.png")
STATIC_DIR = os.path.join(BASE_DIR, "static")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")


os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CARDS_DIR, exist_ok=True)
os.makedirs(PLAYERS_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)


LINEUPS_CSV_PATH = os.path.join(DATA_DIR, "lineups.csv")


@dataclass
class Player:
    team: int
    name: str
    surname: str
    position: str  # "врт" | "защ" | "фрв"
    rating: int  # 60–99
    card_name: str  # optional override, e.g. "gold", "silver", "bronze"
    photo_filename: str


def read_lineups_from_csv(path: str = LINEUPS_CSV_PATH) -> Tuple[List[Player], List[Player]]:
    if not os.path.exists(path):
        return [], []

    team1: List[Player] = []
    team2: List[Player] = []

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                team_num = int(row.get("team", "").strip())
            except (ValueError, AttributeError):
                continue

            try:
                rating = int(row.get("rating", "").strip())
            except (ValueError, AttributeError):
                rating = 60

            player = Player(
                team=team_num,
                name=(row.get("name") or "").strip(),
                surname=(row.get("surname") or "").strip(),
                position=(row.get("position") or "").strip().lower(),
                rating=rating,
                card_name=(row.get("card_name") or "").strip().lower(),
                photo_filename=(row.get("photo_filename") or "").strip(),
            )

            if player.team == 1:
                team1.append(player)
            elif player.team == 2:
                team2.append(player)

    return team1, team2


def choose_card_background(player: Player) -> str:
    """Return path to background card image for given player."""
    # Override from CSV if provided and points to an existing file
    if player.card_name:
        candidate = os.path.join(CARDS_DIR, f"{player.card_name}.png")
        if os.path.exists(candidate):
            return candidate

    # Auto choose by rating
    if player.rating < 80:
        filename = "bronze.png"
    elif 80 <= player.rating <= 85:
        filename = "silver.png"
    else:
        filename = "gold.png"

    return os.path.join(CARDS_DIR, filename)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Try to load a TTF font; fallback to default PIL font if not available.
    """
    # Common path on many Linux systems; adjust as needed.
    possible_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def generate_player_card(player: Player) -> Image.Image:
    """
    Build a single player card image (Pillow Image) using:
    - background card (bronze/silver/gold)
    - player photo (centered, resized)
    - rating top-left
    - name centered under photo
    """
    bg_path = choose_card_background(player)
    if not os.path.exists(bg_path):
        raise FileNotFoundError(f"Card background not found: {bg_path}")

    # Основное фото игрока (поддерживает кириллицу в имени файла)
    # Если не найдено — используем запасное "unknown.png".
    photo_filename = player.photo_filename or ""
    player_photo_path = os.path.join(PLAYERS_DIR, photo_filename)
    if not os.path.exists(player_photo_path):
        fallback_path = os.path.join(PLAYERS_DIR, "unknown.png")
        if not os.path.exists(fallback_path):
            # Если даже unknown.png нет — это уже критическая ошибка
            raise FileNotFoundError(
                f"Player photo not found: {player_photo_path} and fallback unknown.png is missing"
            )
        player_photo_path = fallback_path

    bg = Image.open(bg_path).convert("RGBA")
    w, h = bg.size  # Expected 1288 x 1800, but we respect actual size



# Load player image
    player_img = Image.open(player_photo_path).convert("RGBA")

    # Upscale to larger size (1.5 times previous parameters, but calculate target preserving aspect)
    target_width = int(w * 1.425 * 0.42) #регулируем множитель - размер фото
    target_height = int(h * 1.17 * 0.42) #регулируем множитель - размер фото
    player_img = player_img.resize((target_width, target_height), Image.LANCZOS)  # Use resize for upscale

    # Ensure it fits within the card boundaries (downscale if needed)
    if player_img.width > w or player_img.height > h:
        scale = min(w / player_img.width, h / player_img.height)
        new_size = (int(player_img.width * scale), int(player_img.height * scale))
        player_img = player_img.resize(new_size, Image.LANCZOS)




    # Лёгкий градиент прозрачности только у нижней части фото
    try:
        alpha = player_img.split()[3]
        grad = Image.new("L", player_img.size, 255)
        gw, gh = grad.size
        start_y = int(gh * 0.7)
        for y in range(gh):
            if y < start_y:
                val = 255
            else:
                # 0.0 в точке start_y, 1.0 внизу
                t = (y - start_y) / max(1, gh - 1 - start_y)
                # В самом низу уменьшаем альфу примерно до 70%
                val = int(255 * (1.0 - 0.3 * t))
            for x in range(gw):
                grad.putpixel((x, y), val)
        new_alpha = ImageChops.multiply(alpha, grad)
        player_img.putalpha(new_alpha)
    except Exception:
        # Если что-то пошло не так с альфой — просто оставляем как есть
        pass

    # Position player slightly lower vertically (shifted down)
    px = (w - player_img.width) // 2
    py = int(h * 0.19)  # регулирует положение по Y (меньше - выше)

    card = bg.copy()
    card.paste(player_img, (px, py), mask=player_img)

    draw = ImageDraw.Draw(card)

    # Draw rating top-left (shifted down)
    rating_font = load_font(size=int(h * 0.09))
    rating_text = str(player.rating)
    rating_x = int(w * 0.13)
    rating_y = int(h * 0.19)  # shifted from 0.08 to 0.13
    stroke_width = max(1, int(h * 0.003))
    # Чёрный текст с белой обводкой
    draw.text(
        (rating_x, rating_y),
        rating_text,
        font=rating_font,
        fill=(0, 0, 0, 255),
        stroke_width=stroke_width,
        stroke_fill=(255, 255, 255, 255),
    )

    rating_bbox = draw.textbbox((rating_x, rating_y), rating_text, font=rating_font)
    rating_h = rating_bbox[3] - rating_bbox[1]

    # Под рейтингом пишем позицию (ВРТ / ЗАЩ / ФРВ)
    pos_font = load_font(size=int(h * 0.06)) #размер шрифта
    pos_map = {
        "врт": "ВРТ",
        "защ": "ЗЩ",
        "фрв": "ФРВ",
    }
    pos_text = pos_map.get(player.position, player.position.upper()[:3])
    if pos_text:
        # Чуть ниже рейтинга, с зазором
        pos_y = rating_y + rating_h + int(h * 0.02)
        pos_bbox = draw.textbbox((rating_x, pos_y), pos_text, font=pos_font)
        pos_h = pos_bbox[3] - pos_bbox[1]
        # Не даём позиции вылезти за верхнюю четверть карты (adjusted)
        max_pos_y = int(h * 0.33)  # shifted from 0.25 to 0.30
        if pos_y + pos_h > max_pos_y:
            pos_y = max_pos_y - pos_h
        draw.text(
            (rating_x, pos_y),
            pos_text,
            font=pos_font,
            fill=(0, 0, 0, 255),
            stroke_width=stroke_width,
            stroke_fill=(255, 255, 255, 255),
        )

    # Draw player name under photo (ещё крупнее, чёрный шрифт)
    name_font = load_font(size=int(h * 0.085))
    name_text = player.name or (player.surname or "")
    name_text = name_text.strip()
    if not name_text:
        name_text = "Player"

    # Pillow 10+ убрал textsize, используем textbbox
    bbox = draw.textbbox((0, 0), name_text, font=name_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    name_x = (w - text_w) // 2
    name_y = py + player_img.height + int(h * 0.02)
    # Не даём имени вылезти за нижнюю границу карты
    max_name_y = int(h * 0.9)
    if name_y + text_h > max_name_y:
        name_y = max_name_y - text_h
    draw.text(
        (name_x, name_y),
        name_text,
        font=name_font,
        fill=(0, 0, 0, 255),
        stroke_width=stroke_width,
        stroke_fill=(255, 255, 255, 255),
    )

    return card


def compute_positions_for_team(
    players: List[Player],
    field_size: Tuple[int, int],
    card_max_width: int,
) -> Dict[int, Tuple[int, int]]:
    """
    Compute positions (x, y) on the field image for each player index.

    Для 7–11 игроков используем преднастроенные схемы, чтобы:
    - карточки были симметричны относительно вертикальной оси;
    - не было наслоений по горизонтали;
    - поле было заполнено по высоте (от атаки к обороне).
    """
    width, height = field_size
    n = len(players)

    if n == 0:
        return {}

    # Выбираем вратаря
    gk_indices = [i for i, p in enumerate(players) if p.position == "врт"]
    if gk_indices:
        gk = gk_indices[0]
    else:
        gk = 0

    others = [i for i in range(n) if i != gk]
    # Разделяем остальных на линии по ролям
    fwds_all = [i for i in others if players[i].position == "фрв"]
    defs_all = [i for i in others if players[i].position == "защ"]
    others_without_roles = [
        i for i in others if i not in fwds_all and i not in defs_all
    ]
    others_n = len(others)

    # Схемы: количество игроков по линиям от атаки к обороне (без учёта ГК)
    formations = {
        7: [1, 2, 3],   # 1 (атакующая линия) – 2 (центр) – 3 (ближе к своим воротам) + ГК
        8: [1, 3, 3],   # 1–3–3 + ГК
        9: [2, 3, 3],   # 2–3–3 + ГК
        10: [2, 3, 4],  # 2–3–4 + ГК
        11: [3, 3, 4],  # 3–3–4 + ГК
    }

    formation = formations.get(n)

    positions: Dict[int, Tuple[int, int]] = {}

    def distribute_line(indices: List[int], y_frac: float) -> None:
        if not indices:
            return
        count = len(indices)
        # Разреженная расстановка: увеличенные боковые отступы, чтобы
        # краевые игроки были ближе к центру и между картами был зазор.
        margin = int(width * 0.18)  # 18% ширины поля на margins
        available_width = max(1, width - 2 * margin)
        if count == 1:
            xs = [width // 2]
        else:
            step_x = available_width / max(1, count - 1)
            xs = [int(margin + i * step_x) for i in range(count)]
        y = int(height * y_frac)
        for idx, x in zip(indices, xs):
            positions[idx] = (x, y)

    # Если схема не найдена или не совпадает по количеству игроков — одна линия + ГК.
    if not formation or sum(formation) != others_n:
        distribute_line(others, 0.45)
        positions[gk] = (width // 2, int(height * 0.85))
        return positions

    # Вертикальные уровни: от атаки до обороны (без ГК)
    # Форварды чуть выше, центр тоже подтягиваем вверх, защита ближе к воротам.
    lines_count = len(formation)
    gk_y_frac = 0.88  # вратарь чуть ниже
    if lines_count == 3:
        # Явные уровни для 3 линий: фрв, центр, защ
        # Среднюю и нижнюю линии поднимаем чуть выше.
        line_y_fracs = [0.16, 0.40, 0.64]
    else:
        top_y_frac = 0.14
        span = gk_y_frac - top_y_frac
        step = span / (lines_count + 1)
        line_y_fracs = [top_y_frac + step * (i + 1) for i in range(lines_count)]

    # Сначала распределяем форвардов: в приоритете верхняя линия, затем центр, затем низ
    lines: List[List[int]] = [[] for _ in range(lines_count)]
    caps = formation

    def assign_indices(indices: List[int], preferred_orders: List[int]) -> None:
        for idx in indices:
            placed = False
            for line_idx in preferred_orders:
                if 0 <= line_idx < lines_count and len(lines[line_idx]) < caps[line_idx]:
                    lines[line_idx].append(idx)
                    placed = True
                    break
            if not placed:
                # Если все предпочитаемые линии переполнены — ищем любую с местом
                for line_idx in range(lines_count):
                    if len(lines[line_idx]) < caps[line_idx]:
                        lines[line_idx].append(idx)
                        break

    # Форварды: верх -> центр -> низ
    assign_indices(fwds_all, list(range(lines_count)))
    # Защита: низ -> центр -> верх
    assign_indices(defs_all, list(reversed(range(lines_count))))
    # Остальные: центр -> верх -> низ
    center_first = list(range(lines_count))
    if lines_count == 3:
        center_first = [1, 0, 2]
    assign_indices(others_without_roles, center_first)

    # Теперь у нас есть списки индексов по линиям; раскладываем их по X/Y
    for line_indices, y_frac in zip(lines, line_y_fracs):
        distribute_line(line_indices, y_frac)

    # Вратарь — отдельно внизу по центру
    positions[gk] = (width // 2, int(height * gk_y_frac))

    return positions


def generate_team_lineup_image(players: List[Player], team_number: int) -> str:
    """
    Generate lineup image for one team: field background + player cards.
    Returns path to generated PNG.
    """
    if not players:
        raise ValueError("No players for team")

    if not os.path.exists(FIELD_IMAGE_PATH):
        raise FileNotFoundError(f"Field image not found: {FIELD_IMAGE_PATH}")

    field = Image.open(FIELD_IMAGE_PATH).convert("RGBA")
    field_w, field_h = field.size

    # Размер карточки относительно поля: немного уменьшаем, чтобы между
    # всеми картами гарантированно оставалось пространство.
    n = len(players)

    card_w_frac = 0.19

    card_max_width = int(field_w * card_w_frac)
    card_max_height = min(int(field_h * 0.42), int(card_max_width * 1.4))

    positions = compute_positions_for_team(players, (field_w, field_h), card_max_width)

    composed = field.copy()

    for idx, player in enumerate(players):
        card = generate_player_card(player)
        card.thumbnail((card_max_width, card_max_height), Image.LANCZOS)

        x, y = positions.get(idx, (field_w // 2, field_h // 2))

        # Center card on (x, y)
        paste_x = int(x - card.width / 2)
        paste_y = int(y - card.height / 2)

        composed.paste(card, (paste_x, paste_y), mask=card)

    output_filename = f"team{team_number}_lineup.png"
    output_path = os.path.join(GENERATED_DIR, output_filename)
    composed.save(output_path, format="PNG")

    return output_path


def generate_both_lineups() -> Tuple[str, str]:
    """
    Main high-level function:
    - read CSV
    - generate team1 and team2 images
    - return their file system paths
    """
    team1, team2 = read_lineups_from_csv()

    if not team1 or not team2:
        raise ValueError("Lineups not fully defined (need both teams with players).")

    img1 = generate_team_lineup_image(team1, team_number=1)
    img2 = generate_team_lineup_image(team2, team_number=2)

    return img1, img2