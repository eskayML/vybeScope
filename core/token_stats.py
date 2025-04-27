import logging
import re
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application

from api import fetch_token_stats

logger = logging.getLogger(__name__)

# Token symbol to Solana token address mapping
TOKEN_ADDRESS_MAP = {
    "SOL": "So11111111111111111111111111111111111111112",  # SOL's wrapped address
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}

# Check token stats (Prompt)
async def token_prompt(update: Update, context: Application, user_states: dict) -> None:
    """Prompts user for token symbol/address (handles command or callback)."""
    query = update.callback_query
    message = update.message or (query.message if query else None)
    user = update.effective_user

    if not message or not user:
        logger.warning("token_prompt couldn't find message or user.")
        return

    if query:
        await query.answer()

    user_id = user.id
    await message.reply_text(
        "📈 Enter a token symbol or contract address to check its stats (e.g., SOL or EPjF...):"
    )
    user_states[user_id] = "awaiting_token"


async def process_token(
    user_id: int, token_input: str, context: Application
) -> None:
    # Improved logic: Check if it's a symbol OR a potential address
    token_input = token_input.strip()
    token_address = None
    token_symbol = None

    # Simple check if it looks like an address (Base58, > 30 chars)
    # Use raw string for regex pattern
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
        keyboard = [[InlineKeyboardButton("Try Again 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Invalid input. Please enter a token symbol or contract address.",
            reply_markup=reply_markup
        )
        return

    # Fetch stats using the determined token_address
    await context.bot.send_message(chat_id=user_id, text=f"🔍 Fetching stats for {token_symbol} ({token_address[:6]}...{token_address[-4:]})...")
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
            # Ensure change_24h is not 'N/A' before converting
            if change_24h != "N/A":
                change_value = float(change_24h)
                if change_value > 0:
                    trend = "📈"
                elif change_value < 0:
                    trend = "📉"
                else:
                    trend = "➡️"
            else:
                trend = "❓"
        except (ValueError, TypeError):
            change_24h = "N/A" # Ensure change is N/A if conversion fails
            trend = "❓"

        # Format numbers nicely
        def format_num(n, default="N/A"):
            try:
                # Check if n is None or 'N/A' before formatting
                if n is None or n == 'N/A':
                    return default
                return f"{float(n):,.2f}"
            except (ValueError, TypeError):
                return default

        price_str = f"${format_num(price)}"
        volume_str = f"${format_num(volume_24h)}"
        mc_str = f"${format_num(market_cap)}"

        # Use the actual symbol fetched if available, otherwise stick with input/placeholder
        fetched_symbol = data.get("symbol", token_symbol)
        fetched_address = data.get("address", token_address) # Use address from response if available

        keyboard = [
            [
                InlineKeyboardButton(
                    "Check Another Token/Address 📈", callback_data="token_stats"
                )
            ],
            [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")] # Add back button
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Use standard f-string formatting
        response_text = (
            f"📊 *{fetched_symbol} Stats* ({fetched_address[:4]}...{fetched_address[-4:]})\n\n"
            f"Price: {price_str}\n"
            f"24h Change: {format_num(change_24h, 'N/A')}% {trend}\n"
            f"24h Volume: {volume_str}\n"
            f"Market Cap: {mc_str}\n"
            # f"Details on AlphaVybe: https://alphavybe.com/" # Link might need token context
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=response_text,
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
        keyboard = [[InlineKeyboardButton("Try Again 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text="❌ An unexpected error occurred.", reply_markup=reply_markup) 