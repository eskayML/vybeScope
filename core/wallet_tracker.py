import logging
import re
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application

from api import fetch_wallet_activity
from .utils import format_transaction_details

logger = logging.getLogger(__name__)

# Check wallet activity (Prompt)
async def wallet_prompt(update: Update, context: Application, user_states: dict) -> None:
    """Prompts user for wallet address (handles command or callback)."""
    query = update.callback_query
    message = update.message or (query.message if query else None)
    user = update.effective_user

    if not message or not user:
        logger.warning("wallet_prompt couldn't find message or user.")
        return

    if query:
        await query.answer()

    user_id = user.id
    await message.reply_text(
        "🔍 Enter a Solana wallet address to track its activity (e.g., 5oNDL...):"
    )
    user_states[user_id] = "awaiting_wallet"


async def process_wallet(
    user_id: int, wallet_address: str, context: Application
) -> None:
    wallet_address = wallet_address.strip()
    # Check for empty input
    if not wallet_address:
        keyboard = [
            [InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Wallet address cannot be empty! Please enter a valid Solana address.",
            reply_markup=reply_markup,
        )
        return

    # Basic validation for Solana wallet address
    if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", wallet_address):
        keyboard = [
            [
                InlineKeyboardButton(
                    "Try Another Wallet 🔍", callback_data="wallet_tracker"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Invalid Solana wallet address format.",
            reply_markup=reply_markup,
        )
        return

    await context.bot.send_message(chat_id=user_id, text=f"🔍 Fetching activity for wallet {wallet_address[:6]}...")
    try:
        data = fetch_wallet_activity(wallet_address)
        transactions = data.get("transfers", [])[:5] # Get latest 5

        if not transactions:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Track Another Wallet 🔍", callback_data="wallet_tracker"
                    )
                ],
                [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")] # Add back button
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🕒 No recent activity found for wallet `{wallet_address}`.",
                reply_markup=reply_markup, parse_mode='Markdown'
            )
            return

        message_text = f"🔍 *Recent Activity for Wallet:* `{wallet_address}`\n\n"
        for i, tx in enumerate(transactions):
            # Use the formatting function
            formatted_tx = format_transaction_details(tx)
            # Remove the header from the helper function for list view
            formatted_tx = "\n".join(formatted_tx.split('\n')[2:]) # Keep details
            message_text += f"*{i+1}. Transaction*\n{formatted_tx}\n---\n"

        # message += "\nDetails on AlphaVybe: https://alphavybe.com/"
        keyboard = [
            [
                InlineKeyboardButton(
                    "Track Another Wallet 🔍", callback_data="wallet_tracker"
                )
            ],
             [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")] # Add back button
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id, text=message_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True
        )

    except requests.RequestException as e:
        logger.error(f"Error fetching wallet data for {wallet_address}: {e}")
        keyboard = [
            [InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Couldn't fetch wallet data right now. Try again later!",
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred processing wallet {wallet_address}: {e}")
        keyboard = [[InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="❌ An unexpected error occurred.", reply_markup=reply_markup) 