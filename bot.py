import asyncio
import logging
import os
import re

import requests
import telegram
from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from core.dashboard import (
    clear_user_dashboard,
    get_user_dashboard,
    remove_tracked_wallet,
)

# --- Research Agent Integration ---
from core.research_agent import (
    research_agent_handler,
    send_research_agent_miniapp_button,
)
from core.token_stats import process_token, show_top_holders
from core.token_stats import token_prompt as core_token_prompt  # Rename to avoid clash
from core.wallet_tracker import (
    process_wallet,
    show_recent_transactions,
    wallet_tracking_job,  # Import job directly
)
from core.wallet_tracker import (
    wallet_prompt as core_wallet_prompt,  # Rename to avoid clash
)
from core.whale_alerts import (
    set_threshold_prompt as core_set_threshold_prompt,  # Rename to avoid clash
)
from core.whale_alerts import (  # Import job directly
    whale_alert_job,
    whale_alerts_command,
)


class VybeScopeBot:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        if not self.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN not found in environment variables.")
        self.VYBE_API_KEY = os.getenv("VYBE_API_KEY")
        self.WHALE_ALERT_INTERVAL_SECONDS = int(
            os.getenv("WHALE_ALERT_INTERVAL_SECONDS", 120)
        )
        self.WALLET_TRACKING_INTERVAL_SECONDS = int(
            os.getenv("WALLET_TRACKING_INTERVAL_SECONDS", 120)
        )
        self.user_thresholds = {}
        self.user_states = {}
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        self.application = None

    async def start(self, update: Update, context: Application) -> None:
        """Sends the welcome message and main menu."""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        user = update.effective_user.first_name
        welcome_message = (
            f"🚀 Welcome to VybeScope🔭, *{user}*! \n\n"
            "Explore powerful tools to track whale alerts, analyze token statistics, "
            "and monitor wallet activity using the Vybe API.\n\n"
            "Select an option below to begin your journey! 👇"
        )

        # Main menu keyboard
        keyboard = [
            [InlineKeyboardButton("Dashboard 📊", callback_data="dashboard")],
            [
                InlineKeyboardButton("Whale Alerts 🐋", callback_data="whale_alerts"),
                InlineKeyboardButton(
                    "Wallet Tracker 💼", callback_data="wallet_tracker"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Token Statistics 📈", callback_data="token_stats"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Quick Commands ⚡", callback_data="quick_commands"
                ),
                InlineKeyboardButton(
                    "🆕Research Agent 🤖", callback_data="research_agent"
                ),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Clear any previous state for the user
        if update.effective_user and update.effective_user.id in self.user_states:
            del self.user_states[update.effective_user.id]

        # Determine message object (could be from command or callback)
        message = (
            update.callback_query.message if update.callback_query else update.message
        )
        if not message:  # Handle cases where message might be missing
            return

        # Try sending the photo first only on initial /start command
        if (
            update.message
            and update.message.text
            and update.message.text.startswith("/start")
        ):
            try:
                await message.reply_photo(photo=open("assets/vybe_banner.png", "rb"))
            except FileNotFoundError:
                self.logger.error(
                    "Error: assets/vybe_banner.png not found. Skipping photo."
                )
            except telegram.error.BadRequest as e:
                if "not found" in str(e):
                    self.logger.error(
                        "Error: assets/vybe_banner.png not found. Skipping photo."
                    )
                else:
                    self.logger.error(
                        f"Error sending start photo (BadRequest): {e}. Skipping photo."
                    )
            except Exception as e:
                self.logger.error(f"Error sending start photo: {e}. Skipping photo.")

        # Send or edit the welcome message
        try:
            if update.callback_query:
                if getattr(message, "text", None):
                    await message.edit_text(
                        text=welcome_message,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=welcome_message,
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
            else:
                await message.reply_text(
                    text=welcome_message,
                    reply_markup=reply_markup,
                    parse_mode="Markdown",
                )
        except telegram.error.BadRequest as e:
            if "message is not modified" in str(e):
                self.logger.info("Welcome message already shown.")
            else:
                self.logger.error(f"Error sending/editing welcome message: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in start handler: {e}")

    async def threshold_command(self, update: Update, context: Application) -> None:
        """Handles the /threshold command, triggers the prompt."""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        await core_set_threshold_prompt(update, context, self.user_states)

    async def token_command(self, update: Update, context: Application) -> None:
        """Handles the /token command, triggers the prompt."""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        await core_token_prompt(update, context, self.user_states)

    async def wallet_command(self, update: Update, context: Application) -> None:
        """Handles the /wallet command, triggers the prompt."""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        await core_wallet_prompt(update, context, self.user_states)

    async def check_command(self, update: Update, context: Application) -> None:
        """Handles the /check command, directly checks highest tx."""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        await whale_alerts_command(update, context)

    async def agent_command(self, update: Update, context: Application) -> None:
        """Handles the /agent command, opens the Research Agent mini app."""
        await send_research_agent_miniapp_button(update, context)

    async def dashboard_command(self, update: Update, context: Application) -> None:
        """Shows the user's dashboard: tracked wallets and whale alert settings."""
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        user_id = update.effective_user.id
        dashboard = get_user_dashboard(user_id)
        wallets = dashboard.get("wallets", [])

        # Get tracked tokens and their settings
        from core.dashboard import (
            get_token_alert_settings,
            get_tracked_whale_alert_tokens,
        )

        tracked_tokens = get_tracked_whale_alert_tokens(user_id)
        token_settings = {
            token: get_token_alert_settings(user_id, token) for token in tracked_tokens
        }

        is_empty = not wallets and not tracked_tokens

        if is_empty:
            msg = "📊 *Your Dashboard is Empty!*\n\n"
            msg += "Add a wallet or set up whale alerts for tokens to get started."
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
                        "Edit Whale Alerts 🐋", callback_data="whale_alerts"
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

            # Display wallets section
            msg += f"💼 *Tracked Wallets ({len(wallets)}):*\n"
            if wallets:
                for w in wallets:
                    msg += f"`{w}`\n"
            else:
                msg += "_None yet. Add one Immediately!_\n"

            # Display whale alert section with total count
            msg += (
                f"\n🐋 *Whale Alert Settings ({len(tracked_tokens)} tokens tracked):*\n"
            )

            # Display tracked tokens section if any exist
            if tracked_tokens:
                msg += "*Tracked Tokens:*\n"
                for token in tracked_tokens:
                    settings = token_settings[token]
                    status = (
                        "🟢 Enabled"
                        if settings.get("enabled", False)
                        else "🔴 Disabled"
                    )
                    token_threshold = settings.get("threshold", 50000)
                    msg += f"• `{token}`\n"
                    msg += f"  Status: {status}\n"
                    msg += f"  Threshold: ${token_threshold:,.2f}\n"

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
                        "Whale Alert Options ⚙", callback_data="whale_alerts"
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
                await update.callback_query.message.edit_text(
                    text=msg, reply_markup=reply_markup, parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    text=msg, reply_markup=reply_markup, parse_mode="Markdown"
                )
        except Exception as e:
            self.logger.error(f"Error in dashboard_command: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=msg,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

    async def handle_text(self, update: Update, context: Application) -> None:
        """Handles text inputs based on the current user state."""
        await context.bot.send_chat_action(
            chat_id=update.effective_user.id, action=ChatAction.TYPING
        )
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id
        text = update.message.text.strip()

        if text.startswith("/agent"):
            await send_research_agent_miniapp_button(update, context)
            return

        if user_id not in self.user_states:
            await update.message.reply_text(
                "🤔 Not sure what you mean. Use /start to see the main menu."
            )
            return

        state = self.user_states.pop(user_id)

        if state == "awaiting_threshold":
            if text.lower() == "skip":
                await whale_alerts_command(update, context)
                return
            try:
                threshold_value = float(text)
                if threshold_value <= 0:
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "Set Threshold Again 💰", callback_data="set_threshold"
                            )
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(
                        "❌ Threshold must be a positive number!",
                        reply_markup=reply_markup,
                    )
                    self.user_states[user_id] = "awaiting_threshold"
                    return
                self.user_thresholds[user_id] = threshold_value
                await update.message.reply_text(
                    f"✅ Threshold set to ${threshold_value:,.2f}! Future alert feature is pending.",
                )
                await whale_alerts_command(update, context)
            except ValueError:
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
                self.user_states[user_id] = "awaiting_threshold"

        elif state == "awaiting_token":
            await process_token(user_id, text, context)

        elif state == "awaiting_wallet":
            await process_wallet(user_id, text, context)

        elif state == "dashboard_awaiting_add_wallet":
            # Validate wallet address format before processing
            if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", text):
                await update.message.reply_text(
                    "❌ Invalid Solana wallet address format. Please ensure it is a valid Solana address (e.g., 3qArN...)."
                )
                self.user_states[user_id] = (
                    "dashboard_awaiting_add_wallet"  # Keep user in the same state
                )
                return
            await process_wallet(user_id, text, context)

        elif state == "dashboard_awaiting_remove_wallet":
            removed = remove_tracked_wallet(user_id, text)
            if removed:
                await update.message.reply_text(
                    f"✅ Wallet `{text}` removed from your dashboard!"
                )
            else:
                await update.message.reply_text(
                    f"❌ Wallet `{text}` is not in your dashboard, so it cannot be removed."
                )
            await self.dashboard_command(update, context)

        elif state == "dashboard_awaiting_add_whale_alert":
            from core.dashboard import add_tracked_whale_alert_token

            # Validate token address format before processing
            if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", text):
                await update.message.reply_text(
                    "❌ Invalid Solana token address format. Please ensure it is a valid Solana address (e.g., So1111... or similar)."
                )
                self.user_states[user_id] = (
                    "dashboard_awaiting_add_whale_alert"  # Keep user in the same state
                )
                return

            added = add_tracked_whale_alert_token(user_id, text)
            if added:
                await update.message.reply_text(
                    f"✅ Token `{text}` added to your whale alerts!"
                )
            else:
                await update.message.reply_text(
                    f"❌ Token `{text}` is already in your whale alerts."
                )
            await self.dashboard_command(update, context)
        elif state == "dashboard_awaiting_remove_whale_alert":
            from core.dashboard import remove_tracked_whale_alert_token

            removed = remove_tracked_whale_alert_token(user_id, text)
            if removed:
                await update.message.reply_text(
                    f"✅ Token `{text}` removed from your whale alerts!"
                )
            else:
                await update.message.reply_text(
                    f"❌ Token `{text}` is not in your whale alerts."
                )
            await self.dashboard_command(update, context)

        elif state.startswith("awaiting_token_threshold_"):
            token_address = state.replace("awaiting_token_threshold_", "")
            try:
                threshold_value = float(text)
                if threshold_value <= 0:
                    await update.message.reply_text(
                        "❌ Threshold must be a positive number!"
                    )
                    self.user_states[user_id] = (
                        f"awaiting_token_threshold_{token_address}"
                    )
                    return
                from core.dashboard import set_token_alert_threshold

                set_token_alert_threshold(user_id, token_address, threshold_value)
                await update.message.reply_text(
                    f"✅ Whale alert threshold for `{token_address}` set to ${threshold_value:,.2f}!"
                )
                await whale_alerts_command(update, context)
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid amount! Please enter a number (e.g., 5000)."
                )
                self.user_states[user_id] = f"awaiting_token_threshold_{token_address}"

        else:
            self.logger.warning(f"User {user_id} was in an unknown state: {state}")
            await update.message.reply_text("Something went wrong. Please try /start.")

    async def button_handler(self, update: Update, context: Application) -> None:
        """Handles inline keyboard button clicks."""
        await context.bot.send_chat_action(
            chat_id=update.effective_user.id, action=ChatAction.TYPING
        )
        query = update.callback_query
        if not query or not query.data:
            self.logger.warning("Button handler received invalid query object.")
            return
        await query.answer()

        user_id = query.from_user.id
        callback_data = query.data

        if callback_data == "start":
            await self.start(update, context)
        elif callback_data == "whale_alerts":
            await whale_alerts_command(update, context)
        elif callback_data in ["toggle_whale_on", "toggle_whale_off"]:
            # Deprecated - redirect to whale alerts page
            await whale_alerts_command(update, context)
        elif callback_data == "set_threshold":
            await core_set_threshold_prompt(update, context, self.user_states)
        elif callback_data == "token_stats":
            await core_token_prompt(update, context, self.user_states)
        elif callback_data == "wallet_tracker":
            await core_wallet_prompt(update, context, self.user_states)
        elif callback_data == "dashboard":
            await self.dashboard_command(update, context)
        elif callback_data == "dashboard_add_wallet":
            self.user_states[user_id] = "dashboard_awaiting_add_wallet"
            await query.message.reply_text("💼 Enter the wallet address to add:")
        elif callback_data == "dashboard_remove_wallet":
            self.user_states[user_id] = "dashboard_awaiting_remove_wallet"
            await query.message.reply_text("💼 Enter the wallet address to remove:")
        elif callback_data == "dashboard_set_threshold":
            # Redirect to whale alerts page for token-specific settings
            await whale_alerts_command(update, context)
        elif callback_data == "dashboard_add_whale_alert":
            self.user_states[user_id] = "dashboard_awaiting_add_whale_alert"
            await query.message.reply_text(
                "🐋 Enter the token address to add to whale alerts:"
            )
        elif callback_data == "dashboard_remove_whale_alert":
            self.user_states[user_id] = "dashboard_awaiting_remove_whale_alert"
            await query.message.reply_text(
                "🐋 Enter the token address to remove from whale alerts:"
            )
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
            await self.dashboard_command(update, context)
        elif callback_data == "quick_commands":
            quick_commands_msg = (
                "*⚡ Quick Commands & Features*\n\n"
                "Use these commands for quick access to features:\n\n"
                "*/start* – Show main menu & restart the bot.\n"
                "*/dashboard* – View your personal dashboard (tracked wallets & whale alert settings).\n"
                "*/wallet <address>* – Add a new wallet to track or view an existing tracked wallet.\n"
                "*/token <address>* – Get statistics and information for a specific Solana token.\n"
                "*/whalealerts* – Manage whale alert notifications, add/remove tokens, set thresholds, and toggle alerts.\n"
                "*/agent* – Open the Research Agent mini app for advanced AI analytics.\n\n"
                "*💡 Other Tips:*\n"
                "• Use the interactive buttons in chat for most actions.\n"
                "• Directly send a wallet or token address to the bot for quick info.\n"
                "• The bot guides you with prompts for most operations."
            )

            close_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Close ❌", callback_data="close_quick_commands"
                        )
                    ]
                ]
            )
            await query.message.reply_text(
                quick_commands_msg, parse_mode="Markdown", reply_markup=close_markup
            )
            return
        elif callback_data == "close_quick_commands":
            try:
                await query.message.delete()
            except Exception as e:
                self.logger.warning(f"Failed to delete quick commands message: {e}")
            return
        elif callback_data.startswith("show_top_holders_"):
            token_address = callback_data.replace("show_top_holders_", "")
            await show_top_holders(user_id, token_address, context)
        elif callback_data.startswith("token_stats_back_"):
            try:
                await query.message.delete()
            except Exception as e:
                self.logger.warning(f"Failed to delete top holders message: {e}")
            return
        elif callback_data.startswith("show_recent_tx_"):
            wallet_address = callback_data.replace("show_recent_tx_", "")
            # Call our new function to show recent transactions
            await show_recent_transactions(update, context, wallet_address)
        elif callback_data.startswith("remove_wallet_"):
            wallet_address = callback_data.replace("remove_wallet_", "")
            removed = remove_tracked_wallet(user_id, wallet_address)
            if removed:
                await query.message.reply_text(
                    f"✅ Wallet `{wallet_address}` removed from your dashboard!",
                    parse_mode="Markdown",
                )
            else:
                await query.message.reply_text(
                    f"❌ Wallet `{wallet_address}` was not found in your dashboard.",
                    parse_mode="Markdown",
                )
            await self.dashboard_command(update, context)  # Show updated dashboard
        elif callback_data.startswith("recent_tx_back_"):
            try:
                await query.message.delete()
            except Exception as e:
                self.logger.warning(f"Failed to delete recent tx message: {e}")
            return
        elif callback_data.startswith("track_whale_alert_"):
            # Call our new function that handles adding tokens to whale alerts
            from core.whale_alerts import track_token_whale_alert

            await track_token_whale_alert(update, context)
        elif callback_data.startswith("add_whale_alert_token_"):
            token_address = callback_data.replace("add_whale_alert_token_", "")
            from core.dashboard import add_tracked_whale_alert_token

            add_tracked_whale_alert_token(user_id, token_address)
            await query.message.reply_text(
                f"✅ Token `{token_address}` added to your whale alerts!"
            )
        elif callback_data.startswith("remove_whale_alert_token_"):
            token_address = callback_data.replace("remove_whale_alert_token_", "")
            from core.dashboard import remove_tracked_whale_alert_token

            remove_tracked_whale_alert_token(user_id, token_address)
            await query.message.reply_text(
                f"✅ Token `{token_address}` removed from your whale alerts!"
            )
        elif callback_data.startswith("toggle_token_on:") or callback_data.startswith(
            "toggle_token_off:"
        ):
            from core.dashboard import set_token_alert_enabled

            parts = callback_data.split(":", 1)
            if len(parts) == 2:
                token_address = parts[1]
                enable = callback_data.startswith("toggle_token_on:")
                set_token_alert_enabled(user_id, token_address, enable)
                await query.message.reply_text(
                    f"{'✅ Enabled' if enable else '❌ Disabled'} whale alert for token `{token_address}`.",
                    parse_mode="Markdown",
                )
                await whale_alerts_command(update, context)
        elif callback_data.startswith("disable_alert:"):
            from core.dashboard import set_token_alert_enabled

            token_address = callback_data.split(":", 1)[1]
            set_token_alert_enabled(user_id, token_address, False)
            await query.message.reply_text(
                f"❌ Disabled whale alert for token `{token_address}`.",
                parse_mode="Markdown",
            )
            await whale_alerts_command(update, context)
        elif callback_data.startswith(
            "set_token_threshold:"
        ) or callback_data.startswith("change_threshold:"):
            token_address = callback_data.split(":", 1)[1]
            self.user_states[user_id] = f"awaiting_token_threshold_{token_address}"
            await query.message.reply_text(
                f"💰 Enter the new USD threshold for token `{token_address}`:",
                parse_mode="Markdown",
            )
        else:
            self.logger.info(f"Received unhandled callback_data: {callback_data}")

    async def error_handler(self, update: object, context: Application) -> None:
        """Logs errors and sends a user-friendly message."""
        self.logger.error(
            msg="Exception while handling an update:", exc_info=context.error
        )

        chat_id = None
        if isinstance(update, Update):
            if update.effective_chat:
                chat_id = update.effective_chat.id
            elif update.effective_user:
                chat_id = update.effective_user.id

        error_message = (
            "❌ Oops! Something went wrong on my end. Please try again later."
        )

        if isinstance(context.error, telegram.error.BadRequest):
            if "message is not modified" in str(context.error):
                self.logger.info("Attempted to edit message with identical content.")
                return
            elif "message to edit not found" in str(context.error):
                self.logger.warning("Attempted to edit a message that was not found.")
                error_message = (
                    "❌ Sorry, the message you interacted with might be too old."
                )
        elif isinstance(context.error, requests.RequestException):
            self.logger.error(
                f"Network error connecting to external API: {context.error}"
            )
            error_message = "❌ Network error: Could not connect to external services. Please try again later."
        elif isinstance(context.error, telegram.error.Forbidden):
            self.logger.warning(
                f"Forbidden error: {context.error}. Bot might be blocked by the user {chat_id}."
            )
            return
        elif isinstance(context.error, telegram.error.NetworkError):
            self.logger.error(
                f"Telegram Network error: {context.error}. Retrying or waiting might help."
            )
            error_message = (
                "❌ Network error communicating with Telegram. Please try again."
            )

        if chat_id:
            try:
                await context.bot.send_message(chat_id=chat_id, text=error_message)
            except Exception as e:
                self.logger.error(
                    f"Failed to send error message to user {chat_id}: {e}"
                )

    def run(self):
        self.logger.info("Initializing VybeScope Bot...")
        request = HTTPXRequest(
            connection_pool_size=10,
            read_timeout=30.0,
            connect_timeout=30.0,
        )
        self.application = (
            Application.builder().token(self.TELEGRAM_TOKEN).request(request).build()
        )

        async def set_bot_commands():
            commands = [
                BotCommand("start", "Show main menu and restart the bot"),
                BotCommand("dashboard", "View your dashboard and tracked wallets"),
                BotCommand("wallet", "Track or view a wallet's activity"),
                BotCommand("token", "Get stats for a Solana token"),
                BotCommand("whalealerts", "Manage whale alert notifications"),
                BotCommand("agent", "Open the Research Agent mini app"),
            ]
            await self.application.bot.set_my_commands(commands)

        asyncio.get_event_loop().run_until_complete(set_bot_commands())

        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("token", self.token_command))
        self.application.add_handler(CommandHandler("wallet", self.wallet_command))
        self.application.add_handler(
            CommandHandler("whalealerts", whale_alerts_command)
        )
        self.application.add_handler(
            CommandHandler("dashboard", self.dashboard_command)
        )
        self.application.add_handler(CommandHandler("agent", self.agent_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )
        self.application.add_handler(
            CallbackQueryHandler(research_agent_handler, pattern="^research_agent$")
        )
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_error_handler(self.error_handler)

        # Use Telegram's JobQueue to schedule whale alerts

        self.application.job_queue.run_repeating(
            whale_alert_job, interval=self.WHALE_ALERT_INTERVAL_SECONDS, first=10, name="whale_alert_job"
        )
        self.application.job_queue.run_repeating(
            wallet_tracking_job, interval=self.WALLET_TRACKING_INTERVAL_SECONDS, first=30, name="wallet_tracking_job"
        )

        self.logger.info("Starting bot polling...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    bot = VybeScopeBot()
    bot.run()
