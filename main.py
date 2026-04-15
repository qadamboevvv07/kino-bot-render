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
# 26-shart uchun kanallar ro'yxati
MONITOR_CHANNELS = ["uzbek_retro_kinolari", "kino_tarjima_yer_osti", "Kinolark"]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- BAZANI ISHGA TUSHIRISH ---
def init_db():
    conn = sqlite3.connect('kino_database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS content 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       file_id TEXT, 
                       type TEXT, 
                       name TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

class States(StatesGroup):
    auth = State()
    admin_menu = State()
    uploading = State()
    broadcast = State()

# --- REKLAMANI TOZALASH (17-shart) ---
def clean_caption(text):
    if not text: return "Nomsiz kino"
    first_line = text.split('\n')[0]
    clean = re.sub(r'http\S+|@\S+|https\S+', '', first_line)
    return clean.strip()

# --- OBUNA TEKSHIRUVI (18-shart) ---
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True # 15-shart: Adminni tekshirmaslik
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except:
        return False

# --- ASOSIY MENYU ---
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati")
    kb.button(text="🧸 Multfilmlar ro'yxati")
    return kb.as_markup(resize_keyboard=True)

# --- AVTO-MONITORING (26-shart) ---
@dp.channel_post(F.video)
async def auto_save_from_channels(message: types.Message):
    if message.chat.username in MONITOR_CHANNELS:
        # Faqat 1 soatdan uzun videolarni olish (3600 sekund)
        if message.video.duration >= 3600:
            name = clean_caption(message.caption)
            conn = sqlite3.connect('kino_database.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO content (file_id, type, name) VALUES (?, ?, ?)', 
                           (message.video.file_id, "Kino", name))
            conn.commit()
            conn.close()

# --- START VA OBUNA ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    conn.commit()
    conn.close()

    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
        kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
        return await message.answer("😊 Botdan foydalanish uchun kanalimizga a'zo bo'ling!", reply_markup=kb.as_markup())
    
    await message.answer("🍿 <b>Xush kelibsiz!</b>\nKino kodini yuboring:", reply_markup=main_kb())

@dp.callback_query(F.data == "check_sub")
async def verify_sub(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Endi botdan foydalanishingiz mumkin.", reply_markup=main_kb())
    else:
        await call.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# --- ADMIN PANEL (4, 5, 20, 21-shartlar) ---
@dp.message(Command("admin"))
async def admin_entry(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 <b>Parolni kiriting:</b>")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def auth_pass(message: types.Message, state: FSMContext):
    await message.delete() # 16-shart: Parol o'chiriladi
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder()
        kb.button(text="📊 Statistika"), kb.button(text="📢 Reklama")
        kb.button(text="📥 Pachka qo'shish"), kb.button(text="🏠 Bosh sahifa")
        kb.adjust(2)
        await message.answer("🔓 Admin panel ochiq:", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(States.admin_menu)

@dp.message(F.text == "📊 Statistika", States.admin_menu)
async def show_stats(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    items = conn.execute('SELECT COUNT(*) FROM content').fetchone()[0]
    conn.close()
    await message.answer(f"📊 <b>Bot statistikasi:</b>\n\n👤 A'zolar: {users}\n🎬 Bazadagi kinolar: {items}")

@dp.message(F.text == "📢 Reklama", States.admin_menu)
async def start_broad(message: types.Message, state: FSMContext):
    await message.answer("📝 Reklama xabarini yuboring:")
    await state.set_state(States.broadcast)

@dp.message(States.broadcast)
async def run_broad(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kino_database.db')
    users = conn.execute('SELECT user_id FROM users').fetchall()
    conn.close()
    count = 0
    for u in users:
        try:
            await message.copy_to(u[0])
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ {count} kishiga yuborildi.")
    await state.set_state(States.admin_menu)

# --- QIDIRUV VA RO'YXAT (22, 27-shartlar) ---
@dp.message(F.text.isdigit())
async def search_code(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    if res:
        cap = f"🎬 <b>Nomi:</b> {res[1]}\n🔢 <b>Kodi:</b> {message.text}\n\n🍿 Yoqimli hordiq!\n✨ {BOT_USERNAME}"
        await message.answer_video(video=res[0], caption=cap)
    else:
        await message.answer("😔 Topilmadi.")

@dp.message(F.text.contains("ro'yxati"))
async def show_list(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    type_t = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    # 27-shart: 20 tadan qilib chiqarish
    res = conn.execute('SELECT id, name FROM content WHERE type = ? ORDER BY id DESC LIMIT 20', (type_t,)).fetchall()
    conn.close()
    if not res: return await message.answer("📭 Bo'sh.")
    text = f"📜 <b>Oxirgi 20 ta {type_t}:</b>\n\n" + "\n".join([f"<code>{r[0]}</code>. {r[1]}" for r in res])
    await message.answer(text)

# --- SERVER ---
async def handle(request): return web.Response(text="Bot is Live")
async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
