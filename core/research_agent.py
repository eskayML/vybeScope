import asyncio
import os

from openai import OpenAI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import CallbackContext

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


def toggle_research_agent(user_id: int):
    current = user_research_agent_state.get(user_id, False)
    user_research_agent_state[user_id] = not current
    return not current


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


async def send_toggle_button(
    update: Update, context: CallbackContext, toggled_on: bool
):
    button_text = "Turn Off Research Agent" if toggled_on else "Turn On Research Agent"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(button_text, callback_data="toggle_research_agent")]]
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Research Agent is currently {'ON' if toggled_on else 'OFF'}.",
        reply_markup=keyboard,
    )


async def research_agent_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        user_research_agent_state[user_id] = False
        await send_temp_image_and_delete(update, context)
        await send_toggle_button(update, context, False)
        await update.callback_query.message.reply_text(
            "Error: Research Agent cannot be enabled because OPENAI_API_KEY is not set."
        )
        return
    toggled_on = toggle_research_agent(user_id)
    await send_temp_image_and_delete(update, context)
    await send_toggle_button(update, context, toggled_on)
    if toggled_on:
        await update.callback_query.message.reply_text(
            "Research Agent enabled. Any message you send will be answered by the Research Agent."
        )
    else:
        await update.callback_query.message.reply_text("Research Agent disabled.")


async def handle_research_query(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not user_research_agent_state.get(user_id, False):
        return
    question = update.message.text
    response = await query_openai(question)
    await update.message.reply_text(response)
    # Optionally, you can keep the toggle button visible
    # await send_toggle_button(update, context, True)


async def toggle_research_agent_callback(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    toggled_on = toggle_research_agent(user_id)
    await send_temp_image_and_delete(update, context)
    await send_toggle_button(update, context, toggled_on)
    await update.callback_query.answer(
        f"Research Agent is now {'ON' if toggled_on else 'OFF'}."
    )


async def query_openai(question: str) -> str:
    """Query OpenAI with the given question and return the response using gpt-4o model."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "Error: OPENAI_API_KEY not set."
    try:
        client = OpenAI(api_key=api_key)
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": question},
                ],
                max_tokens=100,
                temperature=0.5,
            )
        )
        answer = response.choices[0].message.content.strip()
        words = answer.split()
        if len(words) > 50:
            answer = " ".join(words[:50]) + "..."
        return answer
    except Exception as e:
        return f"Error: {e}"
