import asyncio, sqlite3, re, os, logging
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
# Kuzatiladigan kanallar (26-shart)
MONITOR_CHANNELS = ["uzbek_retro_kinolari", "kino_tarjima_yer_osti", "Kinolark"]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('kino_database.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS content 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, type TEXT, name TEXT, description TEXT)''')
    conn.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

init_db()

class States(StatesGroup):
    auth, admin_menu, uploading, broadcast = State(), State(), State(), State()

# --- YORDAMCHI FUNKSIYALAR ---
def clean_caption(text):
    if not text: return "Nomsiz kontent"
    first_line = text.split('\n')[0]
    return re.sub(r'http\S+|@\S+|https\S+', '', first_line).strip()

async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status not in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]
    except: return False

# --- KEYBOARDS ---
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati")
    return kb.as_markup(resize_keyboard=True)

def admin_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📥 Pachka qo'shish"), kb.button(text="📊 Statistika")
    kb.button(text="📢 Reklama"), kb.button(text="🏠 Bosh sahifa")
    kb.adjust(2); return kb.as_markup(resize_keyboard=True)

# --- AVTO-MONITORING (26-shart: Kanallarni kuzatish) ---
@dp.channel_post(F.video)
async def auto_channel_save(message: types.Message):
    if message.chat.username in MONITOR_CHANNELS:
        # Faqat 1 soatdan uzun videolarni olish (3600 sekund)
        if message.video.duration >= 3600:
            name = clean_caption(message.caption)
            conn = sqlite3.connect('kino_database.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO content (file_id, type, name) VALUES (?, ?, ?)', 
                           (message.video.file_id, "Kino", name))
            conn.commit(); conn.close()
            logging.info(f"✅ Avto-bazaga qo'shildi: {name}")

# --- ADMIN PANEL & STATISTIKA ---
@dp.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Parolni kiriting:"); await state.set_state(States.auth)

@dp.message(States.auth)
async def auth_check(message: types.Message, state: FSMContext):
    await message.delete()
    if message.text == ADMIN_PASSWORD:
        await message.answer("🔓 Xush kelibsiz!", reply_markup=admin_kb())
        await state.set_state(States.admin_menu)

@dp.message(F.text == "📊 Statistika", States.admin_menu)
async def get_stats(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    u_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    m_count = conn.execute('SELECT COUNT(*) FROM content').fetchone()[0]
    conn.close()
    await message.answer(f"📊 <b>Bot holati:</b>\n\n👤 Foydalanuvchilar: {u_count}\n🎬 Jami kinolar: {m_count}")

# --- QIDIRUV & RO'YXAT (22, 27-shartlar) ---
@dp.message(F.text.isdigit())
async def search_by_code(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("😊 Obuna bo'ling!", reply_markup=main_kb())
    
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    if res:
        cap = f"🎬 <b>Nomi:</b> {res[1]}\n🔢 <b>Kodi:</b> {message.text}\n\n🍿 Yoqimli hordiq!\n✨ {BOT_USERNAME}"
        await message.answer_video(video=res[0], caption=cap)
    else: await message.answer("❌ Topilmadi.")

@dp.message(F.text.contains("ro'yxati"))
async def list_paged(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    t = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    # 27-shart: Oxirgi 20 tasini ko'rsatish (qulaylik uchun)
    res = conn.execute('SELECT id, name FROM content WHERE type = ? ORDER BY id DESC LIMIT 20', (t,)).fetchall()
    conn.close()
    if not res: return await message.answer("📭 Hozircha bo'sh.")
    
    text = f"📜 <b>{t}lar (Oxirgi 20 ta):</b>\n\n" + "\n".join([f"<code>{r[0]}</code>. {r[1]}" for r in res])
    await message.answer(text)

# --- BROADCAST (Reklama yuborish) ---
@dp.message(F.text == "📢 Reklama", States.admin_menu)
async def broad_prompt(message: types.Message, state: FSMContext):
    await message.answer("📝 Reklama xabarini yuboring:"); await state.set_state(States.broadcast)

@dp.message(States.broadcast)
async def broad_run(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kino_database.db')
    users = conn.execute('SELECT user_id FROM users').fetchall(); conn.close()
    success = 0
    for u in users:
        try: await message.copy_to(u[0]); success += 1
        except: pass
        await asyncio.sleep(0.05)
    await message.answer(f"✅ {success} kishiga yuborildi."); await state.set_state(States.admin_menu)

# --- START & BASE LOGIC ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    conn.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    conn.commit(); conn.close()
    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
        kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
        return await message.answer("😊 Botdan foydalanish uchun obuna bo'ling!", reply_markup=kb.as_markup())
    await message.answer("🌟 Xush kelibsiz! Kodni yuboring:", reply_markup=main_kb())

async def handle(request): return web.Response(text="Bot Live")
async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); asyncio.run(main())
