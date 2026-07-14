import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

import aiohttp
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    user_json = parsed.get("user")
    if not user_json:
        return None
    return json.loads(user_json)


async def check_participant(nick: str) -> bool:
    nick = nick.strip().lower().lstrip("@")
    if not nick:
        return False
    async with aiohttp.ClientSession() as session:
        async with session.get(SHEET_CHECK_URL, params={"nick": nick}) as resp:
            data = await resp.json(content_type=None)
            return bool(data.get("valid"))


async def get_direct_link(public_key: str) -> str:
    api_url = "https://cloud-api.yandex.net/v1/disk/public/resources/download"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params={"public_key": public_key}) as resp:
            data = await resp.json()
            return data["href"]


@app.get("/api/file")
async def get_file(
    key: str = Query(...),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    user = validate_init_data(x_telegram_init_data)
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

    href = await get_direct_link(file_info["public_key"])

    session = aiohttp.ClientSession()
    resp = await session.get(href)

    async def stream():
        try:
            async for chunk in resp.content.iter_chunked(65536):
                yield chunk
        finally:
            resp.release()
            await session.close()

    return StreamingResponse(stream(), media_type=file_info["mime"])


@app.get("/")
async def health():
    return {"status": "ok"}
