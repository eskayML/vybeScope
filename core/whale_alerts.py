import logging
import os
import re  # Added import
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import CallbackContext  # Modified import

from api import fetch_whale_transaction_for_single_token  # Modified
from core.dashboard import (
    _load_dashboard,
    add_tracked_whale_alert_token,
    get_token_alert_settings,
    get_tracked_whale_alert_tokens,
    remove_tracked_whale_alert_token,  # Added
)

logger = logging.getLogger(__name__)


# Command to access Whale Alert features
async def whale_alerts_command(
    update: Update, context: CallbackContext
) -> None:  # Modified context type
    """Handles the /whalealerts command or button press."""
    message = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id

    # Get tracked tokens and their settings
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
        delete_text = "🗑️"  # Use regular string instead of f-string
        delete_data = f"delete_token_alert:{token}"  # Added
        keyboard.append(
            [
                InlineKeyboardButton(toggle_text, callback_data=toggle_data),
                InlineKeyboardButton(threshold_text, callback_data=threshold_data),
                InlineKeyboardButton(delete_text, callback_data=delete_data),  # Added
            ]
        )
    # Add Whale Alert button
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Add Whale Alert", callback_data="dashboard_add_whale_alert"
            ),
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


# Set threshold (triggered by button in whale_alerts_command)
async def set_threshold_prompt(
    update: Update,
    context: CallbackContext,
    user_states: dict,  # Modified context type
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

    token_address = None
    if query and query.data:
        if query.data.startswith("set_token_threshold:"):
            token_address = query.data.split(":", 1)[1]
        elif query.data.startswith(
            "change_threshold:"
        ):  # Handles callback from alert message
            token_address = query.data.split(":", 1)[1]

    if token_address:
        # This is the flow for modifying a specific token's threshold
        await message.reply_text(
            f"💰 Enter new threshold for token `{token_address[:6]}...` (e.g., 50000)"
        )
        user_states[user_id] = f"awaiting_token_threshold_{token_address}"
    else:
        # This is the flow for the generic /threshold command or other contexts
        await message.reply_text(
            "💰 Enter your minimum USD value threshold for whale alerts (e.g., 50000)"
        )
        user_states[user_id] = "awaiting_threshold"  # The old generic state


async def whale_alert_job(context: CallbackContext):  # Modified signature
    """Checks whale transactions for all users with alerts enabled and sends notifications."""
    application = context.job.data  # Get Application instance from job context
    dashboard = _load_dashboard()
    for user_id_str in list(dashboard.keys()):
        user_id = int(user_id_str)
        # Iterate live tokens list so removals/disables skip fetch
        for token_address in get_tracked_whale_alert_tokens(user_id):
            settings = get_token_alert_settings(user_id, token_address)
            if not settings.get("enabled", False):
                continue
            threshold = settings.get("threshold", 50000)
            try:
                # Re-check still enabled before API call
                settings = get_token_alert_settings(user_id, token_address)
                if not settings.get("enabled", False):
                    continue
                tx = await fetch_whale_transaction_for_single_token(
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
                token_symbol = tx.get("tokenSymbol", "Unknown Token")
                token_address_display = token_address
                amount = tx.get("calculatedAmount") or tx.get("amount", "?")
                sender = tx.get("senderAddress", "Unknown")
                receiver = tx.get("receiverAddress", "Unknown")
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
                # Add inline buttons for this token (show threshold in button)
                alert_markup = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"{'🔴 Disable' if settings.get('enabled', False) else '🟢 Enable'} {token_address[:4]}...",
                                callback_data=f"toggle_token_{'off' if settings.get('enabled', False) else 'on'}:{token_address}",
                            ),
                            InlineKeyboardButton(
                                f"Set Threshold (${settings.get('threshold', 0)})",
                                callback_data=f"change_threshold:{token_address}",
                            ),
                        ]
                    ]
                )
                # After computing tx and before sending, re-validate tracking status
                # Cancel if user disabled or removed this alert
                current_tokens = get_tracked_whale_alert_tokens(user_id)
                if token_address not in current_tokens:
                    continue
                current_settings = get_token_alert_settings(user_id, token_address)
                if not current_settings.get("enabled", False):
                    continue

                try:
                    await application.bot.send_message(
                        chat_id=user_id,
                        text=alert_msg,
                        parse_mode="Markdown",
                        disable_web_page_preview=False,
                        reply_markup=alert_markup,
                    )
                except Exception as e:
                    logger.error(f"Failed to send whale alert to user {user_id}: {e}")
            except BadRequest as e:
                logger.warning(f"Failed to send whale alert to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error in whale alert job for user {user_id}: {e}")


# Handler for Track Whale Alerts button from token stats
async def track_token_whale_alert(
    update: Update, context: CallbackContext
) -> None:  # Modified context type
    """Handles adding a token to whale alerts from token stats screen."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Extract token address from callback data
    # Format is "track_whale_alert_{token_address}"
    token_address = query.data.replace("track_whale_alert_", "")

    # Basic validation for Solana token address
    if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token_address):
        await query.message.reply_text(
            "❌ Invalid Solana token address format. Please ensure it is a valid address."
        )
        # Optionally, reshow the whale alerts command or a try again button
        await whale_alerts_command(update, context)
        return

    # Add the token to whale alerts with default settings
    added = add_tracked_whale_alert_token(user_id, token_address)

    # Show feedback to user
    if added:
        # Show animation with whale image
        whale_image_path = os.path.join(
            os.path.dirname(__file__), "..", "assets", "whale_pepe.jpeg"
        )
        image_msg = await query.message.reply_photo(
            photo=open(whale_image_path, "rb"),
            caption="🐳 Token added to Whale Alerts! 🚀\n\nYou'll now receive alerts for large transactions of this token.",
        )

        # Show the whale alerts screen with the updated token
        await whale_alerts_command(update, context)

        # Delete the image after a short delay
        time.sleep(3)
        try:
            await context.bot.delete_message(
                chat_id=user_id, message_id=image_msg.message_id
            )
        except Exception as e:
            logger.warning(f"Failed to delete whale alert image: {e}")
    else:
        await query.message.reply_text(
            "This token is already in your whale alerts! 🐳\n"
        )
        await whale_alerts_command(update, context)


# Handler for Remove Whale Alert button
async def remove_whale_alert_handler(
    update: Update, context: CallbackContext
) -> None:  # Modified context type
    """Handles removing a specific whale alert token."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Extract token address from callback data
    # Format is "delete_token_alert:{token_address}"
    token_address = query.data.replace("delete_token_alert:", "")

    removed = remove_tracked_whale_alert_token(user_id, token_address)

    if removed:
        await query.message.reply_text(
            f"🗑️ Whale alert for token `{token_address}` removed."
        )
    else:
        await query.message.reply_text(
            f"Could not find whale alert for token `{token_address}`."
        )

    # Refresh the whale alerts menu
    await whale_alerts_command(update, context)
