import logging
import os

import requests
import telegram
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from api import fetch_whale_transactions
from core.dashboard import (
    _load_dashboard,
    _save_dashboard,
    add_tracked_wallet,
    clear_user_dashboard,
    get_user_dashboard,
    remove_tracked_wallet,
    set_whale_alert_threshold,
)
from core.token_stats import process_token, show_top_holders
from core.token_stats import token_prompt as core_token_prompt  # Rename to avoid clash
from core.wallet_tracker import process_wallet
from core.wallet_tracker import (
    wallet_prompt as core_wallet_prompt,  # Rename to avoid clash
)

# Import core functionalities
from core.whale_alerts import check_highest_whale_tx, get_whale_alerts_enabled
from core.whale_alerts import (
    set_threshold_prompt as core_set_threshold_prompt,  # Rename to avoid clash
)
from core.whale_alerts import toggle_whale_alerts, whale_alerts_command

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


# --- Main Command Handlers ---


async def start(update: Update, context: Application) -> None:
    """Sends the welcome message and main menu."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    user = update.effective_user.first_name
    welcome_message = (
        f"🚀Welcome to VybeScope🔭, *{user}*! \n"
        "Perform Actions that directly interact with the Vybe API \n"
        "Track whale alerts, token stats, and wallet activity.\n\n"
        "Choose an action below to get started! 👇"
    )

    # Main menu keyboard
    keyboard = [
        [InlineKeyboardButton("Dashboard 📊", callback_data="dashboard")],
        [
            InlineKeyboardButton("Whale Alerts 🐋", callback_data="whale_alerts"),
            InlineKeyboardButton("Wallet Tracker 💼", callback_data="wallet_tracker"),
        ],
        [
            InlineKeyboardButton("Token Statistics 📈", callback_data="token_stats"),
        ],
        [
            InlineKeyboardButton("Quick Commands ⚡", callback_data="quick_commands"),
            InlineKeyboardButton("Research Agent 🤖", callback_data="research_agent"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Clear any previous state for the user
    if update.effective_user and update.effective_user.id in user_states:
        del user_states[update.effective_user.id]

    # Determine message object (could be from command or callback)
    message = update.callback_query.message if update.callback_query else update.message
    if not message:  # Handle cases where message might be missing
        return

    # Try sending the photo first only on initial /start command
    if (
        update.message
        and update.message.text
        and update.message.text.startswith("/start")
    ):
        try:
            # Use reply_photo for new message, edit_media for callback?
            # For simplicity, let's assume start always sends a new message with photo
            await message.reply_photo(photo=open("assets/vybe_banner.png", "rb"))
        except FileNotFoundError:
            logger.error("Error: assets/vybe_banner.png not found. Skipping photo.")
        except telegram.error.BadRequest as e:
            if "not found" in str(e):
                logger.error("Error: assets/vybe_banner.png not found. Skipping photo.")
            else:
                logger.error(
                    f"Error sending start photo (BadRequest): {e}. Skipping photo."
                )
        except Exception as e:
            logger.error(f"Error sending start photo: {e}. Skipping photo.")

    # Send or edit the welcome message
    try:
        if update.callback_query:
            # Edit the existing message if it came from a button press (like 'Back to Main Menu')
            # Only edit if the message has text (not a photo or media)
            if getattr(message, "text", None):
                await message.edit_text(
                    text=welcome_message,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
            else:
                # If message has no text (e.g., it's a photo), send a new message
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=welcome_message,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        else:
            # Send a new message if it came from the /start command
            await message.reply_text(
                text=welcome_message, reply_markup=reply_markup, parse_mode="Markdown"
            )
    except telegram.error.BadRequest as e:
        # Handle cases like editing a message with the same content
        if "message is not modified" in str(e):
            logger.info("Welcome message already shown.")
        else:
            logger.error(f"Error sending/editing welcome message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in start handler: {e}")


# --- Direct Command Aliases (Optional) ---
# These allow users to type /threshold, /token, /wallet directly


async def threshold_command(update: Update, context: Application) -> None:
    """Handles the /threshold command, triggers the prompt."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    # Core prompt now handles message update directly
    await core_set_threshold_prompt(update, context, user_states)


async def token_command(update: Update, context: Application) -> None:
    """Handles the /token command, triggers the prompt."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    # Core prompt now handles message update directly
    await core_token_prompt(update, context, user_states)


async def wallet_command(update: Update, context: Application) -> None:
    """Handles the /wallet command, triggers the prompt."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    # Core prompt now handles message update directly
    await core_wallet_prompt(update, context, user_states)


async def check_command(update: Update, context: Application) -> None:
    """Handles the /check command, directly checks highest tx."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    # Pass the message update directly to the core function
    # Note: check_highest_whale_tx still expects a query structure internally.
    # We need to adapt check_highest_whale_tx as well.
    # For now, let's route /check to the whale_alerts menu instead.
    await whale_alerts_command(update, context)


async def dashboard_command(update: Update, context: Application) -> None:
    """Shows the user's dashboard: tracked wallets and whale alert settings."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )
    user_id = update.effective_user.id
    dashboard = get_user_dashboard(user_id)
    wallets = dashboard.get("wallets", [])
    threshold = dashboard.get("whale_alert", {}).get("threshold")
    whale_alerts_enabled = get_whale_alerts_enabled(user_id)
    is_empty = not wallets and not threshold

    # Build the message
    if is_empty:
        msg = "📊 *Your Dashboard is Empty!*\n\n"
        msg += "Add a wallet or set a whale alert threshold to get started."
        keyboard = [
            [
                InlineKeyboardButton(
                    "Add Wallet ➕", callback_data="dashboard_add_wallet"
                ),
                InlineKeyboardButton(
                    "Remove Wallet ➖", callback_data="dashboard_remove_wallet"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Set Whale Threshold ⚙", callback_data="dashboard_set_threshold"
                ),
                InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start"),
            ],
            [
                InlineKeyboardButton(
                    "🗑️ Clear Dashboard", callback_data="dashboard_clear"
                ),
            ],
        ]
    else:
        msg = "📊 *Your Dashboard*\n\n"
        msg += f"💼 *Tracked Wallets ({len(wallets)}):*\n"
        if wallets:
            for w in wallets:
                msg += f"`{w}`\n"
        else:
            msg += "_None yet. Add one from Wallet Tracker!_\n"
        msg += "\n🐋 *Whale Alert Settings:*\n"
        msg += f"Status: {'🟢 Enabled' if whale_alerts_enabled else '🔴 Disabled'}\n"
        msg += f"Threshold: ${threshold:,.2f}" if threshold else "Threshold: _Not set_"
        msg += "\n\nUse the buttons below to manage your dashboard."
        keyboard = [
            [
                InlineKeyboardButton(
                    "Add Wallet ➕", callback_data="dashboard_add_wallet"
                ),
                InlineKeyboardButton(
                    "Remove Wallet ➖", callback_data="dashboard_remove_wallet"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Set Whale Threshold ⚙", callback_data="dashboard_set_threshold"
                ),
                InlineKeyboardButton("Back to Main Menu 🔙", callback_data="start"),
            ],
            [
                InlineKeyboardButton(
                    "🗑️ Clear Dashboard", callback_data="dashboard_clear"
                ),
            ],
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.callback_query:
            # Edit existing message if it's from a button press
            await update.callback_query.message.edit_text(
                text=msg, reply_markup=reply_markup, parse_mode="Markdown"
            )
        else:
            # Send new message if it's from a direct command
            await update.message.reply_text(
                text=msg, reply_markup=reply_markup, parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error in dashboard_command: {e}")
        # Fallback to sending a new message if editing fails
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )


# --- Text Input Handler ---


async def handle_text(update: Update, context: Application) -> None:
    """Handles text inputs based on the current user state."""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id, action=ChatAction.TYPING
    )
    if not update.message or not update.message.text:
        return  # Ignore empty messages

    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_states:
        await update.message.reply_text(
            "🤔 Not sure what you mean. Use /start to see the main menu."
        )
        return

    state = user_states.pop(user_id)  # Consume the state after handling

    if state == "awaiting_threshold":
        if text.lower() == "skip":
            # Provide feedback and suggest next actions
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Check Highest Tx Now 📊", callback_data="check_highest_tx"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Back to Whale Options 🐳", callback_data="whale_alerts"
                    )
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⏭️ Threshold setting skipped.", reply_markup=reply_markup
            )
            return
        try:
            threshold_value = float(text)
            if threshold_value <= 0:
                # Guide the user back
                keyboard = [
                    [
                        InlineKeyboardButton(
                            "Set Threshold Again 💰", callback_data="set_threshold"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "❌ Threshold must be a positive number!", reply_markup=reply_markup
                )
                user_states[user_id] = "awaiting_threshold"  # Re-set state if invalid
                return
            user_thresholds[user_id] = threshold_value
            # Confirmation with next step suggestion
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Check Highest Tx Now 📊", callback_data="check_highest_tx"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Back to Whale Options 🐳", callback_data="whale_alerts"
                    )
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Threshold set to ${threshold_value:,.2f}! Future alert feature is pending. You can check the current highest transaction now.",
                reply_markup=reply_markup,
            )
        except ValueError:
            # Guide the user back
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Set Threshold Again 💰", callback_data="set_threshold"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ Invalid amount! Please enter a number (e.g., 10000).",
                reply_markup=reply_markup,
            )
            user_states[user_id] = "awaiting_threshold"  # Re-set state

    elif state == "awaiting_token":
        # Pass user_id, text input, and context to the core processing function
        await process_token(user_id, text, context)

    elif state == "awaiting_wallet":
        # Pass user_id, text input, and context to the core processing function
        await process_wallet(user_id, text, context)

    elif state == "dashboard_awaiting_add_wallet":
        # Add wallet to the user's dashboard
        add_tracked_wallet(user_id, text)
        await update.message.reply_text(f"✅ Wallet `{text}` added to your dashboard!")
        await dashboard_command(update, context)

    elif state == "dashboard_awaiting_remove_wallet":
        # Remove wallet from the user's dashboard
        remove_tracked_wallet(user_id, text)
        await update.message.reply_text(
            f"✅ Wallet `{text}` removed from your dashboard!"
        )
        await dashboard_command(update, context)

    elif state == "dashboard_awaiting_set_threshold":
        try:
            threshold_value = float(text)
            if threshold_value <= 0:
                await update.message.reply_text(
                    "❌ Threshold must be a positive number!"
                )
                user_states[user_id] = (
                    "dashboard_awaiting_set_threshold"  # Re-set state if invalid
                )
                return
            set_whale_alert_threshold(user_id, threshold_value)
            await update.message.reply_text(
                f"✅ Whale alert threshold set to ${threshold_value:,.2f}!"
            )
            await dashboard_command(update, context)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount! Please enter a number (e.g., 5000)."
            )
            user_states[user_id] = "dashboard_awaiting_set_threshold"  # Re-set state

    else:
        logger.warning(f"User {user_id} was in an unknown state: {state}")
        await update.message.reply_text("Something went wrong. Please try /start.")


# --- Button Click Handler ---


async def button_handler(update: Update, context: Application) -> None:
    """Handles inline keyboard button clicks."""
    await context.bot.send_chat_action(
        chat_id=update.effective_user.id, action=ChatAction.TYPING
    )
    query = update.callback_query
    if not query or not query.data:
        logger.warning("Button handler received invalid query object.")
        return
    await query.answer()  # Acknowledge the button press

    user_id = query.from_user.id
    callback_data = query.data

    # Route callbacks to the appropriate core functions or main handlers
    if callback_data == "start":
        await start(update, context)
    elif callback_data == "whale_alerts":
        await whale_alerts_command(update, context)
    elif callback_data in ["toggle_whale_on", "toggle_whale_off"]:
        await toggle_whale_alerts(update, context)
    elif callback_data == "set_threshold":
        # Pass user_states dictionary
        await core_set_threshold_prompt(update, context, user_states)
    elif callback_data == "check_highest_tx":
        await check_highest_whale_tx(update, context)
    elif callback_data == "token_stats":
        # Pass user_states dictionary
        await core_token_prompt(update, context, user_states)
    elif callback_data == "wallet_tracker":
        # Pass user_states dictionary
        await core_wallet_prompt(update, context, user_states)
    elif callback_data == "dashboard":
        await dashboard_command(update, context)
    elif callback_data == "dashboard_add_wallet":
        user_states[user_id] = "dashboard_awaiting_add_wallet"
        await query.message.reply_text("💼 Enter the wallet address to add:")
    elif callback_data == "dashboard_remove_wallet":
        user_states[user_id] = "dashboard_awaiting_remove_wallet"
        await query.message.reply_text("💼 Enter the wallet address to remove:")
    elif callback_data == "dashboard_set_threshold":
        user_states[user_id] = "dashboard_awaiting_set_threshold"
        await query.message.reply_text("🐋 Enter the new whale alert threshold (USD):")
    elif callback_data == "dashboard_clear":
        cleared = clear_user_dashboard(user_id)
        if cleared:
            await query.message.reply_text(
                "🗑️ Dashboard cleared!", parse_mode="Markdown"
            )
        else:
            await query.message.reply_text(
                "Dashboard was already empty.", parse_mode="Markdown"
            )
        await dashboard_command(update, context)
    elif callback_data.startswith("show_top_holders_"):
        token_address = callback_data.replace("show_top_holders_", "")
        await show_top_holders(user_id, token_address, context)
    elif callback_data.startswith("token_stats_back_"):
        # Only delete the top holders message, do not show token stats again
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete top holders message: {e}")
        return
    else:
        logger.info(f"Received unhandled callback_data: {callback_data}")
        # Optionally send a message if the callback is unknown
        # await query.message.reply_text("Sorry, I didn't understand that button.")


# --- Error Handler ---


async def error_handler(update: object, context: Application) -> None:
    """Logs errors and sends a user-friendly message."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # Determine chat_id if possible
    chat_id = None
    if isinstance(update, Update):
        if update.effective_chat:
            chat_id = update.effective_chat.id
        elif update.effective_user:
            # Fallback for cases where chat might not be available (e.g., some callback queries)
            chat_id = update.effective_user.id

    error_message = "❌ Oops! Something went wrong on my end. Please try again later."

    # Check for specific, potentially user-facing errors
    if isinstance(context.error, telegram.error.BadRequest):
        if "message is not modified" in str(context.error):
            logger.info("Attempted to edit message with identical content.")
            return  # Don't notify the user
        elif "message to edit not found" in str(context.error):
            logger.warning("Attempted to edit a message that was not found.")
            error_message = (
                "❌ Sorry, the message you interacted with might be too old."
            )
        # Add more specific BadRequest checks if needed
    elif isinstance(context.error, requests.RequestException):
        logger.error(f"Network error connecting to external API: {context.error}")
        error_message = "❌ Network error: Could not connect to external services. Please try again later."
    elif isinstance(context.error, telegram.error.Forbidden):
        logger.warning(
            f"Forbidden error: {context.error}. Bot might be blocked by the user {chat_id}."
        )
        # Don't try to send a message if the bot is blocked
        return
    elif isinstance(context.error, telegram.error.NetworkError):
        logger.error(
            f"Telegram Network error: {context.error}. Retrying or waiting might help."
        )
        error_message = (
            "❌ Network error communicating with Telegram. Please try again."
        )

    # Send the error message to the user if we have a chat_id
    if chat_id:
        try:
            await context.bot.send_message(chat_id=chat_id, text=error_message)
        except Exception as e:
            logger.error(f"Failed to send error message to user {chat_id}: {e}")


# --- Scheduled Whale Alert Job ---


async def whale_alert_job(application: Application):
    """Checks whale transactions for all users with alerts enabled and sends notifications."""
    dashboard = _load_dashboard()
    for user_id, user_data in dashboard.items():
        whale_alert = user_data.get("whale_alert", {})
        if whale_alert.get("enabled"):
            try:
                # Fetch the latest whale transaction
                data = fetch_whale_transactions(
                    min_amount_usd=whale_alert.get("threshold", 50000)
                )
                transactions = data.get("transfers", [])
                if not transactions:
                    continue
                # Find the highest value transaction
                highest_tx = max(
                    transactions, key=lambda tx: float(tx.get("valueUsd", 0))
                )
                tx_signature = highest_tx.get("signature")
                # Only alert if this is a new transaction
                if tx_signature and tx_signature != whale_alert.get(
                    "last_alerted_signature"
                ):
                    # Send alert
                    class DummyQuery:
                        message = type(
                            "msg", (), {"reply_text": lambda *a, **k: None}
                        )()

                        async def answer(self):
                            pass

                    class DummyUpdate:
                        callback_query = DummyQuery()
                        effective_user = type("user", (), {"id": int(user_id)})()

                    class DummyContext:
                        bot = application.bot

                    await check_highest_whale_tx(DummyUpdate(), DummyContext())
                    # Update last alerted signature
                    dashboard[user_id]["whale_alert"]["last_alerted_signature"] = (
                        tx_signature
                    )
                    _save_dashboard(dashboard)
            except BadRequest as e:
                logger.warning(f"Failed to send whale alert to user {user_id}: {e}")
            except Exception as e:
                logger.error(f"Error in whale alert job for user {user_id}: {e}")


# --- Main Function ---


def main() -> None:
    """Starts the bot."""
    logger.info("Initializing VybeScope Bot...")

    # Configure HTTPX request settings
    request = HTTPXRequest(
        connection_pool_size=10,
        read_timeout=30.0,  # Slightly increased timeout
        connect_timeout=30.0,
    )
    application = Application.builder().token(TELEGRAM_TOKEN).request(request).build()

    # --- Register Handlers ---
    # Core commands
    application.add_handler(CommandHandler("start", start))

    # Feature-specific commands (triggering prompts or actions from core modules)
    application.add_handler(CommandHandler("threshold", threshold_command))
    application.add_handler(CommandHandler("token", token_command))
    application.add_handler(CommandHandler("wallet", wallet_command))
    application.add_handler(CommandHandler("whalealerts", whale_alerts_command))
    application.add_handler(
        CommandHandler("check", check_command)
    )  # Route /check to menu via alias handler
    application.add_handler(CommandHandler("dashboard", dashboard_command))

    # Text input handler (state-based)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    # Callback query handler (button presses)
    application.add_handler(CallbackQueryHandler(button_handler))

    # Error handler
    application.add_error_handler(error_handler)

    # --- Scheduler for Whale Alerts ---
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: whale_alert_job(application), "interval", minutes=10)
    scheduler.start()

    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

