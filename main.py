import asyncio
import sqlite3
import re
import os
import logging
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

# --- REKLAMANI TOZALASH FUNKSIYASI (17-shart) ---
def clean_caption(text):
    if not text: return "Nomsiz kontent"
    # Faqat birinchi qatorni oladi
    lines = text.split('\n')
    first_line = lines[0]
    # Linklar va @username larni o'chiradi
    clean_text = re.sub(r'http\S+|@\S+|https\S+', '', first_line)
    return clean_text.strip()

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

# --- OBUNA TEKSHIRUVI (18-shart) ---
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True # Adminni tekshirmaydi
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        # Status "left" yoki "kicked" bo'lmasa, demak obuna bo'lgan
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except Exception:
        return False

# --- START HANDLER ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer(
            "😊 <b>Assalomu alaykum!</b>\n\nBotdan foydalanish uchun kanalimizga obuna bo'lishingizni iltimos qilamiz. Bu bizning mehnatimizni qo'llab-quvvatlashdir! ✨", 
            reply_markup=sub_kb()
        )
    await message.answer("🌟 <b>Xush kelibsiz!</b>\nKino kodini yuboring:", reply_markup=main_kb())

@dp.callback_query(F.data == "check_sub")
async def check(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 <b>Rahmat!</b> Endi bemalol foydalanishingiz mumkin.", reply_markup=main_kb())
    else:
        await call.answer("😔 Kechirasiz, hali obuna bo'lmadingiz!", show_alert=True)

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 <b>Admin parolini kiriting:</b>")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def auth_process(message: types.Message, state: FSMContext):
    await message.delete() # 16-shart: Parolni darrov o'chiradi
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder()
        kb.button(text="📥 Pachka qo'shish"), kb.button(text="🗑 O'chirish"), kb.button(text="🏠 Bosh sahifa")
        await message.answer("🔓 <b>Xush kelibsiz, xo'jayin!</b>", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(States.admin_menu)
    else:
        await message.answer("❌ Parol noto'g'ri!")

@dp.message(F.text == "📥 Pachka qo'shish", States.admin_menu)
async def bulk_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Kino"), kb.button(text="Multfilm")
    await message.answer("📂 <b>Turini tanlang:</b>", reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(States.choosing_type)

@dp.message(States.choosing_type)
async def set_type(message: types.Message, state: FSMContext):
    await state.update_data(t=message.text)
    await message.answer(f"🚀 <b>{message.text} rejimi yoqildi.</b>\nVideolarni yuboring, bot reklamalarni tozalab, avtomatik kod beradi!")
    await state.set_state(States.uploading)

@dp.message(F.video, States.uploading)
async def auto_upload(message: types.Message, state: FSMContext):
    data = await state.get_data()
    clean_name = clean_caption(message.caption) # 17-shart: Tozalash
    
    conn = sqlite3.connect('kino_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO content (file_id, type, name) VALUES (?, ?, ?)', 
                   (message.video.file_id, data['t'], clean_name))
    new_id = cursor.lastrowid # 14-shart: Avtomatik kod
    conn.commit()
    conn.close()
    await message.reply(f"✅ <b>Saqlandi!</b>\n🔢 Kodi: <code>{new_id}</code>\n🎬 Nomi: {clean_name}")

# --- QIDIRUV ---
@dp.message(F.text.isdigit())
async def search(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("😊 Iltimos, avval obuna bo'ling!", reply_markup=sub_kb())
    
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    
    if res:
        # 7 va 17-shartlar: Chiroyli matn
        caption = (f"🎬 <b>Nomi:</b> {res[1]}\n"
                   f"🔢 <b>Kodi:</b> {message.text}\n\n"
                   f"🍿 Yoqimli hordiq tilaymiz!\n"
                   f"✨ {BOT_USERNAME}")
        await message.answer_video(video=res[0], caption=caption)
    else:
        await message.answer("😔 <b>Kechirasiz, bu kod bilan hech narsa topilmadi.</b>")

@dp.message(F.text.contains("ro'yxati"))
async def list_items(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    t = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT id, name FROM content WHERE type = ?', (t,)).fetchall()
    conn.close()
    if not res: return await message.answer("📭 Hozircha ro'yxat bo'sh.")
    text = f"📜 <b>{t}lar ro'yxati:</b>\n\n" + "\n".join([f"<code>{r[0]}</code>. {r[1]}" for r in res])
    await message.answer(text)

@dp.message(F.text == "🏠 Bosh sahifa")
async def home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 <b>Bosh sahifa</b>", reply_markup=main_kb())

# --- SERVER ---
async def handle(request): return web.Response(text="Bot is running!")
async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
