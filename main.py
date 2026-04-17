import asyncio, sqlite3, re, os, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiohttp import web

# --- KONFIGURATSIYA (4, 5, 9, 12, 15, 26-shartlar) ---
TOKEN = "8698552076:AAEngUlN8nE4nQVyEa4v4Q6WzsvJGWV5nBI"
ADMIN_ID = 5809175944
ADMIN_PASSWORD = "070820091"
CHANNEL_ID = "@Kinolar_va_multfilmlar_olamiN1"
BOT_USERNAME = "@Kinolar_multfilmbot"
MONITOR_CHANNELS = ["uzbek_retro_kinolari", "kino_tarjima_yer_osti", "Kinolark", "tarjima_kinolarsbot"]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- DATABASE (14, 19, 23, 25-shartlar) ---
# MUHIM: Renderda ma'lumot yo'qolmasligi uchun tashqi SQL yoki Render Disk kerak.
def init_db():
    conn = sqlite3.connect('kino_database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS content 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, type TEXT, name TEXT, genre TEXT, desc TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

class States(StatesGroup):
    auth = State()
    admin_menu = State()
    add_bulk = State()
    broadcast = State()

# --- YORDAMCHI FUNKSIYALAR (6, 11, 17, 25-shartlar) ---
def clean_text(text):
    if not text: return "Yangi xazinamiz ✨", "Sarguzasht"
    clean = re.sub(r'http\S+|@\S+|https\S+|www\S+', '', text).strip()
    lines = [l for l in clean.split('\n') if l.strip()]
    name = lines[0] if lines else "Ajoyib kino"
    genre = "Multfilm" if "mult" in text.lower() else "Kino"
    return name, genre

async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True # 15-shart
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- MONITORING (3, 26-shartlar) ---
@dp.channel_post(F.video)
async def auto_capture(message: types.Message):
    if message.chat.username in MONITOR_CHANNELS and message.video.duration >= 3600:
        name, genre = clean_text(message.caption)
        conn = sqlite3.connect('kino_database.db')
        conn.execute('INSERT INTO content (file_id, type, name, genre) VALUES (?, ?, ?, ?)', 
                     (message.video.file_id, genre, name, "Avto-qo'shilgan"))
        conn.commit()
        conn.close()

# --- ADMIN KIRISH (5, 16-shartlar) ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 <b>Xush kelibsiz, xo'jayin! Parolni kiriting:</b>")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def check_pass(message: types.Message, state: FSMContext):
    await message.delete() # 16-shart: Parol o'chiriladi
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder()
        kb.button(text="📊 Statistika"), kb.button(text="📢 Reklama")
        kb.button(text="📥 Pachka qo'shish"), kb.button(text="🏠 Chiqish")
        await message.answer("✅ <b>Marhamat, buyruqni tanlang:</b>", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(States.admin_menu)

# --- QIDIRUV VA RO'YXAT (2, 7, 22, 27-shartlar) ---
@dp.message(F.text.isdigit())
async def search_by_id(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name, genre FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    if res:
        await message.answer_video(video=res[0], caption=f"🎬 <b>{res[1]}</b>\n\n🍿 Yoqimli hordiq tilaymiz! ✨\n🤖 @{BOT_USERNAME}")
    else:
        await message.answer("😔 Kechirasiz, bunday kodli kino topilmadi. 😊")

@dp.message(F.text.contains("ro'yxati")) # 27-shart: 20 tadan chiqarish
async def show_list(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    type_f = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT id, name FROM content WHERE type = ? ORDER BY id DESC LIMIT 20', (type_f,)).fetchall()
    conn.close()
    if res:
        txt = f"📜 <b>Oxirgi {type_f}lar:</b>\n\n" + "\n".join([f"<code>{r[0]}</code> - {r[1]}" for r in res])
        await message.answer(txt)
    else:
        await message.answer("📬 Hozircha bo'sh. 😊")

# --- PACHKA QO'SHISH (10, 12, 14, 25-shartlar) ---
@dp.message(F.text == "📥 Pachka qo'shish", States.admin_menu)
async def bulk_start(message: types.Message, state: FSMContext):
    await message.answer("📂 Videolarni (biru-to'la 10-15 ta) yuboring. Bot ularni avtomatik saqlaydi!")
    await state.set_state(States.add_bulk)

@dp.message(States.add_bulk, F.video)
async def handle_bulk(message: types.Message):
    name, genre = clean_text(message.caption)
    conn = sqlite3.connect('kino_database.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO content (file_id, type, name, genre) VALUES (?, ?, ?, ?)', 
                (message.video.file_id, genre, name, "Yangi"))
    new_id = cur.lastrowid # 14-shart: Avtomatik kod
    conn.commit()
    conn.close()
    await message.answer(f"✅ Saqlandi! Kod: <code>{new_id}</code>")

# --- START (1, 6, 13, 18-shartlar) ---
@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    conn.commit(); conn.close()
    
    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
        kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
        return await message.answer("😊 <b>Xush kelibsiz!</b>\n\nBotdan foydalanish uchun iltimos kanalimizga obuna bo'ling. Bu biz uchun katta yordam! ✨", reply_markup=kb.as_markup())
    
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati")
    await message.answer("🍿 <b>Kino kodini yuboring:</b>", reply_markup=kb.as_markup(resize_keyboard=True))

# --- SERVER ---
async def handle(request): return web.Response(text="Bot is active!")
async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
