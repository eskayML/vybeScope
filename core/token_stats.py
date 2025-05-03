import logging
import re
import time

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application

from api import fetch_token_stats, fetch_top_token_holders
from core.top_holders_table import format_top_holders_text

logger = logging.getLogger(__name__)

# Token symbol to Solana token address mapping
TOKEN_ADDRESS_MAP = {
    "SOL": "So11111111111111111111111111111111111111112",  # Solana (Wrapped SOL)
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USD Coin
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # Tether USD
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # Bonk
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # dogwifhat
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # Pyth Network
    "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",  # Jito
    "RNDR": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",  # Render Token (SPL)
    "HNT": "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",  # Helium
    "TRUMP": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN",  # OFFICIAL TRUMP
    # Add more mappings here as needed
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
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    await message.reply_text(
        "📈 Enter a token symbol (e.g. WIF, PYTH, JTO, BONK, TRUMP) or the full contract address to check its stats:"
    )
    user_states[user_id] = "awaiting_token"


async def show_top_holders(user_id: int, token_address: str, context: Application):
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    try:
        holders = fetch_top_token_holders(token_address)
        holders_text = format_top_holders_text(holders)
        keyboard = [
            [
                InlineKeyboardButton(
                    "Back to Token Stats",
                    callback_data=f"token_stats_back_{token_address}",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        sent_msg = await context.bot.send_message(
            chat_id=user_id,
            text=holders_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        # Store the message id for deletion
        context.user_data["last_top_holders_msg_id"] = sent_msg.message_id
    except Exception as e:
        logger.error(f"Error fetching top holders: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Failed to fetch top holders.",
        )


async def process_token(user_id: int, token_input: str, context: Application) -> None:
    await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.TYPING)
    # Improved logic: Check if it's a symbol OR a potential address
    token_input = token_input.strip()
    token_address = None
    token_symbol = None

    # Simple check if it looks like an address (Base58, > 30 chars)
    # Use raw string for regex pattern
    if re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", token_input):
        token_address = token_input
        # We might not know the symbol initially from just the address
        token_symbol = token_address[:6] + "..."  # Placeholder symbol
    else:
        # Assume it's a symbol
        token_symbol = token_input.upper()
        if token_symbol in TOKEN_ADDRESS_MAP:
            token_address = TOKEN_ADDRESS_MAP[token_symbol]
        else:
            # Try fetching by symbol directly if API supports it, otherwise error
            # For now, let's stick to the known map or direct address input
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Try Another Token/Address 📈", callback_data="token_stats"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Unknown token symbol: {token_symbol}. Please provide a known symbol (e.g. WIF ,PYTH, JTO, BONK, TRUMP) or the full contract address.",
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
            reply_markup=reply_markup,
        )
        return

    # Show pepe_sniper image with fetching text before Scoping stats
    image_path = "assets/pepe_sniper.jpg"
    image_msg = None
    try:
        image_msg = await context.bot.send_photo(
            chat_id=user_id,
            photo=image_path,
            caption=f"🔍 Scoping stats for {token_symbol} ({token_address[:6]}...{token_address[-4:]})...",
        )
    except Exception as e:
        logger.warning(f"Failed to send image: {e}")

    # Fetch stats using the determined token_address
    try:
        # Assuming fetch_token_stats takes the address
        data = fetch_token_stats(token_address)

        # --- Updated Data Extraction ---
        price = data.get("price")
        price_1d = data.get("price1d")  # Price 24 hours ago
        volume_24h = data.get("usdValueVolume24h")
        market_cap = data.get("marketCap")
        fetched_name = data.get(
            "name", token_symbol
        )  # Use provided name or fallback to symbol
        fetched_symbol = data.get(
            "symbol", token_symbol
        )  # Use provided symbol or fallback
        fetched_address = data.get(
            "mintAddress", token_address
        )  # Use mintAddress or fallback
        logo_url = data.get("logoUrl")  # Extract logo URL

        # --- Calculate 24h Change ---
        change_24h_percent = "N/A"
        trend = "❓"
        if price is not None and price_1d is not None and price_1d != 0:
            try:
                change = ((float(price) - float(price_1d)) / float(price_1d)) * 100
                change_24h_percent = f"{change:,.2f}"  # Format as percentage string
                if change > 0:
                    trend = "🟢📈"
                elif change < 0:
                    trend = "🔴📉"
                else:
                    trend = "➡️"
            except (ValueError, TypeError, ZeroDivisionError) as calc_err:
                logger.warning(
                    f"Could not calculate 24h change for {fetched_address}: {calc_err}"
                )
                change_24h_percent = "N/A"
                trend = "❓"
        # --- End Calculate 24h Change ---

        # Format numbers nicely
        def format_num(n, precision=2, default="N/A"):
            try:
                if n is None:
                    return default
                return f"{float(n):,.{precision}f}"
            except (ValueError, TypeError):
                return default

        # --- Updated Formatting ---
        # Dynamically set price precision: 8 decimals if < 0.01, else 4
        price_precision = 8 if price is not None and abs(float(price)) < 0.01 else 4
        price_str = f"${format_num(price, precision=price_precision)}"  # Dynamic precision for price
        volume_str = f"${format_num(volume_24h)}"
        mc_str = f"${format_num(market_cap)}"
        address_display = f"{fetched_address}" if fetched_address else "N/A"
        explorer_url = (
            f"https://vybe.fyi/tokens/{fetched_address}" if fetched_address else None
        )

        # --- Updated Response Text ---
        response_text = (
            f"📊 *{fetched_name} ({fetched_symbol}) Stats*\n"
            f"   Address: `{address_display}`\n\n"
            f"Price: *{price_str}*\n"
            f"24h Change: *{change_24h_percent}% {trend}*\n"
            f"24h Volume: *{volume_str}*\n"
            f"Market Cap: *{mc_str}*\n"
        )
        if explorer_url:
            response_text += f"\n[More details]({explorer_url})"
        # --- End Updated Response Text ---

        # --- Add Whale Alerts Button ---
        keyboard = [
            [
                InlineKeyboardButton(
                    "Track Whale Alerts 🐋",
                    callback_data=f"track_whale_alert_{fetched_address}",
                ),
                InlineKeyboardButton(
                    "Show Top Holders 🏆",
                    callback_data=f"show_top_holders_{fetched_address}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "Check Another Token/Address 📈", callback_data="token_stats"
                )
            ],
            [InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # --- Send Message/Photo ---
        if logo_url:
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=logo_url,
                    caption=response_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
            except Exception as photo_err:
                logger.warning(
                    f"Failed to send photo {logo_url} for {fetched_address}. Falling back to text. Error: {photo_err}"
                )
                # Fallback to sending text message if photo fails
                await context.bot.send_message(
                    chat_id=user_id,
                    text=response_text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        else:
            # Send only text if no logo URL
            await context.bot.send_message(
                chat_id=user_id,
                text=response_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        # --- End Send Message/Photo ---

        # Delete the image message in a stylish way
        if image_msg:
            time.sleep(3)
            try:
                await context.bot.delete_message(
                    chat_id=user_id, message_id=image_msg.message_id
                )
            except Exception as e:
                logger.warning(f"Failed to delete image message: {e}")

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
        logger.error(
            f"An unexpected error occurred processing token {token_address}: {e}"
        )
        keyboard = [[InlineKeyboardButton("Try Again 📈", callback_data="token_stats")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ An unexpected error occurred.",
            reply_markup=reply_markup,
        )
