import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

# Base URLs for Vybe API
BASE_URL = "https://api.vybenetwork.xyz"
HEADERS = {"accept": "application/json", "x-api-key": os.getenv("VYBE_API_KEY")}


def fetch_whale_transactions(min_amount_usd=50000, limit=2):
    """Fetch whale transactions from Vybe API."""
    url = f"{BASE_URL}/token/transfers?minAmount={min_amount_usd}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def fetch_token_stats(token_address):
    """Fetch token stats from Vybe API."""
    url = f"{BASE_URL}/token/{token_address}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def fetch_wallet_activity(wallet_address, startDate=None):
    """Fetch wallet activity for a wallet as both sender and receiver, sorted by most recent blockTime."""
    if startDate is None:
        startDate = int((datetime.now() - timedelta(days=5)).timestamp())

    receiver_url = f"{BASE_URL}/token/transfers?receiverAddress={wallet_address}&timeStart={startDate}&limit=5"
    sender_url = f"{BASE_URL}/token/transfers?senderAddress={wallet_address}&timeStart={startDate}&limit=5"

    receiver_response = requests.get(receiver_url, headers=HEADERS)
    sender_response = requests.get(sender_url, headers=HEADERS)
    receiver_response.raise_for_status()
    sender_response.raise_for_status()

    receiver_data = receiver_response.json().get("transfers", [])
    sender_data = sender_response.json().get("transfers", [])

    combined = receiver_data + sender_data
    combined_sorted = sorted(combined, key=lambda x: x.get("blockTime", 0), reverse=True)
    return combined_sorted

def get_wallet_token_balance(owner_address):
    """Fetch token balances for a specific wallet address from Vybe API."""
    url = f"{BASE_URL}/account/token-balance/{owner_address}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status() # Will raise an HTTPError for bad responses (4xx or 5xx)
    return response.json()


def fetch_top_token_holders(mint_address, count=5):
    """
    Fetch the top holders of a token from Vybe API.

    Args:
        mint_address (str): The token's mint address.
        count (int): Number of top holders to return. Defaults to 10.

    Returns:
        list of dict: Top token holders.
    """
    url = f"{BASE_URL}/token/{mint_address}/top-holders"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])[:count]


if __name__ == "__main__":
    # balance = get_wallet_token_balance("2ZoLadbpbRmuvF3QZh5sQUBngfnA823CaFRMaNaw1kJy")
    # print(balance)
    
    activity = fetch_wallet_activity("J7tQpK2sQE1xknVmYbjPDg4kcThK1NHXQ3kZrSAuBrah")
    print(activity)

    # top_holders = fetch_top_token_holders("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN")
    # print(top_holders)

    # transactions = fetch_whale_transactions()
    # print(transactions)

    # token_stats = fetch_token_stats("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN")

    # print(token_stats)
