def format_top_holders_text(top_holders):
    """
    Format the top holders data into a readable, emoji-rich text list with bolded keys.
    Args:
        top_holders (list of dict): Output from fetch_top_token_holders.
    Returns:
        str: Formatted text as a string.
    """
    if not top_holders:
        return "No top holders data available."

    lines = ["🏆 <b>Top Token Holders:</b>"]
    for holder in top_holders:
        rank = holder.get("rank", "-")
        owner = holder.get("ownerName") or holder.get("ownerAddress")
        balance = f"{float(holder.get('balance', 0)):.2f}"
        value_usd = f"${float(holder.get('valueUsd', 0)):,.2f}"
        percent = f"{float(holder.get('percentageOfSupplyHeld', 0)):.4f}%"
        symbol = holder.get("tokenSymbol", "-")
        line = (
            f"<b>#{rank}</b> 👤 <b>Owner:</b> {owner}\n"
            f"   💰 <b>Balance:</b> {balance} <b>{symbol}</b> \n"
            f"   💵 <b>Value:</b> {value_usd}\n"
            f"   📊 <b>Supply:</b> {percent}\n"
        )
        lines.append(line)
    return "\n".join(lines)
