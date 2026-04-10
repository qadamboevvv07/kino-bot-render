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

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('kino_database.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS content 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, type TEXT, name TEXT)''')
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
    kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
    kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
    return kb.as_markup()

def admin_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📥 Avto-qo'shish (Pachka)"), kb.button(text="🗑 O'chirish"), kb.button(text="🏠 Bosh sahifa")
    return kb.as_markup(resize_keyboard=True)

# --- WEB SERVER (KEEP ALIVE) ---
async def handle(request): return web.Response(text="Bot Active")
async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

# --- FUNCTIONS ---
async def is_subscribed(user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("😊 Assalomu alaykum! Bizning xizmatlardan foydalanish uchun kanalimizga obuna bo'lishingizni iltimos qilamiz. Bu bizni qo'llab-quvvatlashning eng yaxshi yo'lidir! ✨", reply_markup=sub_kb())
    await message.answer("🌟 Xush kelibsiz! Men sizga eng sara kinolarni topib beraman. Kino kodini yuboring:", reply_markup=main_kb())

@dp.callback_query(F.data == "check_sub")
async def check(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Endi bemalol foydalanishingiz mumkin.", reply_markup=main_kb())
    else:
        await call.answer("😔 Kechirasiz, hali a'zo bo'lmadingiz. Iltimos, obuna bo'ling!", show_alert=True)

# --- ADMIN LOGIC ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Iltimos, admin parolini kiriting:")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def auth_process(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await message.answer("⚡️ Xush kelibsiz! Nima qilamiz?", reply_markup=admin_kb())
        await state.set_state(States.admin_menu)
    else: await message.answer("❌ Parol xato!")

@dp.message(F.text == "📥 Avto-qo'shish (Pachka)", States.admin_menu)
async def bulk_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Kino"), kb.button(text="Multfilm")
    await message.answer("📂 Turini tanlang:", reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(States.choosing_type)

@dp.message(States.choosing_type)
async def set_type(message: types.Message, state: FSMContext):
    await state.update_data(t=message.text)
    await message.answer(f"✅ Rejim: <b>{message.text}</b>\n🚀 Videolarni yuboravering! Bot kodni avtomatik beradi va nomini izohdan oladi.")
    await state.set_state(States.uploading)

@dp.message(F.video, States.uploading)
async def auto_upload(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = message.caption if message.caption else "Nomsiz kino"
    conn = sqlite3.connect('kino_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO content (file_id, type, name) VALUES (?, ?, ?)', (message.video.file_id, data['t'], name))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    await message.reply(f"✅ Saqlandi!\n🔢 Kod: <b>{new_id}</b>\n🎬 Nomi: {name}")

# --- SEARCH & LIST ---
@dp.message(F.text.isdigit())
async def search(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("😊 Iltimos, avval kanalimizga obuna bo'ling!", reply_markup=sub_kb())
    
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    
    if res:
        await message.answer_sticker("CAACAgIAAxkBAAEL7") # Chiroyli stiker
        await message.answer_video(video=res[0], caption=f"🎬 <b>Nomi:</b> {res[1]}\n🔢 <b>Kodi:</b> {message.text}\n\n🍿 Yoqimli tomosha tilaymiz!\n✨ {BOT_USERNAME}")
    else:
        await message.answer("😔 Bu kod bilan hech narsa topilmadi.")

@dp.message(F.text.contains("ro'yxati"))
async def list_items(message: types.Message):
    type_filter = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT id, name FROM content WHERE type = ?', (type_filter,)).fetchall()
    conn.close()
    if not res: return await message.answer("📭 Hozircha ro'yxat bo'sh.")
    text = f"📜 <b>{type_filter}lar ro'yxati:</b>\n\n" + "\n".join([f"<b>{r[0]}</b>. {r[1]}" for r in res])
    await message.answer(text)

@dp.message(F.text == "🏠 Bosh sahifa")
async def home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh sahifa", reply_markup=main_kb())

async def main():
    await start_server()
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
