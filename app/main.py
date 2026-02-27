import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .lineup_service import (
    generate_both_lineups,
    STATIC_DIR,
)


app = FastAPI(title="Football Mini App API")


# Allow local dev and Telegram mini app origins (expand as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Static files (generated images)
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/lineups")
async def get_lineups():
    """
    Главная ручка:
    - Если составы и все картинки корректно заданы — генерирует 2 изображения составов и отдаёт их URL.
    - Если что-то не так — возвращает статус и сообщение.
    """
    try:
        img1_path, img2_path = generate_both_lineups()
    except FileNotFoundError as e:
        # Отсутствуют нужные изображения: поле, карта фона или фото игрока
        return JSONResponse(
            status_code=200,
            content={
                "status": "assets_missing",
                "message": str(e),
            },
        )
    except ValueError as e:
        # Например, не хватает игроков, нет двух команд и т.п.
        return JSONResponse(
            status_code=200,
            content={
                "status": "no_lineups",
                "message": "Составы не сформированы",
                "details": str(e),
            },
        )
    except Exception as e:
        # Непредвиденная ошибка
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Внутренняя ошибка сервера при формировании составов",
                "details": str(e),
            },
        )

    # Преобразуем абсолютные пути в URL под /static
    def to_url(path: str) -> str:
        rel = os.path.relpath(path, STATIC_DIR).replace(os.sep, "/")
        return f"/static/{rel}"

    return {
        "status": "ok",
        "teams": [
            {"team": 1, "image_url": to_url(img1_path)},
            {"team": 2, "image_url": to_url(img2_path)},
        ],
    }

