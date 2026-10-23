"""Action Agent tools: order status, refund (Stripe test mode), record update.
Keys used: DATABASE_URL, STRIPE_SECRET_KEY (refund only)."""
import stripe
from langchain_core.tools import tool

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Order

REFUND_LIMIT = 200.0  # USD. Above this a human must approve (matches refund_policy.txt)
REFUNDABLE_STATUSES = ("delivered", "cancelled")


@tool
def get_order_status(order_id: int) -> str:
    """Get the status, item, amount, ETA and refund state of an order by its order number."""
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            return f"No order found with number {order_id}."
        refund = f"Refunded (ref: {order.refund_reference})" if order.refunded else "Not refunded"
        return (f"Order {order.id}: {order.item}, amount ${order.amount:.2f}, "
                f"status: {order.status}, ETA: {order.eta}, "
                f"ship to: {order.shipping_address}, refund: {refund}, "
                f"customer: {order.customer.name} <{order.customer.email}>")
    finally:
        db.close()


@tool
def process_refund(order_id: int, amount: float) -> str:
    """Refund an order (full or partial) via Stripe test mode.
    Only delivered or cancelled orders can be refunded, only once, and only up to 200 USD.
    If the result says REFUND_NEEDS_APPROVAL, do NOT retry: escalate to a human agent."""
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            return f"No order found with number {order_id}."
        if order.refunded:
            return f"Order {order_id} was already refunded (ref: {order.refund_reference})."
        if order.status not in REFUNDABLE_STATUSES:
            return (f"Order {order_id} is '{order.status}' and cannot be refunded yet. "
                    "Only delivered or cancelled orders are refundable.")
        if amount <= 0 or amount > order.amount:
            return f"Invalid amount. Refund must be between 0 and the order amount (${order.amount:.2f})."
        if amount > REFUND_LIMIT:
            return (f"REFUND_NEEDS_APPROVAL: ${amount:.2f} is above the ${REFUND_LIMIT:.0f} limit. "
                    "A human agent must approve this refund.")
        if not settings.STRIPE_SECRET_KEY:
            return "Refund failed: Stripe key is not configured."

        stripe.api_key = settings.STRIPE_SECRET_KEY
        cents = int(round(amount * 100))
        # Seed orders have no real payment, so in TEST mode we first create a test payment,
        # then refund it. (In a real shop you would store the PaymentIntent id on the order.)
        payment = stripe.PaymentIntent.create(
            amount=cents, currency="usd", payment_method="pm_card_visa", confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={"order_id": str(order_id)},
        )
        refund = stripe.Refund.create(payment_intent=payment.id, amount=cents)

        order.refunded = True
        order.refund_reference = refund.id
        if amount >= order.amount - 0.005:  # full refund: the order status says so too
            order.status = "refunded"
        db.commit()
        return f"Refund of ${amount:.2f} for order {order_id} processed. Reference: {refund.id}"
    except Exception as e:  # Stripe/network errors
        db.rollback()
        return f"Refund failed: {e}"
    finally:
        db.close()


@tool
def update_record(order_id: int, field: str, value: str) -> str:
    """Update a customer detail linked to an order. field must be 'shipping_address'
    (only while the order is 'processing') or 'phone'. Email changes are NOT allowed here."""
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            return f"No order found with number {order_id}."
        if field == "shipping_address":
            if order.status != "processing":
                return (f"Address cannot be changed: order {order_id} is '{order.status}'. "
                        "Only orders in 'processing' status can change address.")
            order.shipping_address = value
        elif field == "phone":
            order.customer.phone = value
        else:
            return "Only 'shipping_address' and 'phone' can be updated by the assistant."
        db.commit()
        return f"Order {order_id}: {field} updated to '{value}'."
    finally:
        db.close()
