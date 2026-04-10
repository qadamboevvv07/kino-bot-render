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

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('kino_database.db')
    # AUTOINCREMENT har safar yangi kodni +1 qilib beradi
    conn.execute('''CREATE TABLE IF NOT EXISTS content 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    file_id TEXT, 
                    type TEXT, 
                    name TEXT)''')
    conn.commit()
    conn.close()

init_db()

class States(StatesGroup):
    auth = State()
    admin_menu = State()
    choosing_type = State()
    uploading = State()

# --- REKLAMANI TOZALASH (17-shart) ---
def clean_caption(text):
    if not text: return "Nomsiz kontent"
    # Faqat birinchi qatorni oladi, link va @username larni o'chiradi
    first_line = text.split('\n')[0]
    clean_text = re.sub(r'http\S+|@\S+', '', first_line)
    return clean_text.strip()

# --- TUGMALAR ---
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎬 Kinolar ro'yxati"), kb.button(text="🧸 Multfilmlar ro'yxati")
    return kb.as_markup(resize_keyboard=True)

def sub_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="Obuna bo'lish ➕", url=f"https://t.me/{CHANNEL_ID[1:]}")
    kb.button(text="Tasdiqlash ✅", callback_data="check_sub")
    return kb.as_markup()

# --- OBUNA TEKSHIRUVI ---
async def is_subscribed(user_id):
    if user_id == ADMIN_ID: return True # Admin uchun obuna shartmas
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- ASOSIY HANDLERLAR ---
@dp.message(Command("start"))
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        # Xushmuomala tushuntirish
        return await message.answer(
            "😊 Assalomu alaykum! Botimizdan foydalanish uchun kanalimizga obuna bo'lishingizni iltimos qilamiz. "
            "Bu bizni qo'llab-quvvatlashning eng yaxshi yo'lidir! ✨", 
            reply_markup=sub_kb()
        )
    await message.answer("🌟 Xush kelibsiz! Kino kodini yuboring yoki menyudan foydalaning:", reply_markup=main_kb())

@dp.callback_query(F.data == "check_sub")
async def check(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.message.delete()
        await call.message.answer("🎉 Rahmat! Endi bemalol foydalanishingiz mumkin.", reply_markup=main_kb())
    else:
        await call.answer("😔 Kechirasiz, hali a'zo bo'lmadingiz!", show_alert=True)

# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔐 Admin parolini kiritishingizni so'rayman:")
        await state.set_state(States.auth)

@dp.message(States.auth)
async def auth_process(message: types.Message, state: FSMContext):
    await message.delete() # Parolni o'chirib yuboradi
    if message.text == ADMIN_PASSWORD:
        kb = ReplyKeyboardBuilder()
        kb.button(text="📥 Avto-qo'shish"), kb.button(text="🗑 O'chirish"), kb.button(text="🏠 Bosh sahifa")
        await message.answer("🔓 Xush kelibsiz, xo'jayin! Barcha funksiyalar tayyor.", reply_markup=kb.as_markup(resize_keyboard=True))
        await state.set_state(States.admin_menu)
    else:
        await message.answer("🚫 Parol xato!")

@dp.message(F.text == "📥 Avto-qo'shish", States.admin_menu)
async def bulk_start(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardBuilder()
    kb.button(text="Kino"), kb.button(text="Multfilm")
    await message.answer("📁 Turini tanlang:", reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(States.choosing_type)

@dp.message(States.choosing_type)
async def set_type(message: types.Message, state: FSMContext):
    await state.update_data(t=message.text)
    await message.answer(f"🚀 {message.text} rejimi yoqildi. Videolarni tashlang, bot hammasini o'zi hal qiladi!")
    await state.set_state(States.uploading)

@dp.message(F.video, States.uploading)
async def auto_upload(message: types.Message, state: FSMContext):
    data = await state.get_data()
    clean_name = clean_caption(message.caption) # Reklamasiz nom
    
    conn = sqlite3.connect('kino_database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO content (file_id, type, name) VALUES (?, ?, ?)', 
                   (message.video.file_id, data['t'], clean_name))
    new_id = cursor.lastrowid # Avtomatik tartib raqami
    conn.commit()
    conn.close()
    await message.reply(f"✅ Saqlandi!\n🔢 Kod: <b>{new_id}</b>\n🎬 Nomi: {clean_name}")

@dp.message(F.text == "🗑 O'chirish", States.admin_menu)
async def delete_cmd(message: types.Message):
    await message.answer("O'chirmoqchi bo'lgan kino kodini yuboring:")

@dp.message(States.admin_menu, F.text.isdigit())
async def delete_process(message: types.Message):
    conn = sqlite3.connect('kino_database.db')
    conn.execute('DELETE FROM content WHERE id = ?', (message.text,))
    conn.commit()
    conn.close()
    await message.answer(f"🗑 {message.text}-sonli kontent o'chirildi.")

# --- QIDIRUV VA RO'YXAT ---
@dp.message(F.text.isdigit())
async def search(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("😊 Iltimos, avval kanalimizga obuna bo'ling!", reply_markup=sub_kb())
    
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT file_id, name FROM content WHERE id = ?', (message.text,)).fetchone()
    conn.close()
    
    if res:
        # Chiroyli caption va bot linki
        caption = (f"🎬 <b>Nomi:</b> {res[1]}\n"
                   f"🔢 <b>Kodi:</b> {message.text}\n\n"
                   f"🍿 Yoqimli hordiq tilaymiz!\n"
                   f"✨ {BOT_USERNAME}")
        await message.answer_video(video=res[0], caption=caption)
    else:
        await message.answer("😔 Kechirasiz, bu kod bilan hech narsa topilmadi.")

@dp.message(F.text.contains("ro'yxati"))
async def list_items(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        return await message.answer("😊 Iltimos, avval kanalimizga obuna bo'ling!", reply_markup=sub_kb())
        
    type_filter = "Kino" if "Kino" in message.text else "Multfilm"
    conn = sqlite3.connect('kino_database.db')
    res = conn.execute('SELECT id, name FROM content WHERE type = ?', (type_filter,)).fetchall()
    conn.close()
    
    if not res: 
        return await message.answer(f"📭 Hozircha {type_filter}lar ro'yxati bo'sh.")
    
    text = f"📜 <b>{type_filter}lar ro'yxati:</b>\n\n" + "\n".join([f"<b>{r[0]}</b>. {r[1]}" for r in res])
    await message.answer(text)

@dp.message(F.text == "🏠 Bosh sahifa")
async def home(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Bosh sahifa", reply_markup=main_kb())

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
