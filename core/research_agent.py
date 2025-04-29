import asyncio
import os

from dotenv import load_dotenv
from openai import OpenAI
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


async def handle_research_query(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not user_research_agent_state.get(user_id, False):
        return
    question = update.message.text
    response = await query_openai(question)
    await update.message.reply_text(response)
    # Optionally, you can keep the toggle button visible
    # await send_toggle_button(update, context, True)


async def query_openai(question: str) -> str:
    """Query OpenAI with the given question and return the response using gpt-4o model."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Error: OPENAI_API_KEY not set."
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            max_tokens=100,
            temperature=0.5,
        )

        answer = response.choices[0].message.content.strip()

        print("---AGENT RESPONSE ---")
        print(answer)

        return answer

    except Exception as e:
        return f"Error: {e}"
