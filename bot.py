import logging
import os
import re
from decimal import Decimal, InvalidOperation

import pytz
import requests
import telegram
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from api import fetch_token_stats, fetch_transactions, fetch_wallet_activity

# Load environment variables from .env file
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
VYBE_API_KEY = os.getenv("VYBE_API_KEY")

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Vybe API endpoints
VYBE_TRANSACTIONS_URL = (
    "https://api.vybenetwork.xyz/token/transfers?min_amount_usd=5000&limit=10"
)
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

# --- Helper Function to Format Transaction ---
def format_transaction_details(tx: dict) -> str:
    """Formats the details of a single transaction dictionary into a readable string."""
    try:
        # Safely convert valueUsd to Decimal for formatting
        value_usd_str = tx.get('valueUsd', '0')
        value_usd = Decimal(value_usd_str) if value_usd_str else Decimal('0')
        # Format currency
        formatted_value = f"${value_usd:,.2f}" # Format with commas and 2 decimal places
    except (InvalidOperation, TypeError):
         formatted_value = f"${tx.get('valueUsd', 'N/A')}" # Fallback if conversion fails

    # Safely get other fields with fallbacks
    signature = tx.get('signature', 'N/A')
    sender = tx.get('senderAddress', 'N/A')
    receiver = tx.get('receiverAddress', 'N/A')
    # Construct the Solana Explorer link for the signature
    explorer_link = f"https://solscan.io/tx/{signature}" if signature != 'N/A' else 'N/A'
    # Format amount and symbol (assuming 'calculatedAmount' and 'symbol' might exist)
    amount_str = tx.get('calculatedAmount', 'N/A')
    symbol = tx.get('symbol', tx.get('mintAddress', 'Unknown Token')) # Prefer symbol if available
    amount_display = f"{amount_str} {symbol}" if amount_str != 'N/A' else 'N/A'


    return (
        f"🐋 *Highest Whale Transaction Alert* 🚨\n\n"
        f"💰 *Value (USD):* {formatted_value}\n"
        f"📊 *Amount:* {amount_display}\n"
        f"🔗 *Signature:* [{signature[:8]}...{signature[-8:]}]({explorer_link})\n"
        f"📤 *Sender:* `{sender}`\n"
        f"📥 *Receiver:* `{receiver}`\n\n"
        # f"🕒 *Time:* {datetime.fromtimestamp(tx.get('blockTime', 0)).strftime('%Y-%m-%d %H:%M:%S UTC') if tx.get('blockTime') else 'N/A'}\n" # Optional: Add timestamp
        f"More details available via explorer link."
    )

# --- Command Handlers ---

# Welcome message with updated inline keyboard
async def start(update: Update, context: "Application") -> None:
    user = update.effective_user.first_name
    welcome_message = (
        f"🚀 Welcome to VybeAgent, {user}! 🐳\n"
        "Track whale alerts, token stats, and wallet activity.\n\n"
        "Choose an action below to get started! 👇"
    )

    # Updated Inline keyboard for the start menu
    keyboard = [
        [
            InlineKeyboardButton("Whale Alerts 🐋", callback_data="whale_alerts"),
            InlineKeyboardButton("Wallet Tracker 🔍", callback_data="wallet_tracker"),
        ],
        [
            InlineKeyboardButton("Token Stats 📈", callback_data="token_stats"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Try sending the photo first
    try:
        await update.message.reply_photo(photo=open("assets/vybe_banner.png", "rb"))
    except FileNotFoundError:
        logger.error("Error: assets/vybe_banner.png not found. Skipping photo.")
    except Exception as e:
        logger.error(f"Error sending start photo: {e}. Skipping photo.")

    # Always send the welcome message with keyboard afterwards
    await update.message.reply_text(
        text=welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


# Command to access Whale Alert features
async def whale_alerts_command(update: Update, context: "Application") -> None:
    """Handles the /whalealerts command or button press."""
    message = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id

    keyboard = [
        [
            InlineKeyboardButton("Set Alert Threshold 💰", callback_data="set_threshold"),
        ],
        [
            InlineKeyboardButton("Check Highest Tx Now 📊", callback_data="check_highest_tx"),
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
async def set_threshold_prompt(update: Update, context: "Application") -> None:
    """Prompts the user to enter a threshold amount."""
    query = update.callback_query
    await query.answer() # Acknowledge button press
    user_id = query.from_user.id
    await query.message.reply_text(
        "💰 Enter your minimum USD value threshold for whale alerts (e.g., 10000):"
    )
    user_states[user_id] = "awaiting_threshold"


# Check for the single highest whale transaction
async def check_highest_whale_tx(update: Update, context: "Application") -> None:
    """Fetches transactions and displays the single highest one based on valueUsd."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    message = query.message

    await message.reply_text("🔍 Fetching latest transactions to find the highest whale move...")

    try:
        data = fetch_transactions() # Assumes this fetches recent large transfers
        transactions = data.get("transfers", [])

        if not transactions:
            keyboard = [
                [InlineKeyboardButton("Try Again 🔄", callback_data="check_highest_tx")]
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
                value_usd = Decimal(tx.get('valueUsd', '0'))
                if value_usd > max_value:
                    max_value = value_usd
                    highest_tx = tx
            except (InvalidOperation, TypeError):
                logger.warning(f"Could not parse valueUsd '{tx.get('valueUsd')}' for tx: {tx.get('signature')}")
                continue # Skip this transaction if valueUsd is invalid

        if highest_tx:
            response_text = format_transaction_details(highest_tx)
            keyboard = [
                 [InlineKeyboardButton("Check Again 🔄", callback_data="check_highest_tx")],
                 [InlineKeyboardButton("Back to Whale Options 🐳", callback_data="whale_alerts")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
        else:
             # This case might occur if all transactions had invalid valueUsd
            keyboard = [
                [InlineKeyboardButton("Try Again 🔄", callback_data="check_highest_tx")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "🕒 No valid transactions found to determine the highest value.",
                reply_markup=reply_markup
            )

    except requests.RequestException as e:
        logger.error(f"Error fetching Vybe API for highest tx check: {e}")
        keyboard = [
            [InlineKeyboardButton("Try Again 🔄", callback_data="check_highest_tx")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "❌ Couldn't fetch transaction data right now. Please try again.",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred in check_highest_whale_tx: {e}")
        await message.reply_text("❌ An unexpected error occurred. Please try again later.")


# --- Existing Commands (Token, Wallet, Help) ---
# Keep threshold command for potential direct access, but primary access is via button
async def threshold(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        "💰 Enter your minimum USD value threshold for whale alerts (e.g., 10000):"
    )
    user_states[user_id] = "awaiting_threshold"


# Renamed old check_whales for clarity, now check_highest_whale_tx handles the user-facing check
# The old check_whales logic for periodic checks/threshold filtering is removed for now.
# async def check_whales(...) -> None: ... (Removed/Replaced)

# Manual check command - repurposed slightly or could be removed if only button access desired.
# For now, let's make it trigger the whale alert options menu.
async def check(update: Update, context: "Application") -> None:
    # user_id = update.effective_user.id
    # await check_highest_whale_tx(update, context) # Or directly check highest? 
    await whale_alerts_command(update, context) # Show options menu instead


# Check token stats (Prompt)
async def token_prompt(update: Update, context: "Application") -> None:
    message = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id
    await message.reply_text(
        "📈 Enter a token symbol or contract address to check its stats (e.g., SOL or EPjF...):"
    )
    user_states[user_id] = "awaiting_token"


async def process_token(
    user_id: int, token_input: str, context: "Application"
) -> None:
    # Improved logic: Check if it's a symbol OR a potential address
    token_input = token_input.strip()
    token_address = None
    token_symbol = None

    # Simple check if it looks like an address (Base58, > 30 chars)
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token_input):
        token_address = token_input
        # We might not know the symbol initially from just the address
        token_symbol = token_address[:6] + "..." # Placeholder symbol
    else:
        # Assume it's a symbol
        token_symbol = token_input.upper()
        if token_symbol in TOKEN_ADDRESS_MAP:
            token_address = TOKEN_ADDRESS_MAP[token_symbol]
        else:
            # Try fetching by symbol directly if API supports it, otherwise error
            # For now, let's stick to the known map or direct address input
            keyboard = [
                [InlineKeyboardButton("Try Another Token/Address 📈", callback_data="token_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Unknown token symbol: {token_symbol}. Please provide a known symbol (SOL, USDC, USDT) or the full contract address.",
                reply_markup=reply_markup,
            )
            return

    if not token_address:
         # This case should ideally be caught above, but as a safeguard:
        await context.bot.send_message(chat_id=user_id, text="❌ Invalid input. Please enter a token symbol or contract address.")
        return

    # Fetch stats using the determined token_address
    await context.bot.send_message(chat_id=user_id, text=f"🔍 Fetching stats for {token_symbol} ({token_address})...")
    try:
        # Assuming fetch_token_stats takes the address
        data = fetch_token_stats(token_address)
        price = data.get("priceUsd", data.get("price", "N/A")) # Check for priceUsd field
        change_24h = data.get("priceChange24h", data.get("change_24h", "N/A")) # Check specific field names
        volume_24h = data.get("volume24h", "N/A") # Add volume
        market_cap = data.get("marketCap", "N/A") # Add market cap

        # Add trend indicator
        trend = ""
        try:
            change_value = float(change_24h)
            if change_value > 0:
                trend = "📈"
            elif change_value < 0:
                trend = "📉"
            else:
                trend = "➡️"
        except (ValueError, TypeError):
            change_24h = "N/A" # Ensure change is N/A if conversion fails
            trend = "❓"

        # Format numbers nicely
        def format_num(n, default="N/A"):
            try:
                return f"{float(n):,.2f}" if n is not None else default
            except (ValueError, TypeError):
                return default

        price_str = f"${format_num(price)}"
        volume_str = f"${format_num(volume_24h)}"
        mc_str = f"${format_num(market_cap)}"

        # Use the actual symbol fetched if available, otherwise stick with input/placeholder
        fetched_symbol = data.get("symbol", token_symbol)

        keyboard = [
            [
                InlineKeyboardButton(
                    "Check Another Token/Address 📈", callback_data="token_stats"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"📊 *{fetched_symbol} Stats* ({token_address[:4]}...{token_address[-4:]})\n\n"
                f"Price: {price_str}\n"
                f"24h Change: {format_num(change_24h, 'N/A')}% {trend}\n"
                f"24h Volume: {volume_str}\n"
                f"Market Cap: {mc_str}\n\n"
                # f"Details on AlphaVybe: https://alphavybe.com/" # Link might need token context
            ),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except requests.RequestException as e:
        logger.error(f"Error fetching token data for {token_address}: {e}")
        keyboard = [[InlineKeyboardButton("Try Again 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Couldn't fetch token data for {token_symbol}. Try again later!",
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred processing token {token_address}: {e}")
        await context.bot.send_message(chat_id=user_id, text="❌ An unexpected error occurred.")


# Check wallet activity (Prompt)
async def wallet_prompt(update: Update, context: "Application") -> None:
    message = update.callback_query.message if update.callback_query else update.message
    user_id = update.effective_user.id
    await message.reply_text(
        "🔍 Enter a Solana wallet address to track its activity (e.g., 5oNDL...):"
    )
    user_states[user_id] = "awaiting_wallet"


async def process_wallet(
    user_id: int, wallet_address: str, context: "Application"
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

    await context.bot.send_message(chat_id=user_id, text=f"🔍 Fetching activity for wallet {wallet_address[:6]}..." )
    try:
        data = fetch_wallet_activity(wallet_address)
        transactions = data.get("transfers", [])[:5] # Get latest 5

        if not transactions:
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Track Another Wallet 🔍", callback_data="wallet_tracker"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🕒 No recent activity found for wallet `{wallet_address}`.",
                reply_markup=reply_markup, parse_mode='Markdown'
            )
            return

        message = f"🔍 *Recent Activity for Wallet:* `{wallet_address}`\n\n"
        for i, tx in enumerate(transactions):
            # Use the formatting function
            formatted_tx = format_transaction_details(tx)
            # Remove the header from the helper function for list view
            formatted_tx = "\n".join(formatted_tx.split('\n')[2:]) # Keep details
            message += f"*{i+1}. Transaction*\n{formatted_tx}\n---\n"

        # message += "\nDetails on AlphaVybe: https://alphavybe.com/"
        keyboard = [
            [
                InlineKeyboardButton(
                    "Track Another Wallet 🔍", callback_data="wallet_tracker"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id, text=message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True
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
        await context.bot.send_message(chat_id=user_id, text="❌ An unexpected error occurred.")


# --- Text and Button Handlers ---

# Handle text input (threshold, token, wallet)
async def handle_text(update: Update, context: "Application") -> None:
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_states:
        # Handle unexpected text input when no state is set
        await update.message.reply_text(
             "🤔 Not sure what you mean. Use /start to see the main menu or /help for commands."
        )
        return

    state = user_states.pop(user_id) # Consume the state after handling

    if state == "awaiting_threshold":
        if text.lower() == "skip": # Allow skipping threshold setting
             await update.message.reply_text("⏭️ Threshold setting skipped.")
             return
        try:
            threshold = float(text)
            if threshold <= 0:
                await update.message.reply_text(
                    "❌ Threshold must be a positive number! Please try setting it again via the Whale Alerts menu."
                )
                user_states[user_id] = "awaiting_threshold" # Re-set state if invalid
                return
            user_thresholds[user_id] = threshold
            # Confirmation with next step suggestion
            keyboard = [
                [InlineKeyboardButton("Check Highest Tx Now 📊", callback_data="check_highest_tx")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Threshold set to ${threshold:,.2f}! Future alert feature is pending. You can check the current highest transaction now.",
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount! Please enter a number (e.g., 10000). Try setting it again via the Whale Alerts menu."
            )
            user_states[user_id] = "awaiting_threshold" # Re-set state

    elif state == "awaiting_token":
        token_input = text
        await process_token(user_id, token_input, context)

    elif state == "awaiting_wallet":
        wallet_address = text
        await process_wallet(user_id, wallet_address, context)

    else:
         # Should not happen if state is managed correctly
        logger.warning(f"User {user_id} was in an unknown state: {state}")
        await update.message.reply_text("Something went wrong. Please try /start.")

# Handle inline keyboard button clicks (updated)
async def button_handler(update: Update, context: "Application") -> None:
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    user_id = query.from_user.id
    callback_data = query.data

    if callback_data == "whale_alerts":
        await whale_alerts_command(update, context)
    elif callback_data == "set_threshold":
        # Now triggers the prompt function directly
        await set_threshold_prompt(update, context)
    elif callback_data == "check_highest_tx":
        await check_highest_whale_tx(update, context)
    elif callback_data == "token_stats":
        # Triggers the token prompt
        await token_prompt(update, context)
    elif callback_data == "wallet_tracker":
        # Triggers the wallet prompt
        await wallet_prompt(update, context)
    # Add other callbacks if needed

# --- Error Handler ---
# Error handler (keep as is, maybe add more specific error handling if needed)
async def error_handler(update: Update, context: "Application") -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # Improved error feedback
    if isinstance(context.error, telegram.error.TelegramError):
        logger.warning(f"Telegram API error: {context.error}")
        # Maybe notify user if it's a known issue like bot blocked
    elif isinstance(context.error, requests.RequestException):
        logger.error(f"Network error connecting to external API: {context.error}")
        # Optionally inform the user about potential connectivity issues

    # Generic message to the user if possible
    if update and hasattr(update, 'effective_message') and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Oops! Something went wrong on my end. Please try again later."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
    elif update and hasattr(update, 'callback_query') and update.callback_query:
         try:
            await context.bot.send_message(
                chat_id=update.callback_query.from_user.id,
                 text="❌ Oops! Something went wrong while processing your request. Please try again later."
            )
         except Exception as e:
            logger.error(f"Failed to send error message to user via callback: {e}")

# --- Main Function ---
def main() -> None:
    # Create the Application instance
    # Consider adding persistence if needed later (e.g., PicklePersistence)
    request = HTTPXRequest(
        connection_pool_size=10,
        read_timeout=20.0, # Increased timeout slightly
        connect_timeout=20.0,
    )
    application = Application.builder().token(TELEGRAM_TOKEN).request(request).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("threshold", set_threshold_prompt)) # Direct command access to threshold prompt
    application.add_handler(CommandHandler("token", token_prompt)) # Direct command access to token prompt
    application.add_handler(CommandHandler("wallet", wallet_prompt)) # Direct command access to wallet prompt
    application.add_handler(CommandHandler("whalealerts", whale_alerts_command)) # Command for whale options
    application.add_handler(CommandHandler("check", check_highest_whale_tx)) # Make /check directly trigger highest tx check

    # Add message handler for text inputs based on user state
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    # Add callback query handler for button presses
    application.add_handler(CallbackQueryHandler(button_handler))

    # Add error handler
    application.add_error_handler(error_handler)

    # Removed the scheduled job for check_whales
    # application.job_queue.scheduler.configure(timezone=pytz.timezone("Etc/GMT-1"))
    # application.job_queue.run_repeating(check_whales, interval=120, first=0)

    logger.info("Starting VybeAgent Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
