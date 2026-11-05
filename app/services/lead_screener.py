import asyncio
import random
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Order
from app.services.tg_bot import send_receipt_and_key

client = TelegramClient(
    'user_session', 
    settings.TG_API_ID, 
    settings.TG_API_HASH
)

async def background_validation_and_send(tg_target: str, order_id: int, amount: float, key: str):
    """
    Фоновый парсинг метаданных профиля (Lead Screening),
    сохранение их в БД и отправка чека с ключом доступа.
    """
    # 1. Обход антифрод-алгоритмов платформы (динамическая задержка)
    await asyncio.sleep(random.uniform(2.5, 5.5))
    
    metadata = {}
    try:
        await client.connect()
        if await client.is_user_authorized():
            # Если целевая строка состоит из цифр (числовой ID)
            target = int(tg_target) if tg_target.lstrip('-').isdigit() else tg_target.strip()
            user = await client.get_entity(target)
            full_user = await client(GetFullUserRequest(user))
            
            metadata = {
                "bio": full_user.full_user.about,
                "has_avatar": bool(user.photo),
                "last_online": str(user.status)
            }
            print(f"[Lead Screening] Данные успешно собраны: {metadata}")
    except Exception as e:
        print(f"[Lead Screening] Ошибка при проверке через Telethon: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()

    # Сохраняем собранные метаданные в БД
    if metadata:
        async with AsyncSessionLocal() as session:
            order = await session.get(Order, order_id)
            if order:
                order.lead_metadata = metadata
                await session.commit()

    # 2. Выдача доступа (отправка чека через aiogram)
    await send_receipt_and_key(
        chat_id=tg_target, 
        order_id=order_id, 
        amount=amount, 
        key=key
    )