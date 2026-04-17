import asyncio, sqlite3, re, os, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiohttp import web

# --- KONFIGURATSIYA (4, 5, 9, 12, 26-shartlar) ---
TOKEN = "8698552076:AAEngUlN8nE4nQVyEa4v4Q6WzsvJGWV5nBI"
ADMIN_ID = 5809175944
ADMIN_PASSWORD = "070820091"
CHANNEL_ID = "@Kinolar_va_multfilmlar_olamiN1"
BOT_USERNAME = "@Kinolar_multfilmbot"
MONITOR_CHANNELS = ["uzbek_retro_kinolari", "kino_tarjima_yer_osti", "Kinolark", "tarjima_kinolarsbot"]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- DATABASE (14, 19, 20, 23-shartlar) ---
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

# --- REKLAMANI TOZALASH (17, 25-shartlar) ---
def clean_caption(text):
    if not text: return "Yangi kino"
    text = re.sub(r'http\S+|@\S+|https\S+|www\S+', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return lines[0] if lines else "Nomsiz kino"

# --- OBUNA TEKSHIRUVI (13, 15, 18-shartlar) ---
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True # 15-shart
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- 26-SHART: AVTO-MONITORING ---
@dp.channel_post(F.video)
async def auto_monitor(message: types.Message):
    if message.chat.username in MONITOR_CHANNELS:
        if message.video.duration >= 3600: # 1 soatdan oshiq
            name = clean_caption(message.caption)
            conn = sqlite3.connect('kino_database.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO content (file_id, type, name, genre) VALUES (?, ?, ?, ?)', 
                           (message.video.file_id, "Kino", name, "Jangari/Sarguzasht"))
            conn.commit()
            conn.close()

# --- FOYDALANUVCHI INTERFEYSI (1, 6, 7, 13, 22, 27-shartlar) ---
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
        return await message.answer("😇 <b>Assalomu alaykum!</b>\n\nBotdan foydalanish uchun kanalimizga a'zo bo'ling. Bu biz uchun katta motivatsiya! ✨", reply_markup=kb.as_markup())
    
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati")
    await message.answer("🌟 <b>Xush kelibsiz!</b>\nKino kodini yuboring yoki ro'yxatdan tanlang:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text.isdigit())
async def get_by_code(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name, genre FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    
    if res:
        cap = (f"🎬 <b>Nomi:</b> {res[1]}\n🎭 <b>Janri:</b> {res[2]}\n🔢 <b>Kodi:</b> {message.text}\n\n"
               f"🍿 Yoqimli tomosha tilaymiz! 😊\n👉 {BOT_USERNAME}")
        await message.answer_video(video=res[0], caption=cap)
    else:
        await message.answer("😔 Kechirasiz, bunday kodli kino hali bazamizda yo'q.")

@dp.message(F.text.contains("ro'yxati")) # 27-shart (20 tadan)
async def show_list(message: types.Message):
    if not await is_subscribed(message.from_user.id): return
    cat = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT id, name FROM content WHERE type = ? ORDER BY id DESC LIMIT 20', (cat,)).fetchall()
    conn.close()
    
    if not res:
        return await message.answer("📬 Hozircha bu ro'yxat bo'sh, tez orada yangi videolar qo'shiladi! 😊")
    
    text = f"📜 <b>Oxirgi 20 ta {cat}lar:</b>\n\n"
    text += "\n".join([f"<code>{r[0]}</code> - {r[1]}" for r in res])
    await message.answer(text)

@dp.message(F.text.len() > 3) # 22-shart (Nom bo'yicha qidiruv)
async def search_by_name(message: types.Message):
    if not await is_subscribed(message.from_user.id) or message.text.startswith('/'): return
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT id, name FROM content WHERE name LIKE ? LIMIT 5', (f'%{message.text}%',)).fetchall()
    conn.close()
    
    if res:
        text = "🔍 <b>Qidiruv natijalari:</b>\n\n"
        text += "\n".join([f"🔢 Kod: <code>{r[0]}</code> | {r[1]}" for r in res])
        await message.answer(text)

# --- ADMIN PANEL (4, 5, 8, 10, 16, 20, 21-shartlar) ---
@dp.message(Command("admin"))
async def admin_auth_start(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔒 <b>Maxfiy parolni kiriting:</b>")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def admin_auth_check(message: types.Message, state: FSMContext):
    await message.delete() # 16-shart
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder()
        kb.button(text="📊 Statistika"), kb.button(text="📢 Reklama")
        kb.button(text="📥 Pachka qo'shish"), kb.button(text="🏠 Bosh sahifa")
        await message.answer("🔓 <b>Xush kelibsiz, Admin!</b>\nHamma tizimlar barqaror ishlamoqda. ✨", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(States.admin_menu)

@dp.message(F.text == "📊 Statistika", States.admin_menu)
async def stats(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    u = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    c = conn.execute('SELECT COUNT(*) FROM content').fetchone()[0]
    conn.close()
    await message.answer(f"📈 <b>Bot holati:</b>\n\n👥 Foydalanuvchilar: {u}\n🎬 Bazadagi videolar: {c}")

@dp.message(F.text == "📢 Reklama", States.admin_menu)
async def ads(message: types.Message, state: FSMContext):
    await message.answer("📝 Reklama xabarini (rasm, matn, video) yuboring:")
    await state.set_state(States.broadcast)

@dp.message(States.broadcast)
async def send_ads(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('kino_database.db')
    users = conn.execute('SELECT user_id FROM users').fetchall()
    conn.close()
    count = 0
    for u in users:
        try: await message.copy_to(u[0]); count += 1; await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Reklama {count} ta foydalanuvchiga muvaffaqiyatli yuborildi!"); await state.set_state(States.admin_menu)

# --- SERVER (RENDER UCHUN) ---
async def handle(request): return web.Response(text="Bot is Alive!")
async def main():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
