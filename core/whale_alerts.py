import logging
from decimal import Decimal, InvalidOperation

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application

from api import fetch_whale_transactions

from .utils import format_transaction_details

logger = logging.getLogger(__name__)

# Command to access Whale Alert features
async def whale_alerts_command(update: Update, context: Application) -> None:
    """Handles the /whalealerts command or button press."""
    message = update.callback_query.message if update.callback_query else update.message

    keyboard = [
        [
            InlineKeyboardButton("Set Alert Threshold 💰", callback_data="set_threshold"),
        ],
        [
            InlineKeyboardButton("Check Highest Tx Now 📊", callback_data="check_highest_tx"),
        ],
        [
            InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start"), # Add back button
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        "🐳 *Whale Alert Options* ⚙️\n\n"
        "Set a USD threshold for future alerts (feature pending) or check the latest single highest transaction detected.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# Set threshold (triggered by button in whale_alerts_command)
async def set_threshold_prompt(update: Update, context: Application, user_states: dict) -> None:
    """Prompts the user to enter a threshold amount (handles command or callback)."""
    query = update.callback_query
    message = update.message or (query.message if query else None)
    user = update.effective_user

    if not message or not user:
        logger.warning("set_threshold_prompt couldn't find message or user.")
        return

    if query:
        await query.answer() # Acknowledge button press

    user_id = user.id
    await message.reply_text(
        "💰 Enter your minimum USD value threshold for whale alerts (e.g., 10000), or type 'skip':"
    )
    user_states[user_id] = "awaiting_threshold"


# Check for the single highest whale transaction
async def check_highest_whale_tx(update: Update, context: Application) -> None:
    """Fetches transactions and displays the single highest one based on valueUsd."""
    query = update.callback_query
    await query.answer()
    message = query.message

    await message.reply_text("🔍 Fetching latest transactions to find the highest whale move...")

    try:
        data = fetch_whale_transactions() # Assumes this fetches recent large transfers
        transactions = data.get("transfers", [])

        if not transactions:
            keyboard = [
                [InlineKeyboardButton("Try Again 🔄", callback_data="check_highest_tx")],
                [InlineKeyboardButton("Back to Whale Options 🐳", callback_data="whale_alerts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "🕒 No recent large transactions found.",
                reply_markup=reply_markup
            )
            return

        # Find the transaction with the highest 'valueUsd'
        highest_tx = None
        max_value = Decimal('-Infinity')

        for tx in transactions:
            try:
                value_usd_str = tx.get('valueUsd', '0')
                value_usd = Decimal(value_usd_str) if value_usd_str else Decimal('0')
                if value_usd > max_value:
                    max_value = value_usd
                    highest_tx = tx
            except (InvalidOperation, TypeError):
                logger.warning(f"Could not parse valueUsd '{tx.get('valueUsd')}' for tx: {tx.get('signature')}")
                continue # Skip this transaction if valueUsd is invalid

        if highest_tx:
            response_text = format_transaction_details(highest_tx)
            # Remove the header from the helper function's output for this specific context
            response_text = "\n".join(response_text.split('\n')[2:])
            response_text = f"🐋 *Highest Whale Transaction Alert* 🚨\n\n{response_text}"

            keyboard = [
                 [InlineKeyboardButton("Check Again 🔄", callback_data="check_highest_tx")],
                 [InlineKeyboardButton("Back to Whale Options 🐳", callback_data="whale_alerts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
        else:
             # This case might occur if all transactions had invalid valueUsd
            keyboard = [
                [InlineKeyboardButton("Try Again 🔄", callback_data="check_highest_tx")],
                [InlineKeyboardButton("Back to Whale Options 🐳", callback_data="whale_alerts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "🕒 No valid transactions found to determine the highest value.",
                reply_markup=reply_markup
            )

    except requests.RequestException as e:
        logger.error(f"Error fetching Vybe API for highest tx check: {e}")
        keyboard = [
            [InlineKeyboardButton("Try Again 🔄", callback_data="check_highest_tx")],
            [InlineKeyboardButton("Back to Whale Options 🐳", callback_data="whale_alerts")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "❌ Couldn't fetch transaction data right now. Please try again.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred in check_highest_whale_tx: {e}")
        # Provide a more specific back button here
        keyboard = [[InlineKeyboardButton("Back to Whale Options 🐳", callback_data="whale_alerts")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("❌ An unexpected error occurred. Please try again later.", reply_markup=reply_markup) 