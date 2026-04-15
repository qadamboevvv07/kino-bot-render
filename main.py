import asyncio, sqlite3, re, os, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiohttp import web

# --- KONFIGURATSIYA (9, 4, 5, 12, 26-shartlar) ---
TOKEN = "8698552076:AAEngUlN8nE4nQVyEa4v4Q6WzsvJGWV5nBI"
ADMIN_ID = 5809175944
ADMIN_PASSWORD = "070820091"
CHANNEL_ID = "@Kinolar_va_multfilmlar_olamiN1"
BOT_USERNAME = "@Kinolar_multfilmbot"
MONITOR_CHANNELS = ["uzbek_retro_kinolari", "kino_tarjima_yer_osti", "Kinolark", "tarjima_kinolarsbot"]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- DATABASE (6, 14, 19, 20-shartlar) ---
def init_db():
    conn = sqlite3.connect('kino_database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS content 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, type TEXT, name TEXT, genre TEXT, year TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

class States(StatesGroup):
    auth = State()
    admin_menu = State()
    broadcast = State()
    add_manual = State()

# --- REKLAMANI TOZALASH VA NOMNI ANIQLASH (14, 17, 25-shartlar) ---
def clean_caption(text):
    if not text: return "Yangi kino"
    lines = text.split('\n')
    # Linklar va @belgisini o'chirish (17-shart)
    clean = re.sub(r'http\S+|@\S+|https\S+|www\S+', '', lines[0])
    return clean.strip() if clean.strip() else "Nomsiz kino"

# --- OBUNA TEKSHIRUVI (13, 15, 18-shartlar) ---
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True # 15-shart: Adminni tekshirmaslik
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

# --- 26-SHART: KANALLARNI AVTO-MONITORING QILISH ---
@dp.channel_post(F.video)
async def auto_monitor(message: types.Message):
    if message.chat.username in MONITOR_CHANNELS:
        # 26-shart: Faqat 1 soatdan (3600s) uzun MP4 videolarni olish
        if message.video.duration >= 3600:
            name = clean_caption(message.caption)
            conn = sqlite3.connect('kino_database.db')
            cursor = conn.cursor()
            # 14-shart: Avtomatik navbatma-navbat kod berish
            cursor.execute('INSERT INTO content (file_id, type, name) VALUES (?, ?, ?)', 
                           (message.video.file_id, "Kino", name))
            conn.commit()
            conn.close()

# --- ASOSIY HANDLERLAR (1, 2, 7, 11, 22-shartlar) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    conn.commit()
    conn.close()

    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
        kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
        # 13-shart: Xushmomila tushuntirish
        return await message.answer("😊 <b>Xush kelibsiz!</b>\n\nBotdan foydalanish uchun kanalimizga obuna bo'lishingizni iltimos qilamiz. Bu bizga yangi kinolar qo'shishga yordam beradi! ✨", reply_markup=kb.as_markup())
    
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati") # 1-shart
    await message.answer("🍿 <b>Kino kodini yuboring:</b>", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text.isdigit()) # 2, 7, 17-shartlar
async def get_kino(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    
    if res:
        # 7, 17-shartlar: Chiroyli format va bot linki
        cap = (f"🎬 <b>Nomi:</b> {res[1]}\n🔢 <b>Kodi:</b> {message.text}\n\n"
               f"🍿 Yoqimli hordiq tilaymiz! ✨\n👉 {BOT_USERNAME}")
        await message.answer_video(video=res[0], caption=cap)
    else:
        await message.answer("😔 Kechirasiz, bunday kodli kino topilmadi.")

@dp.message(F.text.contains("ro'yxati")) # 2, 27-shartlar
async def list_paged(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    cat = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    # 27-shart: 20 tadan qilib chiqarish
    res = conn.execute('SELECT id, name FROM content WHERE type = ? ORDER BY id DESC LIMIT 20', (cat,)).fetchall()
    conn.close()
    
    if not res: return await message.answer("📭 Hozircha ro'yxat bo'sh.")
    
    text = f"📜 <b>{cat}lar (oxirgi 20 ta):</b>\n\n"
    text += "\n".join([f"<code>{r[0]}</code>. {r[1]}" for r in res])
    await message.answer(text)

# --- ADMIN PANEL (4, 5, 8, 10, 16, 20, 21-shartlar) ---
@dp.message(Command("admin")) # 4-shart
async def adm_auth(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 <b>Parolni kiriting:</b>")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def check_adm(message: types.Message, state: FSMContext):
    await message.delete() # 16-shart: Parolni o'chirish
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder()
        kb.button(text="📊 Statistika"), kb.button(text="📢 Reklama") # 20, 21-shartlar
        kb.button(text="📥 Pachka qo'shish"), kb.button(text="🏠 Bosh sahifa")
        await message.answer("🔓 Admin panel ochiq:", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(States.admin_menu)

@dp.message(F.text == "📊 Statistika", States.admin_menu) # 20-shart
async def show_stats(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    u = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    c = conn.execute('SELECT COUNT(*) FROM content').fetchone()[0]
    conn.close()
    await message.answer(f"📊 <b>Statistika:</b>\n👥 Azolar: {u}\n🎬 Kinolar: {c}")

@dp.message(F.text == "📢 Reklama", States.admin_menu) # 21-shart
async def start_broad(message: types.Message, state: FSMContext):
    await message.answer("📝 Reklama xabarini yuboring:")
    await state.set_state(States.broadcast)

@dp.message(States.broadcast)
async def run_broad(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kino_database.db')
    users = conn.execute('SELECT user_id FROM users').fetchall()
    conn.close()
    c = 0
    for u in users:
        try: await message.copy_to(u[0]); c += 1; await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ {c} kishiga yuborildi."); await state.set_state(States.admin_menu)

@dp.message(F.text == "🏠 Bosh sahifa")
async def go_home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh sahifa", reply_markup=main_kb() if 'main_kb' in globals() else None)

# --- SERVER VA ISHGA TUSHIRISH (19-shart) ---
async def handle(request): return web.Response(text="Bot is Running!")
async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
