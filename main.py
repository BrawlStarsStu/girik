import asyncio
import uuid
import textwrap
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultCachedPhoto,
    InlineQueryResultArticle,
    InputTextMessageContent,
    BufferedInputFile
)

# === НАСТРОЙКИ ===
TOKEN = '8303120709:AAF7jtWDG3wmEMOIUOfKOtFlSrWr82b1BIc'
CACHE_CHAT_ID = -1003747602791 # Вставь свой ID канала
MAX_LENGTH = 110

# Словарь со всеми шаблонами
TEMPLATES = {
    "statham": {
        "file": "statham.jpg",
        "title": "Джейсон Стетхем",
        "text_pos": (20, 50), 
        "wrap_width": 20,
        "align": "left",
        "fill_color": "white",
        "shadow_color": "black"
    },
    "churchill": {
        "file": "ch.jpg",
        "title": "Уинстон Черчилль",
        "text_pos": (20, 40), 
        "wrap_width": 20,
        "align": "left",
        "fill_color": "white",
        "shadow_color": "black"
    }, # <--- ВОТ ТУТ БЫЛА ПРОПУЩЕНА СКОБКА И ЗАПЯТАЯ

    # НОВЫЙ ШАБЛОН: КОНФУЦИЙ (ТЕКСТ СПРАВА)
    "konfuciy": {
        "file": "konf.jpg",
        "title": "Конфуций",
        # Первое число (X) делаем большим, чтобы текст ушел вправо. 
        # Если картинка шириной 800px, то 450 — это чуть правее центра.
        "text_pos": (350, 100), 
        "wrap_width": 20,
        # Выравниваем сами строки по правому краю
        "align": "right", 
        "fill_color": "white",
        "shadow_color": "black"
    },
    "zhirik": {
        "file": "zhirik.jpg", 
        "title": "Владимир Жириновский",
        "wrap_width": 20,
        "align": "center", # Автоцентрирование
        "fill_color": "white",
        "shadow_color": "black"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

def generate_image(text: str, template_key: str) -> bytes:
    tpl = TEMPLATES[template_key]
    
    try:
        img = Image.open(tpl["file"]).convert("RGB")
    except FileNotFoundError:
        print(f"Ошибка: Файл {tpl['file']} не найден! Создаю заглушку.")
        img = Image.new("RGB", (800, 600), color=(50, 50, 50))

    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", size=36)
    except IOError:
        font = ImageFont.load_default()

    wrap_width = tpl.get("wrap_width", 30)
    wrapped_text = "\n".join(textwrap.wrap(text, width=wrap_width))
    
    align_type = tpl.get("align", "center")
    
    if "text_pos" in tpl:
        x, y = tpl["text_pos"]
    else:
        bbox = draw.textbbox((0, 0), wrapped_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img.width - text_w) / 2
        y = (img.height - text_h) / 2

    shadow_color = tpl.get("shadow_color")
    fill_color = tpl.get("fill_color", "white")

    if shadow_color:
        draw.multiline_text((x + 2, y + 2), wrapped_text, font=font, fill=shadow_color, align=align_type)
    
    draw.multiline_text((x, y), wrapped_text, font=font, fill=fill_color, align=align_type)

    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf.getvalue()

@dp.inline_query()
async def inline_handler(query: InlineQuery):
    text = query.query.strip()
    
    if not text:
        return
        
    # === НОВАЯ ЛОГИКА: ОЖИДАНИЕ ТОЧКИ ===
    if not text.endswith('.'):
        # Если точки в конце нет, выводим подсказку и НЕ генерируем картинки
        hint_msg = InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="⏳ Жду точку в конце...",
            description="Напиши текст и поставь точку (.), чтобы сгенерировать цитаты. На фото точки не будет!",
            input_message_content=InputTextMessageContent(
                message_text="Чтобы бот создал цитату, используй инлайн-режим и поставь точку в конце текста."
            )
        )
        await query.answer([hint_msg], cache_time=1, is_personal=True)
        return

    # Если точка есть, удаляем её (и возможные пробелы перед ней)
    clean_text = text.rstrip('.').strip()
    
    # Если после удаления точки текст оказался пустым (пользователь ввел просто "."), ничего не делаем
    if not clean_text:
        return

    # Проверка длины уже ОЧИЩЕННОГО текста
    if len(clean_text) > MAX_LENGTH:
        error_msg = InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="❌ Ошибка: Слишком много букв!",
            description=f"Текст: {len(clean_text)} симв. Лимит: {MAX_LENGTH}.",
            input_message_content=InputTextMessageContent(
                message_text=f"Цитата не влезла! Максимальная длина — {MAX_LENGTH} символов."
            )
        )
        await query.answer([error_msg], cache_time=1, is_personal=True)
        return

    results = []
    
    for key, tpl in TEMPLATES.items():
        # Передаем очищенный от точки текст (clean_text) в генератор
        img_bytes = await asyncio.to_thread(generate_image, clean_text, key)
        
        try:
            msg = await bot.send_photo(
                chat_id=CACHE_CHAT_ID,
                photo=BufferedInputFile(img_bytes, filename=f"{key}_{uuid.uuid4().hex[:8]}.jpg"),
                caption=f"Кэш: {tpl['title']}"
            )
            file_id = msg.photo[-1].file_id
            
            results.append(
                InlineQueryResultCachedPhoto(
                    id=str(uuid.uuid4()),
                    photo_file_id=file_id,
                    title=tpl["title"],
                    description=clean_text[:50] + "..."
                )
            )
        except Exception as e:
            print(f"⚠️ Ошибка кэша для {key}: {e}")

    if results:
        await query.answer(results, cache_time=1, is_personal=True)

async def main():
    print("=== Бот Генератор Цитат запущен ===")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")