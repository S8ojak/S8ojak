# RIDNESS Telegram-bot (final merged version)
# — Каталог с расширенным описанием
# — Рабочий Ridness Club (анкета + промокод + LTV)
# — Предзаказ товаров
# — Контакты с emoji-дизайном
# — Админ-команды /ping, /stats, /add_sale
# aiogram 2.25.2  |  Python 3.9+

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# logging
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# env
load_dotenv()
TOKEN = os.getenv("TG_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
if not TOKEN:
    sys.exit("TG_TOKEN missing in .env")

# aiogram init
bot = Bot(token=TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# throttling (works only in aiogram 2.x)
try:
    from aiogram.contrib.middlewares.throttling import ThrottlingMiddleware
    dp.middleware.setup(ThrottlingMiddleware(rate_limit=1.0))
except ImportError:
    pass  # aiogram 3.x — пропустим

# Utility: JSON storage
CATALOG_FILE = "catalog.json"
CLUB_FILE = "club_members.json"


def load_catalog():
    if not os.path.exists(CATALOG_FILE):
        return {}
    with open(CATALOG_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_club():
    if not os.path.exists(CLUB_FILE):
        return []
    return json.load(open(CLUB_FILE, encoding="utf-8"))


def save_club(data):
    json.dump(data, open(CLUB_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def is_member(user_id: int) -> bool:
    """Return True if user is already in the club."""
    return any(u.get("user_id") == user_id for u in load_club())


def get_member(user_id: int):
    """Return member record or None."""
    for u in load_club():
        if u.get("user_id") == user_id:
            return u
    return None


# Global helpers
order_map = {}
order_count = 0


# Keyboards

def main_menu() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Новости", "Каталог")
    kb.add("Предзаказ", "🐎 RIDNESS Club")
    kb.add("Контакты", "Адреса")
    return kb


def guest_menu() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🐎 RIDNESS Club")
    return kb


async def require_membership(msg: types.Message):
    """Notify user that a feature requires club membership."""
    await msg.answer(
        "Доступно только участникам RIDNESS Club.",
        reply_markup=guest_menu(),
    )


def categories_kb(cat_list):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in cat_list:
        kb.add(c)
    kb.add("В главное меню")
    return kb


# Basic commands
@dp.message_handler(commands="start")
async def cmd_start(msg: types.Message):
    if is_member(msg.from_user.id):
        await msg.answer(
            "Добро пожаловать в <b>RIDNESS</b> — экипировка для самых требовательных всадников.\n"
            "Выберите раздел 👇",
            reply_markup=main_menu(),
        )
    else:
        await msg.answer(
            "RIDNESS Club — экипировка для самых требовательных всадников.\n"
            "Для доступа к каталогу и предзаказу вступите в клуб.",
            reply_markup=guest_menu(),
        )


@dp.message_handler(commands="ping")
async def cmd_ping(msg: types.Message):
    await msg.answer("pong")


# Новости
@dp.message_handler(lambda m: m.text == "Новости")
async def show_news(msg: types.Message):
    if not is_member(msg.from_user.id):
        await require_membership(msg)
        return
    await msg.answer(
        "🔥 <b>Новости RIDNESS</b>\n"
        "• Новая коллекция уже доступна!\n"
        "• До 15 июня скидка 10 % на бриджи.\n"
        "• Следите за обновлениями!",
        reply_markup=main_menu(),
    )


# Каталог
@dp.message_handler(lambda m: m.text == "Каталог")
async def choose_category(msg: types.Message):
    if not is_member(msg.from_user.id):
        await require_membership(msg)
        return
    catalog = load_catalog()
    if not catalog:
        await msg.answer("Каталог пока пуст 🚧", reply_markup=main_menu())
        return
    await msg.answer("Выберите категорию:", reply_markup=categories_kb(catalog.keys()))


@dp.message_handler(lambda m: m.text == "Предзаказ")
async def preorder_from_menu(msg: types.Message):
    if not is_member(msg.from_user.id):
        await require_membership(msg)
        return
    await choose_category(msg)


@dp.message_handler(lambda m: m.text and m.text in load_catalog())
async def show_items(msg: types.Message):
    if not is_member(msg.from_user.id):
        await require_membership(msg)
        return
    catalog = load_catalog()
    cat = msg.text
    items = catalog.get(cat, [])
    if not items:
        await msg.answer("В этой категории пока пусто.", reply_markup=categories_kb(catalog.keys()))
        return

    for idx, item in enumerate(items):
        key = f"{cat}:{idx}"
        order_map[key] = (cat, idx)
        caption = (
            f"🆕 <b>{item['name']}</b>\n"
            f"💰 Цена: {item['price']}\n"
            f"{item['desc']}"
        )
        kb = types.InlineKeyboardMarkup().row(
            types.InlineKeyboardButton("🛒 Предзаказать", callback_data=f"order:{key}"),
            types.InlineKeyboardButton("🌐 Сайт", url="https://ridness.ru"),
        )
        photo_path = item.get("photo", "")
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as ph:
                await msg.answer_photo(ph, caption=caption, reply_markup=kb)
        else:
            await msg.answer(caption, reply_markup=kb)

    await msg.answer(
        "Выберите другую категорию или «В главное меню».",
        reply_markup=categories_kb(catalog.keys()),
    )


# FSM предзаказ
class PreOrder(StatesGroup):
    qty = State()
    comment = State()


@dp.callback_query_handler(lambda c: c.data.startswith("order:"))
async def order_start(cb: types.CallbackQuery, state: FSMContext):
    if not is_member(cb.from_user.id):
        await cb.answer("Только для участников клуба", show_alert=True)
        return
    key = cb.data.split(":", 1)[1]
    if key not in order_map:
        await cb.answer("Ошибка товара", show_alert=True)
        return
    cat, idx = order_map[key]
    catalog = load_catalog()
    item = catalog[cat][idx]
    member = get_member(cb.from_user.id) or {}
    await state.update_data(
        item=item["name"],
        name=member.get("name", ""),
        contact=member.get("phone") or member.get("email", ""),
    )
    await bot.send_message(cb.from_user.id, "Количество:")
    await PreOrder.qty.set()
    await cb.answer()


# универсальная отмена

def is_cancel(msg):
    return msg.text and msg.text.lower() == "отмена"


@dp.message_handler(state=PreOrder.qty)
async def po_comment(msg: types.Message, state: FSMContext):
    if is_cancel(msg):
        await state.finish()
        await msg.answer("Отменено.", reply_markup=main_menu())
        return
    await state.update_data(qty=msg.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("Пропустить", "Отмена")
    await msg.answer("Комментарий (или «Пропустить»):", reply_markup=kb)
    await PreOrder.comment.set()


@dp.message_handler(state=PreOrder.comment)
async def po_finish(msg: types.Message, state: FSMContext):
    if is_cancel(msg):
        await state.finish()
        await msg.answer("Отменено.", reply_markup=main_menu())
        return
    data = await state.get_data()
    if msg.text != "Пропустить":
        data["comment"] = msg.text
    global order_count
    order_count += 1
    card = (
        "🛒 <b>Предзаказ</b>\n"
        f"Товар: {data['item']}\n"
        f"Имя: {data['name']}\n"
        f"Контакт: {data['contact']}\n"
        f"Кол-во: {data['qty']}\n"
        f"Комментарий: {data.get('comment', '(нет)')}\n"
        f"Источник: telegram_bot"
    )
    await bot.send_message(ADMIN_ID, card)
    await bot.send_message(GROUP_ID, card)
    await msg.answer("Спасибо! Мы свяжемся с вами 📩", reply_markup=main_menu())
    await state.finish()


# Контакты
@dp.message_handler(lambda m: m.text == "Контакты")
async def show_contacts(msg: types.Message):
    if not is_member(msg.from_user.id):
        await require_membership(msg)
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📞 Телефон", callback_data="copy_phone"),
        types.InlineKeyboardButton("WhatsApp", url="https://wa.me/74955447166"),
        types.InlineKeyboardButton("Instagram", url="https://www.instagram.com/ridness.equestrian/"),
        types.InlineKeyboardButton("Email", url="mailto:ceo@ridness.ru"),
    )
    await msg.answer(
        "📞 <b>Контакты</b>\n"
        "Телефон: +7 495 544‑71‑66\n"
        "WhatsApp: +7 495 544‑71‑66\n"
        "Instagram: @ridness.equestrian\n"
        "Email: ceo@ridness.ru",
        reply_markup=kb,
    )


@dp.callback_query_handler(lambda c: c.data == "copy_phone")
async def copy_phone(cb: types.CallbackQuery):
    await cb.answer("Телефон: +7 495 544‑71‑66", show_alert=True)


# Адреса
@dp.message_handler(lambda m: m.text == "Адреса")
async def show_addresses(msg: types.Message):
    if not is_member(msg.from_user.id):
        await require_membership(msg)
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("КСК Прованс", url="https://yandex.com/maps/-/CHGVqL90"),
        types.InlineKeyboardButton("Магазин «Баланс»", url="https://yandex.com/maps/-/CHGVuMzD"),
        types.InlineKeyboardButton("Emerald Stables", url="https://yandex.com/maps/-/CHGVuVKs"),
    )
    await msg.answer("🏬 Наши адреса:", reply_markup=kb)


# Ridness Club
class ClubJoin(StatesGroup):
    name = State()
    phone = State()
    email = State()
    agree = State()


@dp.message_handler(lambda m: m.text and ("ridness club" in m.text.lower() or m.text.startswith("🐎")))
async def club_entry(msg: types.Message):
    members = load_club()
    if any(u["user_id"] == msg.from_user.id for u in members):
        await msg.answer("Вы уже участник клуба 🎉\nПромокод: RIDNESS10", reply_markup=main_menu())
        return
    await msg.answer(
        "RIDNESS Club — 10 % скидка на сезонную коллекцию и доступ к предзаказу новинок.\n"
        "Для вступления заполните анкету.\n\nВаше имя и фамилия:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"),
    )
    await ClubJoin.name.set()


@dp.message_handler(state=ClubJoin.name)
async def cj_phone(msg: types.Message, state: FSMContext):
    if is_cancel(msg):
        await state.finish()
        await msg.answer("Отменено.", reply_markup=main_menu())
        return
    await state.update_data(name=msg.text)
    await msg.answer(
        "Номер телефона:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"),
    )
    await ClubJoin.phone.set()


@dp.message_handler(state=ClubJoin.phone)
async def cj_email(msg: types.Message, state: FSMContext):
    if is_cancel(msg):
        await state.finish()
        await msg.answer("Отменено.", reply_markup=main_menu())
        return
    await state.update_data(phone=msg.text)
    await msg.answer(
        "E-mail:",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Отмена"),
    )
    await ClubJoin.email.set()


@dp.message_handler(state=ClubJoin.email)
async def cj_agree(msg: types.Message, state: FSMContext):
    if is_cancel(msg):
        await state.finish()
        await msg.answer("Отменено.", reply_markup=main_menu())
        return
    await state.update_data(email=msg.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("Согласен", "Отмена")
    await msg.answer(
        "Вы подтверждаете согласие на обработку персональных данных?\n"
        "Подробнее: https://ridness.ru/privacy",
        reply_markup=kb,
    )
    await ClubJoin.agree.set()


@dp.message_handler(state=ClubJoin.agree)
async def cj_finish(msg: types.Message, state: FSMContext):
    if is_cancel(msg):
        await state.finish()
        await msg.answer("Отменено.", reply_markup=main_menu())
        return
    if msg.text != "Согласен":
        await msg.answer("Для вступления требуется согласие.", reply_markup=main_menu())
        await state.finish()
        return
    data = await state.get_data()
    members = load_club()
    user = {
        "user_id": msg.from_user.id,
        "name": data.get("name", ""),
        "phone": data.get("phone", ""),
        "email": data.get("email", ""),
        "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    members.append(user)
    save_club(members)
    await bot.send_message(
        ADMIN_ID,
        f"🎉 Новый участник Ridness Club:\n{user['name']}\n{user['phone']}\n{user['email']}",
    )
    await msg.answer(
        "Поздравляем, вы вступили в RIDNESS Club!\n"
        "Ваш промокод: <b>RIDNESS10</b>\n"
        "Покажите его в магазине или введите на сайте.",
        reply_markup=main_menu(),
    )
    await state.finish()


# ADMIN: /stats, /add_sale
@dp.message_handler(commands="stats")
async def cmd_stats(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("Нет доступа.")
        return
    club = load_club()
    await msg.answer(f"Участников клуба: {len(club)}\nПредзаказов: {order_count}")


@dp.message_handler(commands="add_sale")
async def cmd_add_sale(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("Нет доступа.")
        return
    global order_count
    try:
        n = int(msg.get_args())
        order_count += n
        await msg.answer(f"Добавлено {n}. Всего предзаказов: {order_count}")
    except Exception:
        await msg.answer("Используйте: /add_sale N")


# Unknown handler
@dp.message_handler()
async def unknown(msg: types.Message):
    kb = main_menu() if is_member(msg.from_user.id) else guest_menu()
    await msg.answer("Выберите действие из меню 👇", reply_markup=kb)


# Bot runner
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

