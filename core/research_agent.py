import asyncio
import os

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Update,
    WebAppInfo,
)
from telegram.ext import CallbackContext

load_dotenv()

PEPE_AGENT_IMAGE_PATH = os.path.join(
    os.path.dirname(__file__), "../assets/pepe_agent.png"
)

SYSTEM_PROMPT = (
    "You are VybeScope's Research Agent, an expert Solana and crypto analyst. "
    "Your job is to answer user questions with highly accurate, concise, and actionable insights. "
    "Always summarize your response in 50 words or less. "
    "Focus on clarity, brevity, and relevance. Avoid filler, disclaimers, or repetition. "
    "Assume the user is familiar with crypto basics. "
    "If a question is unclear, ask for clarification in a single sentence."
)

# In-memory toggle state for users
user_research_agent_state = {}


async def send_temp_image_and_delete(
    update: Update, context: CallbackContext, duration: int = 3
):
    with open(PEPE_AGENT_IMAGE_PATH, "rb") as img:
        msg = await context.bot.send_photo(
            chat_id=update.effective_chat.id, photo=InputFile(img)
        )
    await asyncio.sleep(duration)
    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=msg.message_id
    )


async def send_research_agent_miniapp_button(update: Update, context: CallbackContext):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Open Research Agent",
                    web_app=WebAppInfo(
                        url="https://v0-telegram-chat-app-rose.vercel.app/"
                    ),
                )
            ]
        ]
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Open the Research Agent Mini App:",
        reply_markup=keyboard,
    )


async def research_agent_handler(update: Update, context: CallbackContext):
    await send_temp_image_and_delete(update, context)
    await send_research_agent_miniapp_button(update, context)
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.answer("Opening Research Agent Mini App...")


