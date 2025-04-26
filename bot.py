import logging
import os

import telegram
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.request import HTTPXRequest
import requests
import re
import pytz

# Load environment variables from .env file
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
VYBE_API_KEY = os.getenv("VYBE_API_KEY")

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Vybe API endpoints
VYBE_TRANSACTIONS_URL = "https://api.vybenetwork.xyz/token/transfers?min_amount_usd=5000&limit=10"
VYBE_TOKEN_URL = "https://api.vybenetwork.xyz/token"  # Base URL for specific token (without {mintAddress})
VYBE_WALLET_URL = "https://api.vybenetwork.xyz/token/transfers"  # Use token/transfers with address filter

# Store user thresholds and states in memory
user_thresholds = {}
user_states = {}

# Token symbol to Solana token address mapping
TOKEN_ADDRESS_MAP = {
    "SOL": "So11111111111111111111111111111111111111112",  # SOL's wrapped address
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}

# Welcome message with crypto theme and inline keyboard
async def start(update: Update, context: "Application") -> None:
    user = update.effective_user.first_name
    welcome_message = (
        f"🚀 Welcome to VybeWhaleAlertBot, {user}! 🐳\n"
        "Catch massive on-chain moves with Vybe-powered analytics! 📈\n\n"
        "I track whale transactions, token stats, and wallet activity. "
        "Each alert links to AlphaVybe for deeper insights. 💰\n\n"
        "Choose an action below to get started! 👇"
    )

    # Inline keyboard for the start menu
    keyboard = [
        [
            InlineKeyboardButton("Set Threshold 🐋", callback_data="set_threshold"),
            InlineKeyboardButton("Check Whale Alerts 📊", callback_data="check_whales"),
        ],
        [
            InlineKeyboardButton("Token Stats 📈", callback_data="token_stats"),
            InlineKeyboardButton("Wallet Tracker 🔍", callback_data="wallet_tracker"),
        ],
        [InlineKeyboardButton("Help ℹ️", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    # Prompt for initial threshold if not set
    user_id = update.effective_user.id
    if user_id not in user_thresholds:
        await update.message.reply_text(
            "📊 Let’s set a default threshold for whale alerts (e.g., 10000). "
            "Or type 'skip' to set it later with /threshold:"
        )
        user_states[user_id] = "awaiting_threshold"

# Set threshold
async def threshold(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        "📊 Enter your threshold amount for whale alerts (e.g., 10000):"
    )
    user_states[user_id] = "awaiting_threshold"

# Check for whale transactions
async def check_whales(context: "Application", user_id: int = None, update: Update = None) -> None:
    try:
        headers = {"X-API-Key": VYBE_API_KEY}
        response = requests.get(VYBE_TRANSACTIONS_URL, headers=headers)
        logger.info(f"Transactions API Response: {response.status_code} - {response.text}")
        response.raise_for_status()

        data = response.json()
        # Log the full response for debugging
        logger.info(f"Transactions API Data: {data}")
        # Try both "transfers" and "transactions" keys to handle different response formats
        transactions = data.get("transfers", data.get("transactions", []))  # Adjusted for flexibility

        if not transactions:
            logger.info("No transactions found in the response.")
            if user_id:
                keyboard = [
                    [
                        InlineKeyboardButton("Check Again 🔄", callback_data="check_whales"),
                        InlineKeyboardButton("Set New Threshold 🐋", callback_data="set_threshold"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🕒 No whale transactions found at the moment.\n"
                        "What would you like to do next? 👇"
                    ),
                    reply_markup=reply_markup
                )
            return

        if user_id:
            if user_id not in user_thresholds:
                keyboard = [[InlineKeyboardButton("Set Threshold 🐋", callback_data="set_threshold")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(
                    chat_id=user_id,
                    text="📊 Please set a threshold first using /threshold!\nOr click below to set it now:",
                    reply_markup=reply_markup
                )
                return

            threshold = user_thresholds[user_id]
            found = False
            for tx in transactions:
                amount = tx.get("amount_usd", 0)
                if amount >= threshold:
                    found = True
                    token_symbol = tx.get("token_symbol", "Unknown Token")
                    keyboard = [
                        [
                            InlineKeyboardButton("Check Again 🔄", callback_data="check_whales"),
                            InlineKeyboardButton("Set New Threshold 🐋", callback_data="set_threshold"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🚨 Whale Alert! 🐋\n"
                            f"Transaction: ${amount} ({token_symbol})\n"
                            f"Details on AlphaVybe: https://alphavybe.com/\n\n"
                            "What would you like to do next? 👇"
                        ),
                        reply_markup=reply_markup
                    )
            if not found and user_id:
                keyboard = [
                    [
                        InlineKeyboardButton("Check Again 🔄", callback_data="check_whales"),
                        InlineKeyboardButton("Set New Threshold 🐋", callback_data="set_threshold"),
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🕒 No whale transactions above your threshold right now.\n"
                        "What would you like to do next? 👇"
                    ),
                    reply_markup=reply_markup
                )
            return

        for user_id, threshold in user_thresholds.items():
            for tx in transactions:
                amount = tx.get("amount_usd", 0)
                if amount >= threshold:
                    token_symbol = tx.get("token_symbol", "Unknown Token")
                    keyboard = [
                        [
                            InlineKeyboardButton("Check Again 🔄", callback_data="check_whales"),
                            InlineKeyboardButton("Set New Threshold 🐋", callback_data="set_threshold"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🚨 Whale Alert! 🐋\n"
                            f"Transaction: ${amount} ({token_symbol})\n"
                            f"Details on AlphaVybe: https://alphavybe.com/\n\n"
                            "What would you like to do next? 👇"
                        ),
                        reply_markup=reply_markup
                    )

    except requests.RequestException as e:
        logger.error(f"Error fetching Vybe API: {e}")
        if user_id:
            keyboard = [[InlineKeyboardButton("Try Again 🔄", callback_data="check_whales")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ Couldn’t fetch transaction data right now. Try again later!\n"
                    "Or click below to retry:"
                ),
                reply_markup=reply_markup
            )

# Manual check command
async def check(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    await check_whales(context, user_id, update)

# Check token stats
async def token(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        "📈 Enter a token symbol to check its stats (e.g., SOL or USDC):"
    )
    user_states[user_id] = "awaiting_token"

async def process_token(user_id: int, token_symbol: str, context: "Application") -> None:
    # Validate token symbol (basic check for letters only)
    if not re.match(r"^[A-Za-z]+$", token_symbol):
        keyboard = [[InlineKeyboardButton("Try Another Token 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Invalid token symbol! Please use letters only (e.g., SOL).\nClick below to try another token:",
            reply_markup=reply_markup
        )
        return

    # Map token symbol to Solana token address
    token_symbol = token_symbol.upper()
    if token_symbol not in TOKEN_ADDRESS_MAP:
        keyboard = [[InlineKeyboardButton("Try Another Token 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Token {token_symbol} not supported! Try SOL, USDC, or USDT.\nClick below to try another token:",
            reply_markup=reply_markup
        )
        return

    token_address = TOKEN_ADDRESS_MAP[token_symbol]

    try:
        headers = {"X-API-Key": VYBE_API_KEY}
        # Fetch the specific token details
        response = requests.get(f"{VYBE_TOKEN_URL}/{token_address}", headers=headers)
        logger.info(f"Token API Response: {response.status_code} - {response.text}")
        response.raise_for_status()

        data = response.json()
        price = data.get("price", "N/A")
        change_24h = data.get("change_24h", "N/A")

        # Add trend indicator
        trend = ""
        try:
            change_value = float(change_24h)
            if change_value > 0:
                trend = "📈 (Upward Trend)"
            elif change_value < 0:
                trend = "📉 (Downward Trend)"
            else:
                trend = "➡️ (Stable)"
        except (ValueError, TypeError):
            trend = "❓ (Trend Unavailable)"

        keyboard = [[InlineKeyboardButton("Check Another Token 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📊 {token_symbol} Stats:\n"
                f"Price: ${price}\n"
                f"24h Change: {change_24h}% {trend}\n"
                f"Details on AlphaVybe: https://alphavybe.com/\n\n"
                "What would you like to do next? 👇"
            ),
            reply_markup=reply_markup
        )
    except requests.RequestException as e:
        logger.error(f"Error fetching token data: {e}")
        keyboard = [[InlineKeyboardButton("Try Again 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Couldn’t fetch token data right now. Try again later!\nClick below to retry:",
            reply_markup=reply_markup
        )

# Check wallet activity
async def wallet(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        "🔍 Enter a Solana wallet address to track its activity (e.g., 5oNDL...):"
    )
    user_states[user_id] = "awaiting_wallet"

async def process_wallet(user_id: int, wallet_address: str, context: "Application", awaited=None) -> None:
    # Check for empty input
    if not wallet_address or wallet_address.strip() == "":
        keyboard = [[InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Wallet address cannot be empty! Please enter a valid Solana address (e.g., 5oNDL...).\nClick below to try again:",
            reply_markup=reply_markup
        )
        return

    # Basic validation for Solana wallet address (base58, typically 32-44 characters)
    if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", wallet_address):
        keyboard = [[InlineKeyboardButton("Try Another Wallet 🔍", callback_data="wallet_tracker")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Invalid Solana wallet address! It should be 32-44 characters long and use base58 (e.g., 5oNDL...).\nClick below to try another wallet:",
            reply_markup=reply_markup
        )
        return

    try:
        headers = {"X-API-Key": VYBE_API_KEY}
        # Use the token/transfers endpoint with an address filter
        wallet_url = f"{VYBE_WALLET_URL}?address={wallet_address}&limit=5"
        response = requests.get(wallet_url, headers=headers)
        logger.info(f"Wallet API Response: {response.status_code} - {response.text}")
        response.raise_for_status()

        data = response.json()
        transactions = data.get("transfers", data.get("transactions", []))[:3]  # Adjusted for flexibility

        if not transactions:
            keyboard = [[InlineKeyboardButton("Track Another Wallet 🔍", callback_data="wallet_tracker")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔍 No recent activity for wallet {wallet_address}.\nClick below to track another wallet:",
                reply_markup=reply_markup
            )
            return

        message = f"🔍 Wallet Activity for {wallet_address}:\n\n"
        for tx in transactions:
            amount = tx.get("amount_usd", "N/A")
            message += f"💸 Transaction: ${amount}\n"

        message += "\nDetails on AlphaVybe: https://alphavybe.com/\n\nWhat would you like to do next? 👇"
        keyboard = [[InlineKeyboardButton("Track Another Wallet 🔍", callback_data="wallet_tracker")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=reply_markup
        )

    except requests.RequestException as e:
        logger.error(f"Error fetching wallet data: {e}")
        keyboard = [[InlineKeyboardButton("Try Again 🔍", callback_data="wallet_tracker")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Couldn’t fetch wallet data right now. Try again later!\nClick below to retry:",
            reply_markup=reply_markup
        )

# Help command with crypto theme
async def help_command(update: Update, context: "Application") -> None:
    help_message = (
        "🐳 WhaleAlertBot Help 📈\n\n"
        "I’m your go-to for on-chain crypto insights! Here’s what I can do:\n\n"
        "- Track whale moves with a custom threshold 🐋\n"
        "- Check token prices and stats 📊\n"
        "- Monitor wallet activity 🔍\n"
        "- Get real-time alerts with AlphaVybe links 💰\n\n"
        "Choose an action below to get started! 👇"
    )
    keyboard = [
        [
            InlineKeyboardButton("Set Threshold 🐋", callback_data="set_threshold"),
            InlineKeyboardButton("Check Whale Alerts 📊", callback_data="check_whales"),
        ],
        [
            InlineKeyboardButton("Token Stats 📈", callback_data="token_stats"),
            InlineKeyboardButton("Wallet Tracker 🔍", callback_data="wallet_tracker"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(help_message, reply_markup=reply_markup)

# Handle text input (threshold, token, wallet)
async def handle_text(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    text = update.message.text.lower()

    if user_id not in user_states:
        await update.message.reply_text(
            "🚀 Type / to see all commands or use the buttons to get started!"
        )
        return

    state = user_states[user_id]

    if state == "awaiting_threshold":
        if text == "skip":
            user_states.pop(user_id, None)
            keyboard = [[InlineKeyboardButton("Set Threshold Later 🐋", callback_data="set_threshold")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⏭️ Skipped setting a threshold. You can set it later with /threshold.\nClick below if you’d like to set it now:",
                reply_markup=reply_markup
            )
            return
        try:
            threshold = float(text)
            if threshold <= 0:
                await update.message.reply_text(
                    "❌ Threshold must be a positive number! Try again or type 'skip' to set it later:"
                )
                return
            user_thresholds[user_id] = threshold
            user_states.pop(user_id, None)
            keyboard = [[InlineKeyboardButton("Check Whale Alerts 📊", callback_data="check_whales")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Threshold set to ${threshold}! I’ll alert you for whale moves above this amount. 🐋\nClick below to check for whale alerts now:",
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount! Please enter a number (e.g., 10000) or type 'skip' to set it later:"
            )

    elif state == "awaiting_token":
        user_states.pop(user_id, None)
        token_symbol = text.upper()
        await process_token(user_id, token_symbol, context)

    elif state == "awaiting_wallet":
        user_states.pop(user_id, None)
        wallet_address = text
        await process_wallet(user_id, wallet_address, context)

# Handle inline keyboard button clicks
async def button_handler(update: Update, context: "Application") -> None:
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    user_id = query.from_user.id
    callback_data = query.data

    if callback_data == "set_threshold":
        await query.message.reply_text(
            "📊 Enter your threshold amount for whale alerts (e.g., 10000):"
        )
        user_states[user_id] = "awaiting_threshold"
    elif callback_data == "check_whales":
        await check_whales(context, user_id, update)
    elif callback_data == "token_stats":
        await query.message.reply_text(
            "📈 Enter a token symbol to check its stats (e.g., SOL or USDC):"
        )
        user_states[user_id] = "awaiting_token"
    elif callback_data == "wallet_tracker":
        await query.message.reply_text(
            "🔍 Enter a Solana wallet address to track its activity (e.g., 5oNDL...):"
        )
        user_states[user_id] = "awaiting_wallet"
    elif callback_data == "help":
        await help_command(update, context)

# Error handler
async def error_handler(update: Update, context: "Application") -> None:
    logger.error(f"Update {update} caused error {context.error}")
    # Avoid sending a message if the error is network-related
    if isinstance(context.error, telegram.error.TimedOut):
        logger.warning("Skipping message send due to TimedOut error.")
        return
    if update and update.message:
        keyboard = [[InlineKeyboardButton("Get Help ℹ️", callback_data="help")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "❌ An error occurred. Please try again or get help.\nClick below for assistance:",
            reply_markup=reply_markup
        )

# Main function to start the bot
def main() -> None:
    # Create the Application instance with a custom HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=10,
        read_timeout=10.0,
        connect_timeout=10.0,
    )
    application = Application.builder().token(TELEGRAM_TOKEN).request(request).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("threshold", threshold))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("token", token))
    application.add_handler(CommandHandler("wallet", wallet))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_error_handler(error_handler)

    # Set the scheduler timezone to UTC+1 (adjust based on your actual timezone)
    application.job_queue.scheduler.configure(timezone=pytz.timezone("Etc/GMT-1"))

    # Schedule whale checks every 120 seconds
    application.job_queue.run_repeating(check_whales, interval=120, first=0)

    logger.info("Starting WhaleAlertBot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()