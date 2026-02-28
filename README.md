# Футбольное мини‑приложение (FastAPI)

Локальный сервис на FastAPI, который:

- **читает составы из CSV**;
- **генерирует карточки игроков** на основе рейтинга (bronze / silver / gold);
- **размещает игроков на фоне футбольного поля** для двух команд;
- **отдаёт одну ручку** `GET /lineups`:
  - если составы заданы — возвращает ссылки на 2 изображения составов;
  - если нет — возвращает статус, что составы не сформированы.

## Структура проекта

```text
football_mini_app/
  app/
    main.py
    lineup_service.py
  data/
    lineups.csv          # ты заполняешь вручную
  assets/
    field.png            # фон футбольного поля (одно фото для всех случаев)
    cards/
      bronze.png
      silver.png
      gold.png
    players/
      name_family.png    # фото игроков
  static/
    generated/
      team1_lineup.png   # авто‑генерируется
      team2_lineup.png   # авто‑генерируется
```

Все папки будут созданы автоматически кодом при первом запуске, но файлы `field.png`, `bronze.png`, `silver.png`, `gold.png` и фото игроков тебе нужно положить самостоятельно.

## Формат CSV `data/lineups.csv`

Файл в кодировке UTF‑8 с заголовком, пример:

```csv
team,name,surname,position,rating,card_name,photo_filename
1,Иван,Иванов,врт,86,,ivan_ivanov.png
1,Пётр,Петров,защ,78,,petr_petrov.png
1,Сергей,Сидоров,фрв,90,,sergey_sidorov.png
2,Антон,Антонов,врт,82,,anton_antonov.png
2,Максим,Максимов,защ,88,,maksim_maksimov.png
2,Денис,Денисов,фрв,79,,denis_denisov.png
```

- **team**: номер команды (`1` или `2`).
- **name**: имя (будет показано на карточке).
- **surname**: фамилия (можешь использовать только для себя).
- **position**: `врт`, `защ` или `фрв`.
- **rating**: общий рейтинг (60–99), **используется** для выбора типа карточки и текста рейтинга.
- **card_name**: необязательно, можно оставить пустым — фон выбирается автоматически:
  - `< 80` → `bronze.png`
  - `80–85` → `silver.png`
  - `> 85` → `gold.png`
- **photo_filename**: имя файла фото игрока в папке `assets/players` (например, `ivan_ivanov.png`).

Количество игроков в команде может варьироваться от 7 до 11. Сервис автоматически расставляет:

- `врт` — в воротах (сзади, по центру);
- `защ` — в линию обороны (чуть впереди вратаря);
- `фрв` — в атаке (ближе к чужим воротам).

Если игроков больше — они равномерно распределяются по горизонтали на своей линии.

## Логика выбора карточки

- **bronze** (`bronze.png`) — рейтинг `< 80`;
- **silver** (`silver.png`) — рейтинг `80–85` включительно;
- **gold** (`gold.png`) — рейтинг `> 85`.

На карточке:

- в **левом верхнем углу** — рейтинг;
- в **центре** — фото игрока (по центру, подогнанное по размеру);
- под фото — **имя** (без фамилии).

## Запуск

1. Установить зависимости:

```bash
cd football_mini_app
python -m venv venv
source venv/bin/activate  # или .venv/Scripts/activate на Windows
pip install -r requirements.txt
```

2. Положить файлы:

- `assets/field.png` — один фон футбольного поля;
- `assets/cards/bronze.png`, `assets/silver.png`, `assets/gold.png`;
- `assets/players/*.png` — фото игроков: `name_family.png`;
- `data/lineups.csv` — по формату выше.

3. Запустить сервер:

```bash
uvicorn app.main:app --reload
```

4. Открыть в браузере:

- `http://127.0.0.1:8000/docs` — Swagger UI;
- `GET /lineups` — основная ручка.

## Ответ ручки `/lineups`

- Если составы **не заданы** (нет файла `data/lineups.csv` или в нём нет двух команд) — вернётся:

```json
{
  "status": "no_lineups",
  "message": "Составы не сформированы"
}
```

- Если всё ок — после генерации картинок:

```json
{
  "status": "ok",
  "teams": [
    {
      "team": 1,
      "image_url": "/static/generated/team1_lineup.png"
    },
    {
      "team": 2,
      "image_url": "/static/generated/team2_lineup.png"
    }
  ]
}
```

Эти URL можно будет использовать в Telegram mini app (или просто открыть в браузере) как готовые изображения составов.

---

## Telegram-бот (MVP)

Отдельный микросервис: в боте выбираешь, кто в игре (множественный выбор кнопками), затем по очереди назначаешь каждого в красную или синюю команду; итоговый состав уходит в core, оттуда приходят два фото составов.

### Как устроено

1. **Core** — по-прежнему генерирует картинки. Добавлена ручка **`POST /api/lineups/generate`**: в теле запроса CSV в формате `team,name,surname,position,rating,card_name,photo_filename`; в ответе — JSON с URL двух изображений.
2. **Бот** (`bot/`) — хранит базу игроков в `bot/data/players.csv` (поля: name, surname, position, rating, card_name, photo_filename, mvp, games, goals, wins). По команде `/start` показывает список игроков **кнопками с множественным выбором**: нажимаешь — ставится галочка «в игре», ещё раз — снимается. Кнопка «Готово» переводит к шагу «Распределение»: по одному игроку и две кнопки «Красная (1)» / «Синяя (2)». После распределения всех бот отправляет CSV в core и присылает в чат два фото составов.

### Запуск через Docker Compose

Два сервиса: **core** (FastAPI) и **bot** (Telegram).

1. Создай бота через [@BotFather](https://t.me/BotFather), скопируй токен.
2. В корне проекта создай папки и ассеты, если ещё нет: `data/`, `assets/field.png`, `assets/cards/`, `assets/players/` (фото по именам из `bot/data/players.csv`).
3. Запуск:

```bash
export BOT_TOKEN=твой_токен
docker compose up --build
```

- Core: `http://localhost:8000`
- Бот подключается к core по имени сервиса `http://core:8000` (переменная `CORE_URL` в `docker-compose.yml`).

4. В Telegram отправь боту `/start` и отметь игроков кнопками, затем «Готово» и распредели по командам.

### Локальный запуск бота (без Docker)

```bash
# Терминал 1 — core
uvicorn app.main:app --reload

# Терминал 2 — бот (из корня проекта, чтобы пакет bot был в PYTHONPATH)
pip install -r bot/requirements.txt
export BOT_TOKEN=...
export CORE_URL=http://localhost:8000
python -m bot.main
```

Список игроков для выбора и распределения лежит в `bot/data/players.csv`; имена файлов фото должны совпадать с теми, что лежат в `assets/players/` у core.

