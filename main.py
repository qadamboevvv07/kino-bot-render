import asyncio
import sqlite3
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiohttp import web

# --- KONFIGURATSIYA ---
TOKEN = "8698552076:AAEngUlN8nE4nQVyEa4v4Q6WzsvJGWV5nBI"
ADMIN_ID = 5809175944
ADMIN_PASSWORD = "070820091"
CHANNEL_ID = "@Kinolar_va_multfilmlar_olamiN1"
BOT_USERNAME = "@Kinolar_multfilmbot"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- WEB SERVER (KEEP ALIVE) ---
async def handle(request): return web.Response(text="Bot is running!")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('kino_data.db')
    conn.execute('CREATE TABLE IF NOT EXISTS content (code TEXT PRIMARY KEY, file_id TEXT, type TEXT, name TEXT)')
    conn.commit()
    conn.close()

init_db()

class States(StatesGroup):
    auth = State()
    admin_menu = State()
    choosing_type = State()
    uploading = State()

# --- KEYBOARDS ---
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati")
    return kb.as_markup(resize_keyboard=True)

def sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Kanalga a'zo bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
    kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
    return kb.as_markup()

def admin_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📥 Pachka qo'shish"), kb.button(text="🗑 O'chirish"), kb.button(text="🏠 Bosh sahifa")
    return kb.as_markup(resize_keyboard=True)

# --- CHECK SUB ---
async def is_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- START ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer(f"👋 Assalomu alaykum, {message.from_user.full_name}!\n\n🤖 Botimizdan foydalanish uchun rasmiy kanalimizga a'zo bo'ling.", reply_markup=sub_kb())
    await message.answer("😇 Xush kelibsiz! Men sizga eng sara kinolarni topishda yordam beraman.\n\n👇 Menyunidan birini tanlang yoki kino kodini yuboring:", reply_markup=main_kb())

@dp.callback_query(F.data == "check_sub")
async def check(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Rahmat! Endi botdan to'liq foydalanishingiz mumkin.", reply_markup=main_kb())
    else:
        await call.answer("❌ Hali a'zo bo'lmadingiz!", show_alert=True)

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔑 Parolni kiriting:")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def auth(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await message.answer("🔓 Xush kelibsiz, xo'jayin! Nima qilamiz?", reply_markup=admin_kb())
        await state.set_state(States.admin_menu)
    else:
        await message.answer("🚫 Parol noto'g'ri!")

@dp.message(F.text == "📥 Pachka qo'shish", States.admin_menu)
async def bulk_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Kino"), kb.button(text="Multfilm")
    await message.answer("📁 Turini tanlang:", reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(States.choosing_type)

@dp.message(States.choosing_type)
async def bulk_type(message: types.Message, state: FSMContext):
    await state.update_data(t=message.text)
    await message.answer(f"🚀 Rejim: <b>{message.text}</b>\n\nVideolarni yuboring. Izohiga <b>'kod | nomi'</b> deb yozing.\nMasalan: <code>7 | Qashqirlar makoni</code>")
    await state.set_state(States.uploading)

@dp.message(F.video, States.uploading)
async def process_bulk(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        parts = message.caption.split('|')
        code = parts[0].strip()
        name = parts[1].strip()
        conn = sqlite3.connect('kino_data.db')
        conn.execute('INSERT OR REPLACE INTO content VALUES (?, ?, ?, ?)', (code, message.video.file_id, data['t'], name))
        conn.commit()
        conn.close()
        await message.reply(f"✅ Saqlandi: {code} - {name}")
    except:
        await message.reply("⚠️ Xato! Izohni <b>kod | nomi</b> ko'rinishida yozing.")

@dp.message(F.text == "🗑 O'chirish", States.admin_menu)
async def delete_start(message: types.Message):
    await message.answer("O'chirmoqchi bo'lgan kino kodini yuboring:")

@dp.message(States.admin_menu, F.text.isdigit())
async def delete_process(message: types.Message):
    conn = sqlite3.connect('kino_data.db')
    conn.execute('DELETE FROM content WHERE code = ?', (message.text,))
    conn.commit()
    conn.close()
    await message.answer(f"🗑 Kod {message.text} o'chirildi.")

# --- SEARCH & LIST ---
@dp.message(F.text == "🎬 Kinolar ro'yxati")
async def list_kinos(message: types.Message):
    conn = sqlite3.connect('kino_data.db')
    res = conn.execute('SELECT code, name FROM content WHERE type = "Kino"').fetchall()
    conn.close()
    text = "🎬 <b>Kinolar ro'yxati:</b>\n\n" + "\n".join([f"{r[0]}. {r[1]}" for r in res]) if res else "Hozircha kinolar yo'q."
    await message.answer(text)

@dp.message(F.text == "🧸 Multfilmlar ro'yxati")
async def list_mults(message: types.Message):
    conn = sqlite3.connect('kino_data.db')
    res = conn.execute('SELECT code, name FROM content WHERE type = "Multfilm"').fetchall()
    conn.close()
    text = "🧸 <b>Multfilmlar ro'yxati:</b>\n\n" + "\n".join([f"{r[0]}. {r[1]}" for r in res]) if res else "Hozircha multfilmlar yo'q."
    await message.answer(text)

@dp.message(F.text.isdigit())
async def search(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("❌ Avval kanalga a'zo bo'ling!", reply_markup=sub_kb())
    
    conn = sqlite3.connect('kino_data.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE code = ?', (message.text,)).fetchone()
    conn.close()
    
    if res:
        await message.answer_sticker("CAACAgIAAxkBAAEL6") # Namuna stiker
        await message.answer_video(video=res[0], caption=f"🎬 <b>Nomi:</b> {res[1]}\n🔢 <b>Kodi:</b> {message.text}\n\n🍿 Yoqimli tomosha tilaymiz!\n✨ {BOT_USERNAME}")
    else:
        await message.answer("😔 Afsuski, bu kod bo'yicha hech narsa topilmadi.")

@dp.message(F.text == "🏠 Bosh sahifa")
async def home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh sahifa", reply_markup=main_kb())

async def main():
    await start_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
