import asyncio
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

import database
from config import ADMIN_IDS


load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("Не найден BOT_TOKEN в .env")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DURATIONS = [1, 3, 6, 12]
PAYMENTS = {
    "dushanbe": "Dushanbe City",
    "eskhata": "Eskhata Bank",
    "alif": "Alif",
}

PAYMENT_DETAILS = {
    "dushanbe": "📱 +992 007 336 610",
    "eskhata": "📱 +992 929 559 995",
    "alif": "📱 +992 007 336 610",
}

PAYMENT_OWNER = "Рахматов Фаридун"

user_selections = {}
waiting_for_receipt = {}
waiting_for_delivery = {}
waiting_for_promo = {}
admin_input = {}
waiting_for_support = {}
waiting_for_support_reply = {}


def main_menu_keyboard(user_id):
    keyboard = [
        [
            KeyboardButton(text="🛍 Каталог"),
            KeyboardButton(text="📋 Мои заказы"),
        ],
        [
            KeyboardButton(text="💬 Поддержка"),
            KeyboardButton(text="🏠 Главное меню"),
        ],
    ]

    if is_admin(user_id):
        keyboard.append([
            KeyboardButton(text="⚙️ Админ-панель")
        ])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери нужный раздел...",
    )


def home_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🛍 Открыть каталог",
            callback_data="catalog",
        )],
        [InlineKeyboardButton(
            text="📋 Мои заказы",
            callback_data="my_orders",
        )],
    ])

def clear_user_state(user_id):
    user_selections.pop(user_id, None)
    waiting_for_receipt.pop(user_id, None)
    waiting_for_delivery.pop(user_id, None)
    waiting_for_promo.pop(user_id, None)
    waiting_for_support.pop(user_id, None)
    admin_input.pop(user_id, None)

def is_admin(user_id):
    return user_id in ADMIN_IDS


def catalog_keyboard():
    products = database.get_products(active_only=True)
    buttons = [
        [InlineKeyboardButton(
            text=f"{p['name']} — {p['price']} TJS/мес.",
            callback_data=f"product:{p['product_key']}",
        )]
        for p in products
    ]
    if not buttons:
        buttons = [[InlineKeyboardButton(
            text="Каталог временно пуст", callback_data="catalog"
        )]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def duration_keyboard(key):
    buttons = [
        [InlineKeyboardButton(
            text=f"{m} месяц(а)", callback_data=f"duration:{key}:{m}"
        )]
        for m in DURATIONS
    ]
    buttons.append([InlineKeyboardButton(
        text="⬅️ В каталог", callback_data="catalog"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🛒 Оформить заказ", callback_data="create_order"
        )],
        [InlineKeyboardButton(
            text="⬅️ В каталог", callback_data="catalog"
        )],
    ])


def payment_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=name, callback_data=f"pay:{order_id}:{key}"
        )]
        for key, name in PAYMENTS.items()
    ])




def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все заказы", callback_data="admin:orders")],
        [InlineKeyboardButton(text="👥 Клиенты", callback_data="admin:customers")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="admin:support")],
        [InlineKeyboardButton(text="🛍 Управление товарами", callback_data="admin:products")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin:promocodes")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
    ])

def products_admin_keyboard():
    products = database.get_products(active_only=False)
    buttons = [
        [InlineKeyboardButton(
            text=f"{'🟢' if p['active'] else '⚫'} {p['name']} — {p['price']} TJS",
            callback_data=f"admin:product:{p['product_key']}",
        )]
        for p in products
    ]
    buttons.append([InlineKeyboardButton(
        text="➕ Добавить товар", callback_data="admin:product:add"
    )])
    buttons.append([InlineKeyboardButton(
        text="⬅️ В админ-панель", callback_data="admin:home"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_admin_keyboard(key, active):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить название/цену",
                              callback_data=f"admin:product:edit:{key}")],
        [InlineKeyboardButton(text="🔴 Деактивировать" if active else "🟢 Активировать",
                              callback_data=f"admin:product:toggle:{key}")],
        [InlineKeyboardButton(text="🗑 Удалить товар",
                              callback_data=f"admin:product:delete:{key}")],
        [InlineKeyboardButton(text="⬅️ К товарам", callback_data="admin:products")],
    ])


def order_actions_keyboard(order):
    buttons = []
    if order["status"] == "receipt_submitted":
        buttons.extend([
            [InlineKeyboardButton(text="✅ Подтвердить оплату",
                                  callback_data=f"approve:{order['id']}")],
            [InlineKeyboardButton(text="❌ Отклонить оплату",
                                  callback_data=f"reject:{order['id']}")],
        ])
    if order["status"] == "paid":
        buttons.append([InlineKeyboardButton(
            text="📨 Выдать подписку", callback_data=f"deliver:{order['id']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="⬅️ К заказам", callback_data="admin:orders"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def order_description(order):
    original_price = order.get("original_price") or order["price"]
    coupon_code = order.get("coupon_code")
    discount_percent = order.get("discount_percent") or 0

    if coupon_code and discount_percent:
        price_info = (
            f"💰 Первоначальная цена: {original_price} TJS\n"
            f"🎟 Промокод: {coupon_code}\n"
            f"🏷 Скидка: {discount_percent}%\n"
            f"✅ К оплате: {order['price']} TJS\n"
        )
    else:
        price_info = f"💰 Сумма: {order['price']} TJS\n"

    return (
        f"📦 Заказ №{order['id']}\n\n"
        f"👤 Пользователь: {order['user_id']}\n"
        f"Username: @{order['username'] or 'не указан'}\n"
        f"📦 Товар: {order['product']}\n"
        f"📅 Срок: {order['duration']} мес.\n"
        f"{price_info}"
        f"💳 Оплата: {order['payment_method'] or 'не выбрана'}\n"
        f"📌 Статус: {order['status']}\n"
        f"🕒 Дата: {order['created_at']}\n"
        f"📝 Выданная подписка: {order.get('delivery_text') or 'ещё не выдана'}"
    )

def admin_only(user_id):
    return is_admin(user_id)




@dp.message(CommandStart())
async def start(message: Message):
    uid = message.from_user.id

    # Регистрируем клиента в CRM
    database.register_customer(
        user_id=uid,
        username=message.from_user.username,
        full_name=message.from_user.full_name
    )

    clear_user_state(uid)

    await message.answer(
        "👋 Добро пожаловать в EasyPro!\n\n"
        "🛍 Здесь ты можешь приобрести цифровые подписки.\n\n"
        "Выбери нужный раздел в меню ниже.",
        reply_markup=main_menu_keyboard(uid),
    )

    await message.answer(
        "🏠 Главное меню EasyPro:",
        reply_markup=home_inline_keyboard(),
    )

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not admin_only(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа.")
        return
    await message.answer("⚙️ АДМИН-ПАНЕЛЬ EASYPRO\n\nВыбери раздел:",
                         reply_markup=admin_keyboard())

# ==========================================
# CRM: CUSTOMERS
# ==========================================

@dp.callback_query(F.data == "admin:customers")
async def admin_customers(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    customers = database.get_all_customers()

    if not customers:
        await callback.message.edit_text(
            "👥 Клиентов пока нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="admin:home"
                )]
            ])
        )
        await callback.answer()
        return

    buttons = []

    for customer in customers[:30]:
        name = customer["full_name"] or "Без имени"

        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {name} · {customer['total_orders']} заказов",
                callback_data=f"customer:{customer['user_id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin:home"
        )
    ])

    await callback.message.edit_text(
        f"👥 КЛИЕНТЫ EASYPRO\n\nВсего клиентов: {len(customers)}\n\nВыбери клиента:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("customer:"))
async def admin_customer_details(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    customer = database.get_customer(user_id)

    if not customer:
        await callback.answer("Клиент не найден.", show_alert=True)
        return

    username = (
        f"@{customer['username']}"
        if customer["username"]
        else "Не указан"
    )

    text = (
        "👤 КАРТОЧКА КЛИЕНТА\n\n"
        f"Имя: {customer['full_name']}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user_id}\n\n"
        "📅 ДАТЫ\n"
        f"Первый запуск: {customer['first_seen']}\n"
        f"Последняя активность: {customer['last_seen']}\n\n"
        "🛍 ПОКУПКИ\n"
        f"Всего заказов: {customer['total_orders']}\n"
        f"Потрачено: {customer['total_spent']} TJS\n"
    )

    buttons = [
        [InlineKeyboardButton(
            text="🛍 История заказов",
            callback_data=f"customer_orders:{user_id}"
        )]
    ]

    if customer["username"]:
        buttons.append([
            InlineKeyboardButton(
                text="👤 Открыть профиль Telegram",
                url=f"https://t.me/{customer['username']}"
            )
        ])

    buttons.extend([
        [InlineKeyboardButton(
            text="⬅️ К списку клиентов",
            callback_data="admin:customers"
        )],
        [InlineKeyboardButton(
            text="🏠 Админ-панель",
            callback_data="admin:home"
        )]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("customer_orders:"))
async def admin_customer_orders(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    orders = database.get_user_orders(user_id)

    if not orders:
        text = "🛍 У этого клиента пока нет заказов."
    else:
        text = "🛍 ИСТОРИЯ ЗАКАЗОВ\n\n"

        for order in orders[:20]:
            text += (
                f"Заказ #{order['id']}\n"
                f"Товар: {order['product']}\n"
                f"Срок: {order['duration']} мес.\n"
                f"Цена: {order['price']} TJS\n"
                f"Статус: {order['status']}\n"
                f"Дата: {order['created_at']}\n\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ К карточке клиента",
                callback_data=f"customer:{user_id}"
            )],
            [InlineKeyboardButton(
                text="🏠 Админ-панель",
                callback_data="admin:home"
            )]
        ])
    )

    await callback.answer()



@dp.message(Command("cancel"))
async def cancel_action(message: Message):
    uid = message.from_user.id
    waiting_for_support_reply.pop(uid, None)
    clear_user_state(uid)

    await message.answer(
        "❌ Текущее действие отменено.\n\n"
        "Можешь начать заново через /start."
    )

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛍 Каталог EasyPro\n\nВыбери подписку:",
        reply_markup=catalog_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("product:"))
async def show_product(callback: CallbackQuery):
    key = callback.data.split(":", 1)[1]
    product = database.get_product(key)
    if not product or not product["active"]:
        await callback.answer("Товар больше недоступен.", show_alert=True)
        return
    user_selections[callback.from_user.id] = {"product": key}
    await callback.message.edit_text(
        f"📦 {product['name']}\n\n💰 Цена за месяц: {product['price']} TJS\n\n"
        "Выбери срок подписки:",
        reply_markup=duration_keyboard(key),
    )
    await callback.answer()



@dp.callback_query(F.data.startswith("duration:"))
async def choose_duration(callback: CallbackQuery):
    _, key, months_text = callback.data.split(":")
    months = int(months_text)

    product = database.get_product(key)

    if not product or not product["active"] or months not in DURATIONS:
        await callback.answer("Некорректный выбор.", show_alert=True)
        return

    total = product["price"] * months

    user_selections[callback.from_user.id] = {
        "product": key,
        "duration": months,
        "price": total,
        "original_price": total,
        "coupon_code": None,
        "discount_percent": 0,
    }

    await callback.message.edit_text(
        f"📦 {product['name']}\n"
        f"📅 Срок: {months} мес.\n\n"
        f"💰 Цена: {total} TJS\n\n"
        "🎟 Есть промокод? Можешь получить скидку!\n"
        "Или продолжить без промокода.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🎟 Ввести промокод",
                callback_data="promo:enter"
            )],
            [InlineKeyboardButton(
                text="➡️ Продолжить без промокода",
                callback_data="create_order"
            )],
        ]),
    )

    await callback.answer()

@dp.callback_query(F.data == "promo:enter")
async def enter_promocode(callback: CallbackQuery):
    uid = callback.from_user.id

    if uid not in user_selections:
        await callback.answer("Сначала выбери подписку.", show_alert=True)
        return

    admin_input.pop(uid, None)
    waiting_for_promo[uid] = True

    await callback.message.answer(
        "🎟 Введи свой промокод:"
    )
    await callback.answer()



@dp.callback_query(F.data == "create_order")
async def create_order(callback: CallbackQuery):
    uid = callback.from_user.id
    selection = user_selections.get(uid)
    if selection and selection.get("order_id"):
        await callback.answer(
            f"Заказ №{selection['order_id']} уже создан.",
            show_alert=True
        )
        return

    if not selection or not all(
        k in selection for k in ("product", "duration", "price")
    ):
        await callback.answer(
            "Сначала выбери подписку и срок.",
            show_alert=True
        )
        return

    product = database.get_product(selection["product"])

    if not product or not product["active"]:
        user_selections.pop(uid, None)
        await callback.answer(
            "Этот товар больше недоступен.",
            show_alert=True
        )
        return

    coupon_code = selection.get("coupon_code")
    discount_percent = selection.get("discount_percent", 0)
    original_price = selection.get("original_price", selection["price"])

    # Повторная проверка промокода перед созданием заказа
    if coupon_code:
        promo = database.get_promocode(coupon_code)

        if (
            not promo
            or not promo["active"]
            or (
                promo["max_uses"] > 0
                and promo["used_count"] >= promo["max_uses"]
            )
        ):
            user_selections.pop(uid, None)
            await callback.answer(
                "Промокод больше недоступен. Выбери подписку заново.",
                show_alert=True
            )
            return

    order_id = database.create_order(
        user_id=uid,
        username=callback.from_user.username or "",
        product=product["name"],
        duration=selection["duration"],
        price=selection["price"],
        original_price=original_price,
        coupon_code=coupon_code,
        discount_percent=discount_percent,
    )    
	
    selection["order_id"] = order_id

    # Учитываем использование после создания заказа
    if coupon_code:
        database.use_promocode(coupon_code)

    price_text = (
        f"💰 Первоначальная цена: {original_price} TJS\n"
        f"🎟 Промокод: {coupon_code}\n"
        f"🏷 Скидка: {discount_percent}%\n"
        f"✅ К оплате: {selection['price']} TJS"
        if coupon_code
        else f"💰 Сумма: {selection['price']} TJS"
    )

    await callback.message.edit_text(
        f"✅ Заказ №{order_id} создан!\n\n"
        f"📦 {product['name']}\n"
        f"📅 Срок: {selection['duration']} мес.\n\n"
        f"{price_text}\n\n"
        "Выбери способ оплаты:",
        reply_markup=payment_keyboard(order_id),
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("pay:"))
async def choose_payment(callback: CallbackQuery):
    _, order_id_text, method = callback.data.split(":")
    order_id = int(order_id_text)
    if method not in PAYMENTS:
        await callback.answer("Способ оплаты не найден.", show_alert=True)
        return
    order = database.get_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    if order["status"] != "pending":
        await callback.answer("Этот заказ уже обработан.", show_alert=True)
        return
    database.save_payment(order_id, PAYMENTS[method], "")
    waiting_for_receipt[callback.from_user.id] = order_id
    await callback.message.edit_text(
    f"💳 Способ оплаты: {PAYMENTS[method]}\n\n"
    f"👤 Получатель: {PAYMENT_OWNER}\n"
    f"📱 Реквизиты: {PAYMENT_DETAILS[method]}\n\n"
    f"📦 Заказ №{order_id}\n"
    f"💰 Сумма: {order['price']} TJS\n\n"
    "⚠️ После перевода отправь фотографию чека "
    "в этот чат.\n\n"
    "Администратор проверит оплату.",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⬅️ Назад к способам оплаты",
            callback_data=f"back:payments:{order_id}"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="home"
        )],
    ])
)
    await callback.answer()
@dp.callback_query(F.data == "home")
async def callback_home(callback: CallbackQuery):
    clear_user_state(callback.from_user.id)

    await callback.message.answer(
        "🏠 Главное меню EasyPro\n\nВыбери нужный раздел:",
        reply_markup=main_menu_keyboard(callback.from_user.id),
    )

    await callback.message.answer(
        "Добро пожаловать!",
        reply_markup=home_inline_keyboard(),
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("back:payments:"))
async def back_to_payments(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[2])
    order = database.get_order(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    if order["status"] != "pending":
        await callback.answer(
            "Этот заказ уже обработан.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        f"📦 Заказ №{order_id}\n"
        f"💰 Сумма: {order['price']} TJS\n\n"
        "Выбери способ оплаты:",
        reply_markup=payment_keyboard(order_id),
    )

    await callback.answer()

@dp.message(F.photo)
async def receive_receipt(message: Message):
    uid = message.from_user.id
    order_id = waiting_for_receipt.get(uid)
    if not order_id:
        return
    order = database.get_order(order_id)
    if not order or order["user_id"] != uid or order["status"] != "pending":
        waiting_for_receipt.pop(uid, None)
        await message.answer("Заказ не найден или уже обработан.")
        return
    file_id = message.photo[-1].file_id
    database.save_payment(order_id, order["payment_method"], file_id)
    database.update_order_status(order_id, "receipt_submitted")
    waiting_for_receipt.pop(uid, None)
    await message.answer(
        f"📩 Чек по заказу №{order_id} получен!\n\n"
        "Администратор проверит оплату и сообщит результат."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔍 Открыть заказ",
                             callback_data=f"admin:order:{order_id}")
    ]])
    admin_text = (
        f"🔔 НОВЫЙ ЧЕК!\n\n📦 Заказ №{order_id}\n"
        f"👤 Клиент: {message.from_user.full_name}\n🆔 ID: {uid}\n"
        f"📦 Товар: {order['product']}\n📅 Срок: {order['duration']} мес.\n"
        f"💰 Сумма: {order['price']} TJS\n"
        f"💳 Способ оплаты: {order['payment_method']}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка уведомления {admin_id}: {e}")


@dp.callback_query(F.data == "admin:home")
async def admin_home(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("⚙️ АДМИН-ПАНЕЛЬ EASYPRO",
                                     reply_markup=admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin:support")
async def admin_support(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🟢 Активные обращения",
            callback_data="support:list:open"
        )],
        [InlineKeyboardButton(
            text="⚫ Закрытые обращения",
            callback_data="support:list:closed"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin:home"
        )]
    ])

    await callback.message.edit_text(
        "💬 ПОДДЕРЖКА EASYPRO\n\nВыбери категорию:",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("support:list:"))
async def support_ticket_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    status = callback.data.split(":")[2]
    tickets = database.get_all_support_tickets(status)

    title = "🟢 АКТИВНЫЕ ОБРАЩЕНИЯ" if status == "open" else "⚫ ЗАКРЫТЫЕ ОБРАЩЕНИЯ"

    buttons = []

    for ticket in tickets[:30]:
        buttons.append([
            InlineKeyboardButton(
                text=f"🎫 №{ticket['id']} | Клиент {ticket['user_id']}",
                callback_data=f"support_ticket:{ticket['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ К поддержке",
            callback_data="admin:support"
        )
    ])

    text = title + "\n\n"

    if tickets:
        text += f"Всего обращений: {len(tickets)}\nВыбери обращение:"
    else:
        text += "Обращений пока нет."

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("support_ticket:"))
async def support_ticket_details(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = database.get_ticket(ticket_id)

    if not ticket:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return

    customer = database.get_customer(ticket["user_id"]) or {}
    messages = database.get_support_messages(ticket_id)

    username = customer.get("username")
    full_name = customer.get("full_name") or "Не указано"

    text = (
        f"🎫 ОБРАЩЕНИЕ №{ticket_id}\n\n"
        f"👤 Клиент: {full_name}\n"
        f"🆔 ID: {ticket['user_id']}\n"
        f"Username: @{username or 'не указан'}\n"
        f"📌 Статус: {ticket['status']}\n"
        f"📅 Создано: {ticket['created_at']}\n\n"
        "💬 ИСТОРИЯ ПЕРЕПИСКИ:\n\n"
    )

    if messages:
        for msg in messages[-15:]:
            role = "👤 Клиент" if msg["sender_role"] == "customer" else "🛠 Администратор"
            text += (
                f"{role} ({msg['created_at']}):\n"
                f"{msg['message_text']}\n\n"
            )
    else:
        text += "Сообщений пока нет."

    buttons = []

    if ticket["status"] == "open":
        buttons.append([
            InlineKeyboardButton(
                text="✉️ Ответить клиенту",
                callback_data=f"support_reply:{ticket_id}"
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🔒 Закрыть обращение",
                callback_data=f"support_close:{ticket_id}"
            )
        ])
        back_status = "open"
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🔓 Открыть снова",
                callback_data=f"support_reopen:{ticket_id}"
            )
        ])
        back_status = "closed"

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"support:list:{back_status}"
        )
    ])

    await callback.message.edit_text(
        text[:4000],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("support_close:"))
async def support_close(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    database.close_support_ticket(ticket_id)

    await callback.message.edit_text(
        f"🔒 Обращение №{ticket_id} закрыто.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ К обращению",
                callback_data=f"support_ticket:{ticket_id}"
            )],
            [InlineKeyboardButton(
                text="⬅️ К поддержке",
                callback_data="admin:support"
            )]
        ])
    )
    await callback.answer("Обращение закрыто.")


@dp.callback_query(F.data.startswith("support_reopen:"))
async def support_reopen(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    database.reopen_support_ticket(ticket_id)

    await callback.message.edit_text(
        f"🔓 Обращение №{ticket_id} снова открыто.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ К обращению",
                callback_data=f"support_ticket:{ticket_id}"
            )],
            [InlineKeyboardButton(
                text="⬅️ К поддержке",
                callback_data="admin:support"
            )]
        ])
    )
    await callback.answer("Обращение открыто.")



@dp.callback_query(F.data == "admin:orders")
async def admin_orders(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    orders = database.get_all_orders()
    if not orders:
        await callback.message.edit_text("📋 Заказов пока нет.",
                                         reply_markup=admin_keyboard())
        await callback.answer()
        return
    buttons = [[InlineKeyboardButton(
        text=f"№{o['id']} | {o['product']} | {o['status']}",
        callback_data=f"admin:order:{o['id']}",
    )] for o in orders[:30]]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:home")])
    await callback.message.edit_text(
        f"📋 ВСЕ ЗАКАЗЫ\n\nВсего: {len(orders)}\nВыбери заказ:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:order:"))
async def admin_order(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    order_id = int(callback.data.split(":")[2])
    order = database.get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return
    await callback.message.edit_text(order_description(order),
                                     reply_markup=order_actions_keyboard(order))
    if order["receipt_file_id"]:
        await bot.send_photo(callback.from_user.id, order["receipt_file_id"],
                             caption=f"🧾 Чек по заказу №{order_id}")
    await callback.answer()


@dp.callback_query(F.data == "admin:promocodes")
async def admin_promocodes(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    codes = database.get_all_promocodes()

    if not codes:
        text = "🎟 ПРОМОКОДЫ EASYPRO\n\nПромокодов пока нет."
    else:
        lines = ["🎟 ПРОМОКОДЫ EASYPRO\n"]
        for promo in codes:
            status = "🟢 Активен" if promo["active"] else "🔴 Отключён"
            limit = "∞" if promo["max_uses"] == 0 else str(promo["max_uses"])
            lines.append(
                f"🎫 {promo['code']}\n"
                f"Скидка: {promo['discount_percent']}%\n"
                f"Использовано: {promo['used_count']} / {limit}\n"
                f"Статус: {status}\n"
            )
        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin:promo_add")],
            [InlineKeyboardButton(text="🔄 Включить / отключить", callback_data="admin:promo_toggle")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:home")],
        ]),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:promo_toggle")
async def admin_promo_toggle_menu(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    codes = database.get_all_promocodes()

    if not codes:
        await callback.answer("Промокодов пока нет.", show_alert=True)
        return

    buttons = []

    for promo in codes:
        status = "🟢" if promo["active"] else "🔴"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {promo['code']}",
                callback_data=f"admin:promo_switch:{promo['code']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin:promocodes"
        )
    ])

    await callback.message.edit_text(
        "Выбери промокод, статус которого нужно изменить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:promo_switch:"))
async def admin_promo_switch(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    code = callback.data.split(":", 2)[2]

    promo = database.get_promocode(code)

    if not promo:
        await callback.answer("Промокод не найден.", show_alert=True)
        return

    database.toggle_promocode(code)

    await callback.answer(
        f"{code}: {'отключён' if promo['active'] else 'включён'}",
        show_alert=True
    )

    # Обновляем список промокодов
    await admin_promocodes(callback)


@dp.callback_query(F.data == "admin:promo_add")
async def admin_promo_add(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    admin_input[callback.from_user.id] = {"action": "promo_code"}

    await callback.message.answer(
        "🎟 Создание промокода\n\n"
        "Введи название промокода.\n"
        "Например: EASY10"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    orders = database.get_all_orders()
    total = len(orders)
    paid = sum(o["status"] == "paid" for o in orders)
    delivered = sum(o["status"] == "delivered" for o in orders)
    waiting = sum(o["status"] == "receipt_submitted" for o in orders)
    rejected = sum(o["status"] == "rejected" for o in orders)
    revenue = sum(o["price"] for o in orders if o["status"] in ("paid", "delivered"))
    await callback.message.edit_text(
        "📊 СТАТИСТИКА EASYPRO\n\n"
        f"📦 Всего заказов: {total}\n💳 Ожидают проверки: {waiting}\n"
        f"✅ Оплачено: {paid}\n📨 Выдано: {delivered}\n"
        f"❌ Отклонено: {rejected}\n\n💰 Подтверждённая выручка: {revenue} TJS",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:home")
        ]]),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("approve:"))
async def approve_payment(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    order_id = int(callback.data.split(":")[1])
    order = database.get_order(order_id)
    if not order or order["status"] != "receipt_submitted":
        await callback.answer("Заказ уже обработан или не найден.", show_alert=True)
        return
    database.update_order_status(order_id, "paid")
    # Начисление 5% кэшбэка за оплаченный заказ
    cashback = round(float(order["price"]) * 0.05, 2)

    cashback_added = database.add_cashback(
        order["user_id"],
        order_id,
        cashback
    )
    try:
        await bot.send_message(
            order["user_id"],
            f"✅ Оплата по заказу №{order_id} подтверждена!\n\n"
            f"💚 Тебе начислено кэшбэка: {cashback if cashback_added else 0} TJS\n\n"
            "Скоро мы отправим тебе подписку."
        )
    except Exception as e:
        print(f"Не удалось уведомить клиента: {e}")

    order = database.get_order(order_id)
    await callback.message.edit_text(order_description(order),
                                     reply_markup=order_actions_keyboard(order))
    await callback.answer("Оплата подтверждена!")


@dp.callback_query(F.data.startswith("reject:"))
async def reject_payment(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    order_id = int(callback.data.split(":")[1])
    order = database.get_order(order_id)
    if not order or order["status"] != "receipt_submitted":
        await callback.answer("Заказ уже обработан или не найден.", show_alert=True)
        return
    database.update_order_status(order_id, "rejected")
    try:
        await bot.send_message(order["user_id"],
            f"❌ Оплата по заказу №{order_id} отклонена.\n\nСвяжись с нашей поддержкой для уточнения.")
    except Exception as e:
        print(f"Не удалось уведомить клиента: {e}")
    order = database.get_order(order_id)
    await callback.message.edit_text(order_description(order),
                                     reply_markup=order_actions_keyboard(order))
    await callback.answer("Оплата отклонена.")


@dp.callback_query(F.data.startswith("deliver:"))
async def start_delivery(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    order_id = int(callback.data.split(":")[1])
    order = database.get_order(order_id)
    if not order or order["status"] != "paid":
        await callback.answer("Сначала подтверди оплату.", show_alert=True)
        return
    waiting_for_delivery[callback.from_user.id] = order_id
    await callback.message.answer(
        f"📨 Отправь следующим сообщением данные подписки для заказа №{order_id}.\n\n"
        "Например: логин, пароль или инструкция клиенту.\n\nОтправь /cancel для отмены."
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:products")
async def admin_products(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text("🛍 УПРАВЛЕНИЕ ТОВАРАМИ\n\nВыбери товар:",
                                     reply_markup=products_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "admin:product:add")
async def admin_add_product(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    admin_input[callback.from_user.id] = {"action": "add_key"}
    await callback.message.answer(
        "➕ Добавление товара\n\nОтправь уникальный ключ товара латиницей "
        "(например: spotify). Только a-z, цифры и _; от 2 до 32 символов.\n\n/cancel — отмена."
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:product:edit:"))
async def admin_edit_product(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    key = callback.data.split(":")[3]
    product = database.get_product(key)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    admin_input[callback.from_user.id] = {"action": "edit_name", "key": key}
    await callback.message.answer(f"Текущее название: {product['name']}\nОтправь новое название.")
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:product:toggle:"))
async def admin_toggle_product(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    key = callback.data.split(":")[3]
    product = database.get_product(key)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    database.toggle_product(key)
    updated = database.get_product(key)
    await callback.message.edit_text(
        f"📦 {updated['name']}\n💰 Цена: {updated['price']} TJS/мес.\n"
        f"Статус: {'активен' if updated['active'] else 'выключен'}",
        reply_markup=product_admin_keyboard(key, updated["active"]),
    )
    await callback.answer("Статус изменён.")


@dp.callback_query(F.data.startswith("admin:product:delete:"))
async def admin_delete_product(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    key = callback.data.split(":")[3]
    product = database.get_product(key)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Удалить товар «{product['name']}»?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да, удалить",
                                  callback_data=f"admin:product:delete_confirm:{key}")],
            [InlineKeyboardButton(text="Отмена", callback_data=f"admin:product:{key}")],
        ]),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:product:delete_confirm:"))
async def admin_delete_product_confirm(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    key = callback.data.split(":")[3]
    product = database.get_product(key)
    if product:
        database.delete_product(key)
    await callback.message.edit_text("🗑 Товар удалён.",
                                     reply_markup=products_admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data.regexp(r"^admin:product:[^:]+$"))
async def admin_product_detail(callback: CallbackQuery):
    if not admin_only(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    key = callback.data.split(":")[2]
    product = database.get_product(key)
    if not product:
        await callback.answer("Товар не найден.", show_alert=True)
        return
    await callback.message.edit_text(
        f"📦 {product['name']}\n💰 Цена: {product['price']} TJS/мес.\n"
        f"Статус: {'активен' if product['active'] else 'выключен'}",
        reply_markup=product_admin_keyboard(key, product["active"]),
    )
    await callback.answer()

# ===== ПОСТОЯННОЕ МЕНЮ =====

@dp.message(F.text == "🛍 Каталог")
async def menu_catalog(message: Message):
    await message.answer(
        "🛍 Каталог EasyPro\n\nВыбери подписку:",
        reply_markup=catalog_keyboard(),
    )


@dp.message(F.text == "📋 Мои заказы")
async def menu_my_orders(message: Message):
    orders = database.get_user_orders(message.from_user.id)

    if not orders:
        await message.answer(
            "📋 У тебя пока нет заказов.",
            reply_markup=home_inline_keyboard(),
        )
        return

    status_names = {
        "pending": "⏳ Ожидает оплаты",
        "receipt_submitted": "🔍 Чек на проверке",
        "approved": "✅ Оплата подтверждена",
        "rejected": "❌ Заказ отклонён",
        "paid": "✅ Оплата подтверждена",
        "delivered": "🎉 Подписка выдана",
    }

    lines = ["📋 ТВОИ ЗАКАЗЫ\n"]

    for order in orders:
        status = status_names.get(order["status"], order["status"])

        original_price = order.get("original_price") or order["price"]
        coupon_code = order.get("coupon_code")
        discount_percent = order.get("discount_percent") or 0

        if coupon_code and discount_percent:
            price_info = (
                f"Первоначальная цена: {original_price} TJS\n"
                f"🎟 Промокод: {coupon_code}\n"
                f"🏷 Скидка: {discount_percent}%\n"
                f"✅ К оплате: {order['price']} TJS\n"
            )
        else:
            price_info = f"Сумма: {order['price']} TJS\n"

        lines.append(
            f"📦 Заказ №{order['id']}\n"
            f"Товар: {order['product']}\n"
            f"Срок: {order['duration']} мес.\n"
            f"{price_info}"
            f"Статус: {status}\n"
            f"Подписка: {order.get('delivery_text') or 'Ещё не выдана'}\n"
        )

    await message.answer(
        "\n".join(lines),
        reply_markup=home_inline_keyboard(),
    )


@dp.message(F.text == "🏠 Главное меню")
async def menu_home(message: Message):
    clear_user_state(message.from_user.id)

    await message.answer(
        "🏠 Главное меню EasyPro\n\n"
        "Выбери нужный раздел:",
        reply_markup=main_menu_keyboard(message.from_user.id),
    )

    await message.answer(
        "Добро пожаловать!",
        reply_markup=home_inline_keyboard(),
    )


@dp.message(F.text == "💬 Поддержка")
async def menu_support(message: Message):
    uid = message.from_user.id

    ticket = database.get_active_ticket(uid)

    if not ticket:
        ticket_id = database.create_support_ticket(uid)
    else:
        ticket_id = ticket["id"]

    waiting_for_support[uid] = ticket_id

    await message.answer(
        f"💬 Поддержка EasyPro\n\n"
        f"🎫 Обращение №{ticket_id}\n"
        "Напиши свой вопрос или сообщение.\n\n"
        "Наши администраторы ответят здесь.\n"
        "Все сообщения сохраняются в истории.\n\n"
        "Для выхода из режима поддержки напиши /cancel."
    )

@dp.message(F.text == "⚙️ Админ-панель")
async def menu_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа.")
        return

    await message.answer(
        "⚙️ АДМИН-ПАНЕЛЬ EASYPRO\n\nВыбери раздел:",
        reply_markup=admin_keyboard(),
    )
@dp.callback_query(F.data.startswith("support_reply:"))
async def support_reply_start(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    ticket_id = int(callback.data.split(":")[1])
    ticket = database.get_ticket(ticket_id)

    if not ticket:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return

    if ticket["status"] != "open":
        await callback.answer(
            "Обращение закрыто. Сначала открой его снова.",
            show_alert=True
        )
        return

    waiting_for_support_reply[callback.from_user.id] = ticket_id

    await callback.message.answer(
        f"✉️ Ответ клиенту\n"
        f"🎫 Обращение №{ticket_id}\n"
        f"🆔 Клиент: {ticket['user_id']}\n\n"
        "Отправь сообщение клиенту.\n"
        "Можешь отправлять несколько сообщений подряд.\n"
        "Для выхода напиши /cancel."
    )

    await callback.answer()
@dp.message(F.text)
async def handle_admin_text(message: Message):
    uid = message.from_user.id

    # Ответ администратора клиенту
    if uid in waiting_for_support_reply:
        ticket_id = waiting_for_support_reply[uid]
        ticket = database.get_ticket(ticket_id)
        reply_text = message.text.strip()

        if not reply_text:
            await message.answer("Напиши текст ответа.")
            return

        if not ticket or ticket["status"] != "open":
            waiting_for_support_reply.pop(uid, None)
            await message.answer("Обращение закрыто или не найдено.")
            return

        try:
            database.save_support_message(
                ticket_id,
                uid,
                "admin",
                reply_text
            )

            await bot.send_message(
                ticket["user_id"],
                f"💬 ОТВЕТ ПОДДЕРЖКИ EASYPRO\n\n{reply_text}"
            )

            await message.answer(
                f"✅ Сообщение отправлено клиенту.\n"
                f"🎫 Обращение №{ticket_id}\n\n"
                "Можешь отправить следующий ответ или написать /cancel."
            )

        except Exception as e:
            print(f"Ошибка отправки ответа: {e}")
            await message.answer("❌ Не удалось отправить сообщение.")

        return

    # Сообщение клиента в активном обращении
    if not is_admin(uid) and uid not in waiting_for_promo:
        ticket = database.get_active_ticket(uid)

        if ticket:
            ticket_id = ticket["id"]
            support_text = message.text.strip()

            if not support_text:
                await message.answer("Напиши текст сообщения.")
                return

            database.save_support_message(
                ticket_id,
                uid,
                "customer",
                support_text
            )

            reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✉️ Ответить клиенту",
                    callback_data=f"support_reply:{ticket_id}"
                )],
                [InlineKeyboardButton(
                    text="📋 Открыть обращение",
                    callback_data=f"support_ticket:{ticket_id}"
                )]
            ])

            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"💬 НОВОЕ СООБЩЕНИЕ В ПОДДЕРЖКУ\n\n"
                        f"🎫 Обращение №{ticket_id}\n"
                        f"👤 {message.from_user.full_name}\n"
                        f"🆔 ID: {uid}\n\n"
                        f"📝 Сообщение:\n{support_text}",
                        reply_markup=reply_keyboard
                    )
                except Exception as e:
                    print(f"Ошибка отправки поддержки {admin_id}: {e}")

            await message.answer(
                "✅ Сообщение отправлено администраторам.",
                reply_markup=main_menu_keyboard(uid)
            )
            return

    # Ввод промокода клиентом
    if uid in waiting_for_promo:
        code = message.text.strip().upper()
        selection = user_selections.get(uid)

        if not selection:
            waiting_for_promo.pop(uid, None)
            await message.answer("Сначала выбери подписку заново.")
            return

        promo = database.get_promocode(code)

        if not promo or not promo["active"]:
            await message.answer(
                "❌ Промокод не найден или отключён. Попробуй ещё раз."
            )
            return

        if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
            await message.answer(
                "❌ Лимит использований этого промокода исчерпан."
            )
            return

        original_price = selection["original_price"]
        discount_percent = promo["discount_percent"]
        final_price = original_price * (100 - discount_percent) // 100
        discount_amount = original_price - final_price

        selection["price"] = final_price
        selection["coupon_code"] = code
        selection["discount_percent"] = discount_percent

        waiting_for_promo.pop(uid, None)

        await message.answer(
            "🎉 ПРОМОКОД ПРИМЕНЁН!\n\n"
            f"🎟 Код: {code}\n"
            f"💰 Первоначальная цена: {original_price} TJS\n"
            f"🏷 Скидка: {discount_percent}% (-{discount_amount} TJS)\n"
            f"✅ Итоговая цена: {final_price} TJS\n\n"
            "Нажми кнопку ниже, чтобы оформить заказ.",
            reply_markup=order_keyboard()
        )
        return

    # Остальные действия доступны только администраторам
    if not is_admin(uid):
        return

    state = admin_input.get(uid)

    if state:
        value = message.text.strip()
        action = state["action"]

        if action == "promo_code":
            code = value.upper()

            if not re.fullmatch(r"[A-Z0-9_-]{3,20}", code):
                await message.answer(
                    "❌ Используй 3–20 символов: латинские буквы, цифры, _ или -."
                )
                return

            if database.get_promocode(code):
                await message.answer("❌ Такой промокод уже существует.")
                return

            admin_input[uid] = {
                "action": "promo_discount",
                "code": code
            }

            await message.answer(
                f"🎟 Промокод: {code}\n\n"
                "Теперь введи размер скидки в процентах (от 1 до 100)."
            )
            return

        if action == "promo_discount":
            if not value.isdigit() or not 1 <= int(value) <= 100:
                await message.answer("❌ Введи целое число от 1 до 100.")
                return

            admin_input[uid] = {
                "action": "promo_limit",
                "code": state["code"],
                "discount": int(value)
            }

            await message.answer(
                f"✅ Скидка: {value}%\n\n"
                "Теперь введи максимальное количество использований.\n"
                "Например: 50\n"
                "Или отправь 0, если ограничений нет."
            )
            return

        if action == "promo_limit":
            if not value.isdigit():
                await message.answer("❌ Введи целое число от 0 и выше.")
                return

            max_uses = int(value)

            database.add_promocode(
                state["code"],
                state["discount"],
                max_uses
            )

            limit_text = "Без ограничений" if max_uses == 0 else str(max_uses)

            await message.answer(
                "🎉 ПРОМОКОД СОЗДАН!\n\n"
                f"🎟 Код: {state['code']}\n"
                f"💰 Скидка: {state['discount']}%\n"
                f"🔢 Лимит: {limit_text}\n\n"
                "Промокод готов к использованию."
            )
            admin_input.pop(uid, None)

            await message.answer(
                "🎟 Управление промокодами:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="⬅️ К промокодам",
                        callback_data="admin:promocodes"
                    )]
                ])
            )
            return

        if action == "add_key":
            value = re.sub(r"\s+", "_", value.strip()).lower()

            if not re.fullmatch(r"[a-z0-9_]{2,32}", value):
                await message.answer(
                    "❌ Используй латинские буквы, цифры и пробелы. "
                    "От 2 до 32 символов."
                )
                return

            if database.get_product(value):
                await message.answer(
                    "Такой ключ уже существует. Отправь другой."
                )
                return

            admin_input[uid] = {
                "action": "add_name",
                "key": value
            }

            await message.answer(
                f"✅ Ключ: {value}\n\n"
                "Теперь отправь название товара так, "
                "как его увидят клиенты."
            )
            return

        if action == "add_name":
            if not value:
                await message.answer("Название не может быть пустым.")
                return

            admin_input[uid]["name"] = value
            admin_input[uid]["action"] = "add_price"
            await message.answer("Отправь цену за 1 месяц в TJS (только число).")
            return

        if action == "add_price":
            if not value.isdigit() or int(value) <= 0:
                await message.answer("Цена должна быть положительным целым числом.")
                return

            database.add_product(state["key"], state["name"], int(value))
            admin_input.pop(uid, None)

            await message.answer("✅ Товар добавлен в каталог.")
            await message.answer(
                "🛍 Управление товарами:",
                reply_markup=products_admin_keyboard()
            )
            return

        if action == "edit_name":
            if not value:
                await message.answer("Название не может быть пустым.")
                return

            admin_input[uid] = {
                "action": "edit_price",
                "key": state["key"],
                "name": value
            }

            await message.answer("Отправь новую цену за месяц в TJS (только число).")
            return

        if action == "edit_price":
            if not value.isdigit() or int(value) <= 0:
                await message.answer("Цена должна быть положительным целым числом.")
                return

            database.update_product(state["key"], state["name"], int(value))
            admin_input.pop(uid, None)
            product = database.get_product(state["key"])

            await message.answer(
                f"✅ Товар обновлён: {product['name']} — {product['price']} TJS/мес."
            )
            await message.answer(
                "🛍 Управление товарами:",
                reply_markup=products_admin_keyboard()
            )
            return

    # Отправка оплаченного заказа клиенту
    order_id = waiting_for_delivery.get(uid)

    if not order_id:
        return

    order = database.get_order(order_id)

    if not order or order["status"] != "paid":
        waiting_for_delivery.pop(uid, None)
        await message.answer("Заказ уже обработан.")
        return

    delivery_text = message.text.strip()

    if not delivery_text:
        await message.answer("Сообщение пустое. Отправь данные подписки.")
        return

    database.save_delivery(order_id, delivery_text)
    database.update_order_status(order_id, "delivered")
    waiting_for_delivery.pop(uid, None)

    try:
        await bot.send_message(
            order["user_id"],
            f"🎉 Твоя подписка готова!\n\n📦 Заказ №{order_id}\n"
            f"📦 {order['product']}\n\n🔐 Данные подписки:\n{delivery_text}\n\n"
            "Спасибо, что выбрал EasyPro!"
        )
    except Exception as e:
        print(f"Не удалось отправить подписку клиенту: {e}")

    await message.answer(
        f"✅ Подписка по заказу №{order_id} отправлена клиенту."
    )

@dp.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery):
    orders = database.get_user_orders(callback.from_user.id)

    if not orders:
        await callback.message.edit_text(
            "📋 У тебя пока нет заказов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🛍 Открыть каталог",
                    callback_data="catalog",
                )]
            ]),
        )
        await callback.answer()
        return

    status_names = {
        "pending": "⏳ Ожидает оплаты",
        "receipt_submitted": "🔍 Чек на проверке",
        "approved": "✅ Оплата подтверждена",
        "rejected": "❌ Заказ отклонён",
        "paid": "✅ Оплата подтверждена",
        "delivered": "🎉 Подписка выдана",
    }

    lines = ["📋 ТВОИ ЗАКАЗЫ\n"]

    for order in orders:
        status = status_names.get(
            order["status"],
            order["status"],
        )

        original_price = order.get("original_price") or order["price"]
        coupon_code = order.get("coupon_code")
        discount_percent = order.get("discount_percent") or 0

        if coupon_code and discount_percent:
            price_info = (
                f"Первоначальная цена: {original_price} TJS\n"
                f"🎟 Промокод: {coupon_code}\n"
                f"🏷 Скидка: {discount_percent}%\n"
                f"✅ Оплачено к оплате: {order['price']} TJS\n"
            )
        else:
            price_info = f"Сумма: {order['price']} TJS\n"

        lines.append(
            f"📦 Заказ №{order['id']}\n"
            f"Товар: {order['product']}\n"
            f"Срок: {order['duration']} мес.\n"
            f"{price_info}"
            f"Статус: {status}\n"
            f"Подписка: {order.get('delivery_text') or 'Ещё не выдана'}\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🛍 Открыть каталог",
                callback_data="catalog",
            )]
        ]),
    )
    await callback.answer()

async def main():
    database.init_db()
    print("EasyPro запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
