import asyncio
import sqlite3
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

# --- KONFIGURATSIYA ---
TOKEN = "8698552076:AAEngUlN8nE4nQVyEa4v4Q6WzsvJGWV5nBI"
ADMIN_ID = 5809175944
ADMIN_PASSWORD = "070820091"
BOT_USERNAME = "@Kinolar_multfilmbot"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- WEB SERVER (RENDER UCHUN) ---
async def handle(request):
    return web.Response(text="Bot is active!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('kino_database.db')
    conn.execute('CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT, name TEXT, type TEXT)')
    conn.commit()
    conn.close()

init_db()

class BotStates(StatesGroup):
    waiting_pw = State()
    is_admin = State()
    choosing_type = State()
    naming = State()
    coding = State()
    uploading = State()

# --- TUGMALAR ---
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati")
    kb.button(text="🧸 Multfilmlar ro'yxati")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def admin_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="➕ Yangi qo'shish"), kb.button(text="🗑 O'chirish")
    kb.button(text="🏠 Bosh sahifa")
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(f"🌟 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\nKino kodini yuboring:", reply_markup=main_menu())

@dp.message(Command("admin"))
async def admin_auth(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔑 <b>Parol kiriting:</b>")
        await state.set_state(BotStates.waiting_pw)

@dp.message(BotStates.waiting_pw)
async def check_pw(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await message.delete()
        await message.answer("🔓 Xush kelibsiz!", reply_markup=admin_menu())
        await state.set_state(BotStates.is_admin)

@dp.message(F.text == "🎬 Kinolar ro'yxati")
async def list_movies(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    data = conn.execute('SELECT name, code FROM movies WHERE type = "Kino"').fetchall()
    conn.close()
    txt = "🎬 <b>Kinolar:</b>\n\n" + "\n".join([f"💎 {n} — <code>{c}</code>" for n, c in data]) if data else "Bo'sh."
    await message.answer(txt)

@dp.message(F.text == "🧸 Multfilmlar ro'yxati")
async def list_cartoons(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    data = conn.execute('SELECT name, code FROM movies WHERE type = "Multfilm"').fetchall()
    conn.close()
    txt = "🧸 <b>Multfilmlar:</b>\n\n" + "\n".join([f"✨ {n} — <code>{c}</code>" for n, c in data]) if data else "Bo'sh."
    await message.answer(txt)

@dp.message(F.text, lambda m: m.text.isdigit())
async def search(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM movies WHERE code = ?', (message.text,)).fetchone()
    conn.close()
    if res:
        cap = f"🎬 <b>Nomi:</b> {res[1]}\n🍿 Yoqimli tomosha!\n🤖 {BOT_USERNAME}"
        await message.answer_video(video=res[0], caption=cap) if not str(res[0]).startswith("http") else await message.answer(f"{cap}\n🔗 {res[0]}")
    else:
        await message.answer("🚫 Topilmadi.")

@dp.message(F.text == "➕ Yangi qo'shish", BotStates.is_admin)
async def add_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Kino"), kb.button(text="Multfilm")
    await message.answer("📂 Turini tanlang:", reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(BotStates.choosing_type)

@dp.message(BotStates.choosing_type)
async def add_type(message: types.Message, state: FSMContext):
    await state.update_data(m_type=message.text)
    await message.answer(f"📝 {message.text} nomini yozing:")
    await state.set_state(BotStates.naming)

@dp.message(BotStates.naming)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(m_name=message.text)
    await message.answer("🔢 Kodni yozing:")
    await state.set_state(BotStates.coding)

@dp.message(BotStates.coding)
async def add_code(message: types.Message, state: FSMContext):
    await state.update_data(m_code=message.text)
    await message.answer("📥 Videoni yoki linkni yuboring:")
    await state.set_state(BotStates.uploading)

@dp.message(BotStates.uploading)
async def save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    f_id = message.video.file_id if message.video else message.text
    conn = sqlite3.connect('kino_database.db')
    try:
        conn.execute('INSERT INTO movies VALUES (?, ?, ?, ?)', (data['m_code'], f_id, data['m_name'], data['m_type']))
        conn.commit()
        await message.answer("✅ Saqlandi!", reply_markup=admin_menu())
    except: await message.answer("❌ Xato!")
    conn.close()
    await state.set_state(BotStates.is_admin)

@dp.message(F.text == "🏠 Bosh sahifa")
async def home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh sahifa", reply_markup=main_menu())

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())