import uuid
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Order, OrderStatus

BASE_PRICE = Decimal("19.99")
DISCOUNT_RATE = Decimal("0.15")

def calculate_final_amount(apply_discount: bool) -> Decimal:
    if apply_discount:
        amount = BASE_PRICE * (Decimal("1.00") - DISCOUNT_RATE)
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return BASE_PRICE

def generate_access_key() -> str:
    """Генерация ключа строго по ТЗ: KEY-XXXX-YYYY"""
    part1 = uuid.uuid4().hex[:4].upper()
    part2 = uuid.uuid4().hex[:4].upper()
    return f"KEY-{part1}-{part2}"

async def process_webhook_payment(
    db: AsyncSession,
    order_id: int,
    transaction_id: str,
    status: str,
    amount: float
) -> Order:
    # Защита от race conditions через пессимистичную блокировку
    stmt = select(Order).where(Order.id == order_id).with_for_update()
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Идемпотенция: повторная обработка возвращает текущее состояние
    if order.status == OrderStatus.PAID:
        return order

    if status == "success":
        paid_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        if paid_amount != order.final_amount:
            raise HTTPException(status_code=400, detail="Payment amount mismatch")

        order.status = OrderStatus.PAID
        order.transaction_id = transaction_id
        
        # Генерация цифрового доступа при переходе заказа в статус paid
        order.access_key = generate_access_key()

        await db.commit()
        await db.refresh(order)
    else:
        order.status = OrderStatus.FAILED
        await db.commit()

    return order