from pydantic import BaseModel, Field

class WebhookRequest(BaseModel):
    transaction_id: str
    order_id: int
    status: str
    amount: float
