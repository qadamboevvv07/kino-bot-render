import asyncio, os, logging, re, psycopg2
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# --- KONFIGURATSIYA (4, 5, 9, 15) ---
TOKEN = "8698552076:AAEngUlN8nE4nQVyEa4v4Q6WzsvJGWV5nBI"
ADMIN_ID = 5809175944
ADMIN_PASSWORD = "070820091"
CHANNEL_ID = "@Kinolar_va_multfilmlar_olamiN1"
# Supabase URI linkini shu yerga qo'ying
DB_URL = "postgres://postgres:[parol]@db.supabase.co:5432/postgres"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class Form(StatesGroup):
    auth, admin_menu, broadcast = State(), State(), State()

# --- DATABASE (19) ---
def get_db(): return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS movies (id SERIAL PRIMARY KEY, file_id TEXT, name TEXT, type TEXT, duration INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY)")
    conn.commit(); cur.close(); conn.close()

# --- YORDAMCHI (13, 15, 17, 18, 26, 28) ---
async def check_sub(user_id):
    if user_id == ADMIN_ID: return True
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- START VA VERIFIKATSIYA (1, 13, 18, 28) ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (message.from_user.id,))
    conn.commit(); cur.close(); conn.close()
    
    if not await check_sub(message.from_user.id):
        kb = InlineKeyboardBuilder()
        kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
        kb.button(text="Tasdiqlash ✅", callback_data="verify_sub")
        return await message.answer("👋 <b>Xush kelibsiz!</b>\n\nIltimos, botdan foydalanish uchun kanalimizga obuna bo'ling. Bu bizni qo'llab-quvvatlaydi! 😊", reply_markup=kb.as_markup())
    
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati")
    await message.answer("🍿 <b>Kino kodini yuboring yoki menyudan tanlang:</b>", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.callback_query(F.data == "verify_sub")
async def verify(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 <b>Rahmat! Obuna tasdiqlandi.</b> 😊\nEndi botdan to'liq foydalanishingiz mumkin.")
    else:
        await call.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)

# --- ADMIN PANEL (4, 5, 10, 16, 20) ---
@dp.message(Command("admin"))
async def admin_auth(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 <b>Parolni kiriting:</b>")
        await state.set_state(Form.auth)

@dp.message(Form.auth)
async def check_pwd(message: types.Message, state: FSMContext):
    await message.delete() # 16-shart: Parol o'chiriladi
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder().button(text="📊 Statistika").button(text="📢 Reklama").button(text="🏠 Chiqish")
        await message.answer("🔓 <b>Admin panel ochiq!</b>", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(Form.admin_menu)
    else:
        await state.clear()

# --- AVTOMATIK QO'SHISH (14, 25, 26) ---
@dp.message(F.video)
async def auto_add_movie(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if message.video.duration < 3600: return # 26-shart: 1 soatdan uzunlar
    
    raw_caption = message.caption or "Nomsiz film"
    # Tozalash (17-shart)
    clean_name = re.sub(r'http\S+|@\S+', '', raw_caption).strip().split('\n')[0]
    m_type = "Multfilm" if "mult" in raw_caption.lower() else "Kino"
    
    conn = get_db(); cur = conn.cursor()
    cur.execute("INSERT INTO movies (file_id, name, type, duration) VALUES (%s, %s, %s, %s) RETURNING id", 
                (message.video.file_id, clean_name, m_type, message.video.duration))
    new_id = cur.fetchone()[0] # 14-shart: Avto kod
    conn.commit(); cur.close(); conn.close()
    await message.answer(f"✅ Saqlandi! Kodi: <code>{new_id}</code>")

# --- QIDIRUV VA RO'YXAT (2, 7, 11, 27) ---
@dp.message(F.text.isdigit())
async def search_movie(message: types.Message, state: FSMContext):
    # Admin parolni kiritayotgan bo'lsa, qidiruv ishlamaydi
    if await state.get_state() == Form.auth: return
    
    if not await check_sub(message.from_user.id): return
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT file_id, name FROM movies WHERE id = %s", (int(message.text),))
    res = cur.fetchone(); cur.close(); conn.close()
    
    if res:
        cap = f"🎬 <b>{res[1]}</b>\n\n🍿 Yoqimli hordiq tilaymiz! ✨\n🤖 @Kinolar_multfilmbot"
        await message.answer_video(video=res[0], caption=cap)
    else:
        await message.answer("😔 Kechirasiz, bunday kodli kino topilmadi.")

@dp.message(F.text.contains("ro'yxati"))
async def show_list(message: types.Message):
    if not await check_sub(message.from_user.id): return
    m_type = "Kino" if "Kino" in message.text else "Multfilm"
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM movies WHERE type = %s ORDER BY id DESC LIMIT 20", (m_type,))
    res = cur.fetchall(); cur.close(); conn.close()
    
    if res:
        txt = f"📜 <b>{m_type}lar (Oxirgi 20 ta):</b>\n\n" + "\n".join([f"<code>{r[0]}</code> - {r[1]}" for r in res])
        await message.answer(txt)
    else:
        await message.answer("📬 Hozircha ro'yxat bo'sh.")

# --- WEB SERVER (Render uchun) ---
async def handle(request): return web.Response(text="Bot is Active")
async def main():
    init_db()
    app = web.Application(); app.router.add_get("/", handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
