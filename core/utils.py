from datetime import datetime
from decimal import Decimal, InvalidOperation


def format_transaction_details(tx: dict) -> str:
    """Formats the details of a single transaction dictionary into a readable string."""
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
    # Format amount and symbol (assuming 'calculatedAmount' and 'symbol' might exist)
    amount_str = tx.get("calculatedAmount", "N/A")
    symbol = tx.get(
        "symbol", tx.get("mintAddress", "Unknown Token")
    )  # Prefer symbol if available
    amount_display = f"{amount_str} {symbol}" if amount_str != "N/A" else "N/A"

    return (
        f"⏰ *Time:* {formatted_time}\n"
        f"💰 *Value (USD):* {formatted_value}\n"
        f"📊 *Amount:* {amount_display}\n"
        f"🔗 *Signature:* [{signature[:8]}...{signature[-8:]}]({explorer_link})\n"
        f"📤 *Sender:* `{sender}`\n"
        f"📥 *Receiver:* `{receiver}`\n"
    )
