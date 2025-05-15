import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from api import fetch_token_stats  # ADDED IMPORT

logger = logging.getLogger(__name__)


async def get_token_symbol(token_address: str) -> str:  # Changed
    """Fetches the token symbol for a given token address."""
    try:
        token_data = await fetch_token_stats(token_address)  # Changed
        return token_data.get("symbol", "Unknown Token")
    except Exception as e:
        logger.error(f"Error fetching token symbol for {token_address}: {e}")
        return "Unknown Token"


async def format_transaction_details(tx: dict, wallet_address: str) -> str:  # Changed
    """Formats the details of a single transaction dictionary into a readable string,
    tailored to the perspective of the given wallet_address.
    """
    try:
        # Safely convert valueUsd to Decimal for formatting
        value_usd_str = tx.get("valueUsd", "0")
        value_usd = Decimal(value_usd_str) if value_usd_str else Decimal("0")
        # Format currency
        formatted_value = (
            f"${value_usd:,.2f}"  # Format with commas and 2 decimal places
        )
    except (InvalidOperation, TypeError):
        formatted_value = (
            f"${tx.get('valueUsd', 'N/A')}"  # Fallback if conversion fails
        )

    # Parse block time if available
    block_time = tx.get("blockTime")
    formatted_time = "N/A"
    if block_time:
        try:
            # Convert blockTime (usually Unix timestamp) to datetime
            dt = datetime.fromtimestamp(block_time)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            formatted_time = "N/A"

    # Safely get other fields with fallbacks
    signature = tx.get("signature", "N/A")
    sender = tx.get("senderAddress", "N/A")
    receiver = tx.get("receiverAddress", "N/A")
    # Construct the Solana Explorer link for the signature
    explorer_link = (
        f"https://solscan.io/tx/{signature}" if signature != "N/A" else "N/A"
    )

    # NEW LOGIC for symbol and amount_display
    amount_str = tx.get("calculatedAmount", "N/A")
    symbol_from_tx = tx.get("symbol")
    mint_address = tx.get("mintAddress")

    final_symbol = None
    final_symbol_known = False

    if symbol_from_tx:
        final_symbol = symbol_from_tx
        final_symbol_known = True
    elif mint_address:
        try:
            final_symbol = await get_token_symbol(mint_address)  # Changed
            if final_symbol:
                final_symbol_known = True
        except Exception:
            # If get_token_symbol fails, proceed to fallback (USD value)
            pass

    if final_symbol_known and amount_str != "N/A":
        amount_display = f"{amount_str} {final_symbol}"
    else:
        amount_display = formatted_value  # Fallback to USD value

    # Determine if the wallet is sender or receiver
    transaction_perspective = ""
    if sender == wallet_address:
        transaction_perspective = f"📤 *{wallet_address[:6]}...{wallet_address[-4:]} sent:* {amount_display} to `{receiver}`\n"
    elif receiver == wallet_address:
        transaction_perspective = f"📥 *{wallet_address[:6]}...{wallet_address[-4:]} received:* {amount_display} from `{sender}`\n"
    else:
        # Fallback if the wallet_address is neither sender nor receiver (should not happen in normal flow)
        transaction_perspective = (
            f"📤 *Sender:* `{sender}`\n📥 *Receiver:* `{receiver}`\n"
        )

    return (
        f"⏰ *Time:* {formatted_time}\n"
        f"💰 *Value (USD):* {formatted_value}\n"
        f"{transaction_perspective}"  # Use the new perspective string
        f"🔗 *Solscan:* [{signature[:8]}...{signature[-8:]}]({explorer_link})\n"
    )
