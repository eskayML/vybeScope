import logging

from telegram.error import BadRequest

from api import fetch_whale_transactions
from core.dashboard import _load_dashboard, _save_dashboard
from core.whale_alerts import check_highest_whale_tx

logger = logging.getLogger(__name__)


async def whale_alert_job(application):
    """Checks whale transactions for all users with alerts enabled and sends notifications."""
    dashboard = _load_dashboard()
    for user_id, user_data in dashboard.items():
        whale_alert = user_data.get("whale_alert", {})
        if whale_alert.get("enabled"):
            try:
                data = fetch_whale_transactions(
                    min_amount_usd=whale_alert.get("threshold", 50000)
                )
                transactions = data.get("transfers", [])
                if not transactions:
                    continue
                highest_tx = max(
                    transactions, key=lambda tx: float(tx.get("valueUsd", 0))
                )
                tx_signature = highest_tx.get("signature")
                if tx_signature and tx_signature != whale_alert.get(
                    "last_alerted_signature"
                ):

                    class DummyQuery:
                        message = type(
                            "msg", (), {"reply_text": lambda *a, **k: None}
                        )()

                        async def answer(self):
                            pass

                    class DummyUpdate:
                        callback_query = DummyQuery()
                        effective_user = type("user", (), {"id": int(user_id)})()

                    class DummyContext:
                        bot = application.bot

                    await check_highest_whale_tx(DummyUpdate(), DummyContext())
                    dashboard[user_id]["whale_alert"]["last_alerted_signature"] = (
                        tx_signature
                    )
                    _save_dashboard(dashboard)
            except BadRequest as e:
                logger.warning(f"Failed to send whale alert to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error in whale alert job for user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error in whale alert job for user {user_id}: {e}")
