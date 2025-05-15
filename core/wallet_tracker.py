import logging
import os
import re
import time
from datetime import datetime, timedelta

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application

from api import fetch_wallet_activity, get_wallet_token_balance

from .dashboard import _load_dashboard, add_tracked_wallet, get_user_dashboard
from .utils import format_transaction_details

logger = logging.getLogger(__name__)


WALLET_TRACKING_INTERVAL_SECONDS = int(
    os.getenv("WALLET_TRACKING_INTERVAL_SECONDS", 60)
)

# Dictionary to store the latest transaction timestamp for each wallet
last_transaction_times = {}


# Check wallet activity (Prompt)
async def wallet_prompt(
    update: Update, context: Application, user_states: dict
) -> None:
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
        "🔍 Enter a Solana wallet address to track its activity (e.g., 3qArN...):"
    )
    user_states[user_id] = "awaiting_wallet"


async def process_wallet(
    user_id: int, wallet_address: str, context: Application
) -> str:  # Returns status string
    wallet_address = wallet_address.strip()
    # Check for empty input
    if not wallet_address:
        return "empty_input"  # Caller handles message and re-prompt

    # Basic validation for Solana wallet address
    if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", wallet_address):
        return "validation_error"  # Caller handles message and re-prompt

    # Send image with caption before fetching balances
    image_path = "assets/wallet_tracking_pepe.jpg"
    image_msg = None
    try:
        image_msg = await context.bot.send_photo(
            chat_id=user_id,
            photo=image_path,
            caption=f"⏳ Finding token balances for wallet `{wallet_address[:6]}...`",
        )
    except Exception as e:
        logger.warning(f"Failed to send image: {e}")

    try:
        # Call the balance function
        balance_data = await get_wallet_token_balance(wallet_address)

        # --- Extract Core Information ---
        total_value_usd_str = balance_data.get("totalTokenValueUsd", "0")
        total_value_change_1d_str = balance_data.get("totalTokenValueUsd1dChange", "0")
        token_count = balance_data.get("totalTokenCount", 0)
        tokens = balance_data.get("data", [])

        # --- Safely Convert Numbers ---
        total_value_usd = 0.0
        total_value_change_formatted = ""

        try:
            total_value_usd = float(total_value_usd_str)
        except (ValueError, TypeError):
            logger.warning(
                f"Could not convert totalTokenValueUsd '{total_value_usd_str}' to float for wallet {wallet_address}. Defaulting to 0."
            )

        try:
            total_value_change_1d = float(total_value_change_1d_str)
            change_sign = "+" if total_value_change_1d >= 0 else ""
            change_emoji = "📈" if total_value_change_1d >= 0 else "📉"
            total_value_change_formatted = (
                f"{change_emoji} {change_sign}${total_value_change_1d:,.2f} (24h)"
            )
        except (ValueError, TypeError):
            logger.warning(
                f"Could not convert totalTokenValueUsd1dChange '{total_value_change_1d_str}' to float for wallet {wallet_address}."
            )
            total_value_change_formatted = ""  # Don't show if invalid

        # --- Handle No Tokens Case ---
        if not tokens and total_value_usd == 0.0:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Track Another Wallet 🔍", callback_data="wallet_tracker"
                    )
                ],
                [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🤷‍♂️ No token balances found for wallet `{wallet_address}`.",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            # Wallet is valid but no tokens, still "processed" in terms of validation
            # Add to dashboard if it's a new valid wallet, even if empty, so user sees it.
            add_tracked_wallet(user_id, wallet_address)
            return "processed_successfully_no_tokens"

        # --- Build the Message ---
        message_text = "✅ Successfully Started Tracking!\n"
        message_text += f"💼 *Wallet:* `{wallet_address}`\n\n"
        message_text += f"💰 *Total Value:* ${total_value_usd:,.2f} USD\n"
        if total_value_change_formatted:
            message_text += f"📊 *Change (24h):* {total_value_change_formatted}\n"
        message_text += f"🪙 *Token Count:* {token_count}\n\n"
        message_text += "✨ *Tokens Held:*\n"

        if not tokens:
            message_text += (
                "- No specific token data available (might only have SOL).\n"
            )
        else:
            for token in tokens:
                symbol = token.get("symbol", "N/A")
                name = token.get("name", "Unknown Token")
                amount_str = token.get("amount", "0")
                value_usd_str = token.get("valueUsd", "0")
                price_usd_str = token.get("priceUsd", "N/A")

                # Initialize formatted strings
                amount_formatted = amount_str  # Fallback
                value_usd_formatted = "N/A"
                price_usd_formatted = "N/A"

                # Format amount (display raw value with commas)
                try:
                    amount_float = float(amount_str)
                    if amount_float == int(amount_float):
                        amount_formatted = f"{int(amount_float):,}"
                    else:
                        amount_formatted = f"{amount_float:,}"
                except (ValueError, TypeError):
                    pass

                # Format current value
                try:
                    value_usd_float = float(value_usd_str)
                    value_usd_formatted = f"${value_usd_float:,.2f}"
                except (ValueError, TypeError):
                    pass

                # Format current price
                try:
                    price_usd_float = float(price_usd_str)
                    price_usd_formatted = f"${price_usd_float:,.6f}".rstrip("0").rstrip(
                        "."
                    )
                except (ValueError, TypeError):
                    pass

                message_text += f"\n--- *{symbol}* ({name}) ---\n"
                message_text += f"   🔢 *Amount:* {amount_formatted}\n"
                message_text += f"   💲 *Value:* {value_usd_formatted} USD"
                message_text += f"\n   📈 *Price:* {price_usd_formatted}"
                message_text += "\n"

        add_tracked_wallet(user_id, wallet_address)

        keyboard = [
            [
                InlineKeyboardButton(
                    "Remove Wallet 🗑️",
                    callback_data=f"remove_wallet_{wallet_address}",
                )
            ],
            [
                InlineKeyboardButton(
                    "Track Another Wallet 🔍", callback_data="wallet_tracker"
                )
            ],
            [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        if image_msg:
            time.sleep(3)  # Optional delay for better UX
            try:
                await context.bot.delete_message(
                    chat_id=user_id, message_id=image_msg.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete image message: {e}")
        return "processed_successfully"

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Track Another Wallet 🔍", callback_data="wallet_tracker"
                    )
                ],
                [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🤷‍♂️ No token balances found for wallet `{wallet_address}` (Wallet might be new or inactive).",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        else:
            logger.error(f"HTTP error fetching balance data for {wallet_address}: {e}")
            keyboard = [
                [InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Couldn't fetch wallet balance data right now. Please ensure the API key is valid and the API is reachable.",
                reply_markup=reply_markup,
            )
        return "processing_failed_api"  # Wallet was valid, but API failed
    except requests.RequestException as e:
        logger.error(f"Network error fetching wallet data for {wallet_address}: {e}")
        keyboard = [
            [InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Network error: Couldn't connect to the API. Please check your connection.",
            reply_markup=reply_markup,
        )
        return "processing_failed_api"  # Wallet was valid, but API failed
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred processing wallet {wallet_address}: {e}"
        )  # Use logger.exception for stack trace
        keyboard = [
            [InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ An unexpected error occurred. The developers have been notified.",
            reply_markup=reply_markup,
        )
        return "processing_failed_unexpected"  # Wallet was valid, but other error


async def check_recent_transactions(wallet_address, user_id, application):
    """
    Check for recent transactions in the last 60 seconds for a specific wallet.

    Args:
        wallet_address (str): The wallet address to check
        user_id (int): The user ID who is tracking this wallet
        application (Application): The telegram bot application object
    """
    # Ensure wallet is still tracked
    if wallet_address not in get_user_dashboard(user_id).get("wallets", []):
        return
    try:
        start_date = int(
            (
                datetime.now() - timedelta(seconds=WALLET_TRACKING_INTERVAL_SECONDS)
            ).timestamp()
        )

        # Get the last known transaction time for this wallet, or initialize it
        global last_transaction_times
        last_tx_time = last_transaction_times.get(wallet_address, 0)

        # Fetch recent wallet activity using our startDate
        recent_transactions = await fetch_wallet_activity(
            wallet_address, startDate=start_date
        )

        if not recent_transactions:
            logger.debug(f"No recent transactions found for wallet {wallet_address}")
            return

        # Find new transactions - those with block time after our last recorded time
        new_transactions = []
        latest_block_time = last_tx_time

        for tx in recent_transactions:
            block_time = tx.get("blockTime", 0)

            # Update our tracking of the latest transaction time
            if block_time > latest_block_time:
                latest_block_time = block_time

            # Only include transactions that are newer than what we've seen before
            if block_time > last_tx_time:
                new_transactions.append(tx)

        # Update the last transaction time for this wallet
        if latest_block_time > last_tx_time:
            last_transaction_times[wallet_address] = latest_block_time

        # If we have new transactions, notify the user
        if new_transactions:
            logger.info(
                f"Found {len(new_transactions)} new transactions for wallet {wallet_address}, processing the first one."
            )

            # Process only the first new transaction
            first_tx = new_transactions[0]
            tx_formatted = await format_transaction_details(first_tx, wallet_address)

            # Create message text
            message = "🚨 *New Transaction Detected!*\n\n"
            message += f"💼 *Wallet:* `{wallet_address}`\n\n"
            message += tx_formatted

            # Create keyboard for the message
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Remove Wallet 🗑️",
                        callback_data=f"remove_wallet_{wallet_address}",
                    )
                ],
                [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send the notification
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
    except Exception as e:
        logger.error(
            f"Error checking recent transactions for wallet {wallet_address}: {str(e)}"
        )


async def show_recent_transactions(
    update: Update, context: Application, wallet_address: str
) -> None:
    """Fetches and displays recent transactions for a given wallet address."""
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id

    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)

    try:
        # Fetch recent activity (both sent and received)
        transactions = await fetch_wallet_activity(wallet_address)

        if not transactions:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"No recent transactions found for wallet `{wallet_address}` in the last 5 days.",
                parse_mode="Markdown",
            )
            return

        # Limit to the latest 5 transactions for brevity
        latest_transactions = transactions[:5]

        response_text = f"📜 *Recent Transactions for Wallet:* `{wallet_address}`\n\n"
        for tx in latest_transactions:
            # Ensure that only the transaction dictionary is passed
            response_text += (
                await format_transaction_details(tx, wallet_address) + "\n---\n"
            )

        keyboard = [
            [
                InlineKeyboardButton(
                    "Back to Wallet Info 🔙",
                    callback_data=f"recent_tx_back_{wallet_address}",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Always send a new message for the transaction details
        await context.bot.send_message(
            chat_id=user_id,
            text=response_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error(f"Error in show_recent_transactions for {wallet_address}: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Error fetching or displaying recent transactions for wallet `{wallet_address}`. Please try again later.",
            parse_mode="Markdown",
        )


async def wallet_tracking_job(application):
    """
    Check for recent transactions for all tracked wallets.
    This function is meant to be called periodically by the job queue in bot.py.
    """
    try:
        # Iterate over users dynamically, fetching live tracked wallets
        for user_id_str in list(_load_dashboard().keys()):
            user_id = int(user_id_str)
            wallets = get_user_dashboard(user_id).get("wallets", [])
            for wallet_address in wallets:
                await check_recent_transactions(wallet_address, user_id, application)
    except Exception as e:
        logger.error(f"Error in wallet tracking job: {str(e)}")
