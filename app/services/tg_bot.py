import secrets
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.config import settings

logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=settings.BOT_TOKEN) if settings.BOT_TOKEN else None
dp = Dispatcher()

# Состояния для FSM (машины состояний) при оформлении заказа в боте
class OrderStates(StatesGroup):
    waiting_for_username = State()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def generate_access_key() -> str:
    """Генерация ключа доступа в формате KEY-XXXX-YYYY"""
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    return f"KEY-{part1}-{part2}"

async def send_receipt_and_key(chat_id: str | int, order_id: int, amount: float, key: str):
    """Отправка чека и ключа доступа пользователю в Telegram"""
    if not bot:
        logger.warning("BOT_TOKEN не задан. Отправка чека пропущена.")
        return

    text = (
        f"<b>✅ Оплата успешно завершена!</b>\n\n"
        f"<b>Заказ:</b> #{order_id}\n"
        f"<b>Товар:</b> VIP Доступ\n"
        f"<b>Сумма:</b> ${amount:.2f}\n\n"
        f"<b>Ваш ключ доступа:</b>\n"
        f"<code>{key}</code>"
    )

    try:
        # Проверяем, числовой ли ID или строка с цифрами
        clean_id = str(chat_id).strip()
        if clean_id.lstrip('-').isdigit():
            target_id = int(clean_id)
        else:
            target_id = clean_id if clean_id.startswith("@") else f"@{clean_id}"

        await bot.send_message(chat_id=target_id, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"Чек успешно отправлен пользователю {target_id} (Заказ #{order_id})")
    except Exception as e:
        logger.error(f"Не удалось отправить чек в Telegram для {chat_id}: {e}")


# --- ХЭНДЛЕРЫ БОТА ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Стартовое меню с выбором тарифов"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ VIP Доступ (Базовый) — $19.99", callback_data="select_plan_base")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Со скидкой 15% (-15%) — $16.99", callback_data="select_plan_discount")
    )

    await message.answer(
        f"Привет, <b>{message.from_user.first_name}</b>!\n\n"
        "Добро пожаловать в шлюз оплаты VIP-доступа.\n"
        "Выберите подходящий тариф:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data.startswith("select_plan_"))
async def process_plan_selection(callback: CallbackQuery, state: FSMContext):
    """Сохраняем выбранный тариф и просим ввести юзернейм"""
    apply_discount = "discount" in callback.data
    await state.update_data(apply_discount=apply_discount)

    amount_str = "$16.99" if apply_discount else "$19.99"

    await callback.message.edit_text(
        f"Выбран тариф ({amount_str}).\n\n"
        "Теперь введите ваш <b>Telegram Username</b> (например, <code>@username</code>) или Telegram ID, на который будет оформлен доступ:",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(OrderStates.waiting_for_username)
    await callback.answer()

@dp.message(OrderStates.waiting_for_username)
async def process_username_input(message: Message, state: FSMContext):
    """Получаем юзернейм, создаем заказ и даем ссылку на оплату"""
    user_input = message.text.strip()
    data = await state.get_data()
    apply_discount = data.get("apply_discount", False)

    # Если пользователь написал текстовый юзернейм, но оформляет со своего аккаунта —
    # привязываем его числовой chat.id для 100% гарантии доставки чека через Bot API
    tg_target = str(message.chat.id) if user_input.startswith("@") or not user_input.lstrip('-').isdigit() else user_input

    from decimal import Decimal
    from app.database import AsyncSessionLocal
    from app.models import Order
    from app.services.payment_service import calculate_final_amount, BASE_PRICE

    final_amt = calculate_final_amount(apply_discount)

    # Создаем заказ напрямую в базе данных из бота
    async with AsyncSessionLocal() as session:
        new_order = Order(
            tg_target=tg_target,
            base_price=BASE_PRICE,
            discount_applied=apply_discount,
            final_amount=final_amt
        )
        session.add(new_order)
        await session.commit()
        await session.refresh(new_order)
        order_id = new_order.id
        amount = float(new_order.final_amount)

    await state.clear()

    # Берем адрес из конфига
    base_url = getattr(settings, 'BASE_URL', '').rstrip('/')
    
    if not base_url or "localhost" in base_url or "127.0.0.1" in base_url:
        base_url = "https://prewashed-stood-bootie.ngrok-free.dev"

    pay_url = f"{base_url}/pay/{order_id}"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"💳 Оплатить (${amount:.2f})", url=pay_url)
    )

    await message.answer(
        f"✅ <b>Заказ #{order_id} успешно создан!</b>\n\n"
        f"Получатель: <code>{user_input}</code> (ID: <code>{tg_target}</code>)\n"
        f"Сумма к оплате: <b>${amount:.2f}</b>\n\n"
        "Нажмите кнопку ниже для перехода на страницу эмуляции оплаты:",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )