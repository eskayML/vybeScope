import logging
import os
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application

from api import fetch_whale_transaction, fetch_whale_transaction_for_single_token
from core.dashboard import (
    _load_dashboard,
    get_token_alert_settings,
    get_tracked_whale_alert_tokens,
    set_token_alert_enabled,
    set_token_alert_threshold,
)

from .dashboard import get_whale_alerts_enabled, set_whale_alerts_enabled

logger = logging.getLogger(__name__)


# Command to access Whale Alert features
async def whale_alerts_command(update: Update, context: Application) -> None:
    """Handles the /whalealerts command or button press."""
    message = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id

    # Get current toggle state
    is_enabled = get_whale_alerts_enabled(user_id)
    tracked_tokens = get_tracked_whale_alert_tokens(user_id)
    token_settings = [
        (token, get_token_alert_settings(user_id, token)) for token in tracked_tokens
    ]

    keyboard = []
    for token, settings in token_settings:
        toggle_text = (
            f"🔴 Disable {token[:4]}..."
            if settings["enabled"]
            else f"🟢 Enable {token[:4]}..."
        )
        toggle_data = f"toggle_token_{'off' if settings['enabled'] else 'on'}:{token}"
        threshold_text = f"Set Threshold (${settings['threshold']})"
        threshold_data = f"set_token_threshold:{token}"
        keyboard.append(
            [
                InlineKeyboardButton(toggle_text, callback_data=toggle_data),
                InlineKeyboardButton(threshold_text, callback_data=threshold_data),
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start"),
        ]
    )
    reply_markup = InlineKeyboardMarkup(keyboard)

    status_lines = [
        f"{token[:6]}...: {'🟢 ON' if settings['enabled'] else '🔴 OFF'}, Threshold: ${settings['threshold']}"
        for token, settings in token_settings
    ]
    status_text = "\n".join(status_lines) if status_lines else "No tokens tracked."

    await message.reply_text(
        f"🐳 *Whale Alert Options* ⚙️\n\n{status_text}\n\nManage alerts for each token below.",
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
            tokens_dict = whale_alert.get("tokens", {})
            for token_address, settings in tokens_dict.items():
                if not settings.get("enabled", False):
                    continue
                threshold = settings.get("threshold", 5)
                try:
                    tx = fetch_whale_transaction_for_single_token(
                        token_address, min_amount_usd=threshold
                    )
                    if not tx:
                        continue
                    value_usd = tx.get("valueUsd", "0")
                    try:
                        if float(value_usd) < threshold:
                            continue
                    except Exception:
                        continue
                    block_time = tx.get("blockTime")
                    token_symbol = tx.get("tokenSymbol", "Unknown Token")
                    token_address_display = token_address
                    amount = tx.get("calculatedAmount") or tx.get("amount", "?")
                    sender = tx.get("fromOwner", "Unknown")
                    receiver = tx.get("toOwner", "Unknown")
                    signature = tx.get("signature", "")
                    solscan_url = f"https://solscan.io/tx/{signature}"
                    alert_msg = (
                        f"🐋💸 *Whale Alert!* 💸🐋\n\n"
                        f"🪙 Token: *{token_symbol}*\n"
                        f"🏷️ Address: `{token_address_display}`\n"
                        f"💰 Amount: {amount} {token_symbol}\n"
                        f"💵 Value: ${float(value_usd):,.2f}\n\n"
                        f"👤 Sender: \n`{sender}`\n\n"
                        f"👥 Receiver: \n`{receiver}`\n\n"
                        f"🔗 [View on Solscan]({solscan_url})"
                    )
                    # Add inline buttons for this token
                    alert_markup = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Disable Alert",
                                    callback_data=f"disable_alert:{token_address}",
                                ),
                                InlineKeyboardButton(
                                    "Change Threshold",
                                    callback_data=f"change_threshold:{token_address}",
                                ),
                            ]
                        ]
                    )
                    try:
                        await application.bot.send_message(
                            chat_id=user_id,
                            text=alert_msg,
                            parse_mode="Markdown",
                            disable_web_page_preview=False,
                            reply_markup=alert_markup,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send whale alert to user {user_id}: {e}"
                        )
                except BadRequest as e:
                    logger.warning(f"Failed to send whale alert to user {user_id}: {e}")
                except Exception as e:
                    logger.error(f"Error in whale alert job for user {user_id}: {e}")
