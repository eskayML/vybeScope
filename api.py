import asyncio
import os
from datetime import datetime, timedelta

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# Base URLs for Vybe API
BASE_URL = "https://api.vybenetwork.xyz"
HEADERS = {"accept": "application/json", "x-api-key": os.getenv("VYBE_API_KEY")}


async def fetch_token_stats(token_address):
    """Fetch token stats from Vybe API."""
    url = f"{BASE_URL}/token/{token_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            return await response.json()


async def fetch_whale_transaction(min_amount_usd=50000):
    """Fetch whale transactions from Vybe API."""
    if min_amount_usd is None:
        min_amount_usd = 50000

    alert_intervals = int(os.getenv("WHALE_ALERT_INTERVAL_SECONDS", 60))
    start_date = int(
        (datetime.now() - timedelta(seconds=alert_intervals - 2)).timestamp()
    )
    url = f"{BASE_URL}/token/transfers?timeStart={start_date}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            data = await response.json()

    transactions = data.get("transfers", [])

    if not transactions:
        return None

    # Get the top 10 transactions sorted by USD value
    top_transactions = sorted(
        transactions, key=lambda x: float(x.get("valueUsd", 0)), reverse=True
    )[:10]

    # Loop through each transaction to fetch the token symbol using mintAddress
    tasks = []
    for transaction in top_transactions:
        mint_address = transaction.get("mintAddress")
        if mint_address:
            tasks.append(asyncio.ensure_future(fetch_token_stats(mint_address)))

    # Wait for all tasks to complete
    token_stats_results = await asyncio.gather(*tasks)

    # Assign the results back to the transactions
    for i, transaction in enumerate(top_transactions):
        mint_address = transaction.get("mintAddress")
        if mint_address:
            if i < len(token_stats_results) and token_stats_results[i]:
                transaction["tokenSymbol"] = token_stats_results[i].get("symbol", "SOL")
            else:
                transaction["tokenSymbol"] = "SOL"

    return top_transactions


async def fetch_whale_transaction_for_single_token(
    mintAddress, min_amount_usd=50000, limit=1000
):
    """Fetch whale transactions from Vybe API for a single token and return the one with the maximum USD value."""

    if min_amount_usd is None:
        min_amount_usd = 50000

    alert_intervals = int(os.getenv("WHALE_ALERT_INTERVAL_SECONDS", 60))
    start_date = int(
        (datetime.now() - timedelta(seconds=alert_intervals - 2)).timestamp()
    )

    url = f"{BASE_URL}/token/transfers?mintAddress={mintAddress}&timeStart={start_date}&limit={limit}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            data = await response.json()
    transactions = data.get("transfers", [])

    if not transactions:
        return None

    max_transaction = max(transactions, key=lambda x: float(x.get("valueUsd", 0)))

    # Fetch token stats to get the token symbol
    token_stats_data = await fetch_token_stats(mintAddress)
    max_transaction["tokenSymbol"] = token_stats_data.get("symbol", "SOL")

    return max_transaction


async def fetch_wallet_activity(wallet_address, startDate=None):
    """Fetch wallet activity for a wallet as both sender and receiver, sorted by most recent blockTime."""
    if startDate is None:
        startDate = int((datetime.now() - timedelta(days=5)).timestamp())

    receiver_url = f"{BASE_URL}/token/transfers?receiverAddress={wallet_address}&timeStart={startDate}&limit=10"
    sender_url = f"{BASE_URL}/token/transfers?senderAddress={wallet_address}&timeStart={startDate}&limit=10"

    async with aiohttp.ClientSession() as session:
        async with (
            session.get(receiver_url, headers=HEADERS) as receiver_response,
            session.get(sender_url, headers=HEADERS) as sender_response,
        ):
            receiver_response.raise_for_status()
            sender_response.raise_for_status()

            receiver_data_json = await receiver_response.json()
            sender_data_json = await sender_response.json()

    receiver_data = receiver_data_json.get("transfers", [])
    sender_data = sender_data_json.get("transfers", [])

    combined = receiver_data + sender_data
    # Filter transactions by valueUsd > 0.01
    filtered_transactions = [
        tx for tx in combined if float(tx.get("valueUsd", 0)) > 0.01
    ]
    combined_sorted = sorted(
        filtered_transactions, key=lambda x: x.get("blockTime", 0), reverse=True
    )
    return combined_sorted


async def fetch_recent_wallet_transactions(wallet_address, seconds_ago=120):
    """Fetch recent wallet transactions within the specified seconds."""
    start_date = int((datetime.now() - timedelta(seconds=seconds_ago)).timestamp())

    receiver_url = f"{BASE_URL}/token/transfers?receiverAddress={wallet_address}&timeStart={start_date}&limit=10"
    sender_url = f"{BASE_URL}/token/transfers?senderAddress={wallet_address}&timeStart={start_date}&limit=10"

    async with aiohttp.ClientSession() as session:
        async with (
            session.get(receiver_url, headers=HEADERS) as receiver_response,
            session.get(sender_url, headers=HEADERS) as sender_response,
        ):
            receiver_response.raise_for_status()
            sender_response.raise_for_status()

            receiver_data_json = await receiver_response.json()
            sender_data_json = await sender_response.json()

    receiver_data = receiver_data_json.get("transfers", [])
    sender_data = sender_data_json.get("transfers", [])

    combined = receiver_data + sender_data
    # Filter transactions by valueUsd > 0.01
    filtered_transactions = [
        tx for tx in combined if float(tx.get("valueUsd", 0)) > 0.01
    ]
    combined_sorted = sorted(
        filtered_transactions, key=lambda x: x.get("blockTime", 0), reverse=True
    )
    return combined_sorted


async def get_wallet_token_balance(owner_address):
    """Fetch token balances for a specific wallet address from Vybe API."""
    url = f"{BASE_URL}/account/token-balance/{owner_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()  # Will raise an HTTPError for bad responses (4xx or 5xx)
            return await response.json()


async def fetch_top_token_holders(mint_address, count=5):
    """
    Fetch the top holders of a token from Vybe API.

    Args:
        mint_address (str): The token's mint address.
        count (int): Number of top holders to return. Defaults to 10.

    Returns:
        list of dict: Top token holders.
    """
    url = f"{BASE_URL}/token/{mint_address}/top-holders"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            response.raise_for_status()
            data = await response.json()
    return data.get("data", [])[:count]


async def main():
    # balance = await get_wallet_token_balance("2ZoLadbpbRmuvF3QZh5sQUBngfnA823CaFRMaNaw1kJy")
    # print(balance)

    # print("WALLET ACTIVITY")
    # activity = await fetch_wallet_activity("J7tQpK2sQE1xknVmYbjPDg4kcThK1NHXQ3kZrSAuBrah")
    # print(activity)
    recent = await fetch_recent_wallet_transactions(
        "J7tQpK2sQE1xknVmYbjPDg4kcThK1NHXQ3kZrSAuBrah", seconds_ago=12000
    )
    print(recent)
    # top_holders = await fetch_top_token_holders("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN")
    # print(top_holders)

    # token_whales = await fetch_whale_transaction_for_single_token(
    #     "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"
    # )
    # print(token_whales)

    # print("WHALE TRANSACTION")
    # transactions = await fetch_whale_transaction()
    # print(transactions)

    # token_stats = await fetch_token_stats("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN")
    # print(token_stats)


if __name__ == "__main__":
    asyncio.run(main())
