"""HTTP client to core service: send CSV, get image URLs (async)."""
import io
import os
import httpx
from PIL import Image

CORE_URL = os.environ.get("CORE_URL", "http://localhost:8000")

# Макс. ширина для отправки в Telegram — меньше файл, быстрее загрузка и нет таймаутов
TELEGRAM_MAX_WIDTH = 1200
TELEGRAM_JPEG_QUALITY = 88


async def generate_lineups(csv_body: str) -> dict:
    """POST CSV to core, return JSON with team image URLs."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{CORE_URL.rstrip('/')}/api/lineups/generate",
            content=csv_body.encode("utf-8"),
            headers={"Content-Type": "text/csv; charset=utf-8"},
        )
        r.raise_for_status()
        return r.json()


async def get_image_bytes(url: str) -> bytes:
    """Fetch image from core by path (e.g. /static/generated/team1_lineup.png)."""
    full_url = f"{CORE_URL.rstrip('/')}{url}" if url.startswith("/") else url
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(full_url)
        r.raise_for_status()
        return r.content


def resize_for_telegram(png_bytes: bytes) -> bytes:
    """
    Ужимает PNG в JPEG с ограничением по ширине.
    Сильно уменьшает размер файла — загрузка в Telegram не упирается в таймаут.
    """
    img = Image.open(io.BytesIO(png_bytes))
    if img.mode == "RGBA":
        back = Image.new("RGB", img.size, (255, 255, 255))
        back.paste(img, mask=img.split()[3])
        img = back
    else:
        img = img.convert("RGB")
    w, h = img.size
    if w > TELEGRAM_MAX_WIDTH:
        ratio = TELEGRAM_MAX_WIDTH / w
        new_size = (TELEGRAM_MAX_WIDTH, int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=TELEGRAM_JPEG_QUALITY, optimize=True)
    return buf.getvalue()
