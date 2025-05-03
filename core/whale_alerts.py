import logging
import os
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application

from api import fetch_whale_transaction, fetch_whale_transaction_for_single_token
from core.dashboard import _load_dashboard, get_tracked_whale_alert_tokens

from .dashboard import get_whale_alerts_enabled, set_whale_alerts_enabled

logger = logging.getLogger(__name__)


# Command to access Whale Alert features
async def whale_alerts_command(update: Update, context: Application) -> None:
    """Handles the /whalealerts command or button press."""
    message = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id

    # Get current toggle state
    is_enabled = get_whale_alerts_enabled(user_id)
    toggle_text = "🔴 Disable Alerts" if is_enabled else "🟢 Enable Alerts"
    toggle_data = "toggle_whale_off" if is_enabled else "toggle_whale_on"

    keyboard = [
        [
            InlineKeyboardButton(toggle_text, callback_data=toggle_data),
        ],
        [
            InlineKeyboardButton(
                "Set Alert Threshold 💰", callback_data="set_threshold"
            ),
        ],
        [
            InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        "🐳 *Whale Alert Options* ⚙️\n\n"
        f"Alerts are currently {'🟢 ON' if is_enabled else '🔴 OFF'}\n\n"
        "Set a USD threshold (default is 50,000) for future alerts.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def toggle_whale_alerts(update: Update, context: Application) -> None:
    """Handles toggling whale alerts on/off with animation."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Determine the new state from the callback data
    new_state = query.data == "toggle_whale_on"
    set_whale_alerts_enabled(user_id, new_state)

    # Show animation with whale image
    whale_image_path = os.path.join(
        os.path.dirname(__file__), "..", "assets", "whale_pepe.jpeg"
    )

    if new_state:
        # Send whale image and delete after a short delay
        image_msg = await query.message.reply_photo(
            photo=open(whale_image_path, "rb"), caption="🐳 Whale Alerts Activated! 🚀"
        )
        await whale_alerts_command(update, context)
        time.sleep(3)
        try:
            await context.bot.delete_message(
                chat_id=user_id, message_id=image_msg.message_id
            )
        except Exception as e:
            logger.warning(f"Failed to delete whale alert image: {e}")
        return

    # Update the main menu
    await whale_alerts_command(update, context)


# Set threshold (triggered by button in whale_alerts_command)
async def set_threshold_prompt(
    update: Update, context: Application, user_states: dict
) -> None:
    """Prompts the user to enter a threshold amount (handles command or callback)."""
    query = update.callback_query
    message = update.message or (query.message if query else None)
    user = update.effective_user

    if not message or not user:
        logger.warning("set_threshold_prompt couldn't find message or user.")
        return

    if query:
        await query.answer()  # Acknowledge button press

    user_id = user.id
    await message.reply_text(
        "💰 Enter your minimum USD value threshold for whale alerts (e.g., 50000), or type 'skip':"
    )
    user_states[user_id] = "awaiting_threshold"


async def whale_alert_job(application: Application):
    """Checks whale transactions for all users with alerts enabled and sends notifications."""
    dashboard = _load_dashboard()
    for user_id, user_data in dashboard.items():
        whale_alert = user_data.get("whale_alert", {})
        if whale_alert.get("enabled"):
            tracked_tokens = get_tracked_whale_alert_tokens(user_id)
            if not tracked_tokens:
                continue
            try:
                whale_threshold = whale_alert.get("threshold", 50000)
                for token_address in tracked_tokens:
                    tx = fetch_whale_transaction_for_single_token(
                        token_address, min_amount_usd=whale_threshold
                    )
                    if not tx:
                        continue
                    value_usd = tx.get("valueUsd", "0")
                    try:
                        if float(value_usd) < whale_threshold:
                            continue
                    except Exception:
                        continue
                    block_time = tx.get("blockTime")
                    token = tx.get("tokenSymbol", "Unknown Token")
                    amount = tx.get("amount", "?")
                    sender = tx.get("fromOwner", "Unknown")
                    receiver = tx.get("toOwner", "Unknown")
                    signature = tx.get("signature", "")
                    solscan_url = f"https://solscan.io/tx/{signature}"
                    alert_msg = (
                        f"🐋 *Whale Alert!* 🐋\n\n"
                        f"Token: `{token}`\n"
                        f"Amount: {amount}\n"
                        f"Value: ${float(value_usd):,.2f}\n"
                        f"From: `{sender}`\n"
                        f"To: `{receiver}`\n"
                        f"[View on Solscan]({solscan_url})"
                    )
                    try:
                        await application.bot.send_message(
                            chat_id=user_id,
                            text=alert_msg,
                            parse_mode="Markdown",
                            disable_web_page_preview=False,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send whale alert to user {user_id}: {e}"
                        )
            except BadRequest as e:
                logger.warning(f"Failed to send whale alert to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error in whale alert job for user {user_id}: {e}")
