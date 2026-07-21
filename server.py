import hashlib
import hmac
import json
import logging
import os
import time
from urllib.parse import parse_qsl

import aiohttp
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse

logger = logging.getLogger("lager")
logging.basicConfig(level=logging.INFO)

# ===== НАСТРОЙКА =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER")

# тот же Apps Script, что уже проверяет участников по таблице
SHEET_CHECK_URL = "https://script.google.com/macros/s/AKfycbzfxfN7f_-L9J1qmh2uQjyQlwksBaLYSlwSf5dE9DK7DmPUZO7OHEJ0Flk3rJO6vXFv/exec"

# ===== КАРТА ФАЙЛОВ =====
# key должен совпадать с "fileKey" в мини-эппе
FILES = {
    "guide_pdf": {
        "name": "Гайд по Claude.pdf",
        "mime": "application/pdf",
        "public_key": "https://disk.yandex.ru/i/u_T4yCHy9nWcpg",
    },
    "read_before_docx": {
        "name": "Прочти это перед стартом!.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/k60e9Lpzob4TNg",
    },
    "l1_skills_lib_pdf": {
        "name": "Библиотеки навыков для Claude.pdf",
        "mime": "application/pdf",
        "public_key": "https://disk.yandex.ru/i/D-EuZMY1RGaHKg",
    },
    "l1_workshop1_mp4": {
        "name": "Воркшоп - ч.1 база работы с Claude.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/xlxtOfPRF7QSQg",
    },
    "l1_workshop2_mp4": {
        "name": "Воркшоп - ч.2 - Claude code , Claude design.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/qHJJUce3x5Lsmg",
    },
    "l1_payments_pdf": {
        "name": "Как оплатить нейросети и симкарты для работы-2.pdf",
        "mime": "application/pdf",
        "public_key": "https://disk.yandex.ru/i/f_iDKjz28woqXw",
    },
    "l1_top10_skills_pdf": {
        "name": "Лучшие Skills для Claude - топ 10.pdf",
        "mime": "application/pdf",
        "public_key": "https://disk.yandex.ru/i/3E0mFb0GkBxyfw",
    },
    "l2_skills_table_xlsx": {
        "name": "Skills Claude маркетплейсы - курс.xlsx",
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "public_key": "https://disk.yandex.ru/i/fuX5Pn1-lxCcYQ",
    },
    "l2_skills_lib_pdf": {
        "name": "Библиотеки навыков для Claude.pdf",
        "mime": "application/pdf",
        "public_key": "https://disk.yandex.ru/i/cDq06Lwx19Zrwg",
    },
    "l2_instructions_pdf": {
        "name": "Инструкция по работе со Skills.pdf",
        "mime": "application/pdf",
        "public_key": "https://disk.yandex.ru/i/dj0RXXqgBn78nw",
    },
    "l2_homework_docx": {
        "name": "ДЗ.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/u-Q6KgCGZc9tfw",
    },
    "l2_skills_lesson_mp4": {
        "name": "Урок Skills в Claude.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/SF053kyeW_czWQ",
    },
    "org_meeting_1_mp4": {
        "name": "Организационная встреча.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/W3KlZngx4Hdkbg",
    },
    "l3_claude_code_intro_mp4": {
        "name": "Знакомство с Claude Code.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/5VmFAr9SwR07pg",
    },
    "l3_useful_links_pdf": {
        "name": "Полезные ссылки для работы с Claude Code.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/GBtg8z_sNZPqqA",
    },
    "l4_ai_agents_mp4": {
        "name": "ИИ агенты в Claude Code.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/fv6ftp0l6PR0og",
    },
    "l4_prompt_reviews_docx": {
        "name": "Промпт - ИИ-агент для сбора отзывов и вопросов.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/VuCrHHHR1ip-Kg",
    },
    "l4_prompt_supply_docx": {
        "name": "Промпт - ИИ-агент по поставкам.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/Owpa4TsMjZEGZg",
    },
    "l4_services_docx": {
        "name": "Сервисы, которые нужны для урока.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/gX68bUFnm-g6UQ",
    },
    "l4_prompt_reviews_wb_docx": {
        "name": "Промпт - ИИ-агент по отзывам для WB.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/U8UIGcOUH-ZQfg",
    },
    "l5_stock_supply_agent_mp4": {
        "name": "ИИ-агент по остаткам и поставкам.mp4",
        "mime": "video/mp4",
        "public_key": "https://disk.yandex.ru/i/6ylTZWMrtu-70g",
    },
    "l5_prompt_ozon_docx": {
        "name": "Промпт - ИИ-агент по остаткам и поставкам Ozon.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/DmvCYg5RQAejbg",
    },
    "l5_prompt_wb_docx": {
        "name": "Промпт - ИИ-агент по поставкам WB.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/C_n_QUnpC4mFuA",
    },
    "l5_links_docx": {
        "name": "Ссылки с урока.docx",
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "public_key": "https://disk.yandex.ru/i/tY0ttanVZKu40g",
    },
}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def validate_init_data(init_data: str):
    """Проверяет подпись initData от Telegram по официальному алгоритму.
    Возвращает словарь пользователя, если подпись верна, иначе None - подделать нельзя,
    так как подпись строится с использованием токена бота, которого никто кроме нас не знает."""
    logger.info("initData raw length=%s preview=%r", len(init_data or ""), (init_data or "")[:80])

    if not init_data:
        logger.warning("REJECT: init_data is empty")
        return None

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError as e:
        logger.warning("REJECT: parse_qsl failed: %s", e)
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        logger.warning("REJECT: no hash field in parsed data, keys=%s", list(parsed.keys()))
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.warning(
            "REJECT: hash mismatch. computed=%s received=%s bot_token_len=%s",
            computed_hash, received_hash, len(BOT_TOKEN or ""),
        )
        return None

    user_json = parsed.get("user")
    if not user_json:
        logger.warning("REJECT: no user field in parsed data")
        return None

    logger.info("ACCEPT: init data valid for user=%s", user_json)
    return json.loads(user_json)


async def check_participant(nick: str) -> bool:
    nick = nick.strip().lower().lstrip("@")
    if not nick:
        return False
    async with aiohttp.ClientSession() as session:
        async with session.get(SHEET_CHECK_URL, params={"nick": nick}) as resp:
            data = await resp.json(content_type=None)
            return bool(data.get("valid"))


def auth_username(x_telegram_init_data: str, init_data: str) -> str:
    raw = x_telegram_init_data or init_data or ""
    user = validate_init_data(raw)
    if not user:
        raise HTTPException(status_code=403, detail="Не удалось подтвердить, кто ты в Telegram")
    username = user.get("username")
    if not username:
        raise HTTPException(
            status_code=403,
            detail="У тебя не задан юзернейм в Telegram - укажи @ник в настройках Telegram",
        )
    return username


@app.get("/api/check-access")
async def check_access(
    key: str = Query(...),
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
    init_data: str = Query(None),
):
    username = auth_username(x_telegram_init_data, init_data)
    if not await check_participant(username):
        raise HTTPException(status_code=403, detail="Не нашли тебя в списке участников лагеря")
    if key not in FILES:
        raise HTTPException(status_code=404, detail="Такой файл не найден")
    return {"ok": True}
async def mark_viewed(
    key: str = Query(...),
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
    init_data: str = Query(None),
):
    username = auth_username(x_telegram_init_data, init_data)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            SHEET_CHECK_URL, params={"action": "mark_viewed", "nick": username, "key": key}
        ) as resp:
            await resp.json(content_type=None)
    return {"ok": True}


@app.get("/api/progress")
async def get_progress(
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
    init_data: str = Query(None),
):
    username = auth_username(x_telegram_init_data, init_data)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            SHEET_CHECK_URL, params={"action": "get_progress", "nick": username}
        ) as resp:
            data = await resp.json(content_type=None)
    return {"viewed": data.get("viewed", []), "total": len(FILES)}


async def get_direct_link(public_key: str) -> str:
    api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params={"public_key": public_key}) as resp:
            data = await resp.json()
            return data["href"]


_link_cache = {}


async def cached_direct_link(public_key: str) -> str:
    """Прямые ссылки Яндекса живут ограниченное время - кэшируем ненадолго,
    чтобы не дёргать Яндекс заново при каждом открытии одного и того же файла подряд."""
    now = time.time()
    cached = _link_cache.get(public_key)
    if cached and cached[1] > now:
        return cached[0]
    href = await get_direct_link(public_key)
    _link_cache[public_key] = (href, now + 600)  # 10 минут
    return href


@app.get("/api/file")
async def get_file(
    key: str = Query(...),
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
    init_data: str = Query(None),
    range: str = Header(None),
):
    raw_init_data = x_telegram_init_data or init_data or ""
    user = validate_init_data(raw_init_data)
    if not user:
        raise HTTPException(status_code=403, detail="Не удалось подтвердить, кто ты в Telegram")

    username = user.get("username")
    if not username:
        raise HTTPException(
            status_code=403,
            detail="У тебя не задан юзернейм в Telegram - укажи @ник в настройках Telegram",
        )

    if not await check_participant(username):
        raise HTTPException(status_code=403, detail="Не нашли тебя в списке участников лагеря")

    file_info = FILES.get(key)
    if not file_info:
        raise HTTPException(status_code=404, detail="Такой файл не найден")

    href = await cached_direct_link(file_info["public_key"])

    upstream_headers = {}
    if range:
        upstream_headers["Range"] = range

    session = aiohttp.ClientSession()
    resp = await session.get(href, headers=upstream_headers)

    response_headers = {"Accept-Ranges": "bytes"}
    for h in ("Content-Range", "Content-Length"):
        if h in resp.headers:
            response_headers[h] = resp.headers[h]
    status_code = 206 if resp.status == 206 else 200

    async def stream():
        try:
            async for chunk in resp.content.iter_chunked(65536):
                yield chunk
        finally:
            resp.release()
            await session.close()

    return StreamingResponse(
        stream(), status_code=status_code, media_type=file_info["mime"], headers=response_headers
    )


@app.get("/api/open")
async def open_on_disk(
    key: str = Query(...),
    init_data: str = Query(..., alias="init_data"),
):
    # тут initData приходит параметром, а не заголовком - потому что это обычный переход
    # по ссылке (кнопка "Открыть на Диске"), а не fetch() из скрипта
    user = validate_init_data(init_data)
    if not user:
        raise HTTPException(status_code=403, detail="Не удалось подтвердить, кто ты в Telegram")

    username = user.get("username")
    if not username or not await check_participant(username):
        raise HTTPException(status_code=403, detail="Не нашли тебя в списке участников лагеря")

    file_info = FILES.get(key)
    if not file_info:
        raise HTTPException(status_code=404, detail="Такой файл не найден")

    return RedirectResponse(url=file_info["public_key"])


@app.get("/")
async def health():
    return {"status": "ok"}
