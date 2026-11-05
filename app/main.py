import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, engine, Base
from app.models import Order
from app.schemas import WebhookRequest
from app.services.payment_service import calculate_final_amount, BASE_PRICE, process_webhook_payment
from app.services.tg_bot import dp, bot
from app.services.lead_screener import background_validation_and_send

# Указываем надежный путь к шаблонам
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Создаем таблицы в БД при старте
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Запускаем бота в фоновом режиме
    polling_task = None
    if bot:
        polling_task = asyncio.create_task(dp.start_polling(bot))
    
    yield
    
    # 3. Останаваем бота при завершении работы сервера
    if polling_task:
        polling_task.cancel()

app = FastAPI(title="TG VIP Access Gateway", lifespan=lifespan)

@app.middleware("http")
async def add_localtunnel_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Bypass-Tunnel-Reminder"] = "true"
    return response

@app.get("/", response_class=HTMLResponse)
async def get_checkout(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"base_price": BASE_PRICE}
    )

@app.post("/orders/create")
async def create_order(
    tg_target: str = Form(...),
    apply_discount: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    final_amt = calculate_final_amount(apply_discount)
    new_order = Order(
        tg_target=tg_target.strip(),
        base_price=BASE_PRICE,
        discount_applied=apply_discount,
        final_amount=final_amt
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    
    return RedirectResponse(url=f"/pay/{new_order.id}", status_code=303)

@app.get("/pay/{order_id}", response_class=HTMLResponse)
async def pay_screen(order_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse(
        request=request,
        name="pay.html",
        context={"order": order}
    )

@app.post("/api/payments/webhook")
async def payment_webhook(
    payload: WebhookRequest, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    order = await process_webhook_payment(
        db=db,
        order_id=payload.order_id,
        transaction_id=payload.transaction_id,
        status=payload.status,
        amount=payload.amount
    )
    
    # Отправка чека и ключа в Telegram при успешной оплате выполняется в фоне
    if order.status.value == "paid" and order.tg_target:
        background_tasks.add_task(
            background_validation_and_send,
            tg_target=order.tg_target,
            order_id=order.id,
            amount=float(order.final_amount),
            key=order.access_key
        )
        
    return {"status": "ok", "order_status": order.status, "access_key": order.access_key}