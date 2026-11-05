import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_target: Mapped[str] = mapped_column(String(255), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_applied: Mapped[bool] = mapped_column(default=False)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    
    transaction_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lead_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_orders_status", "status"),
    )
