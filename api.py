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
    """Fetch wallet activity from Vybe API starting from a specific date."""
    if startDate is None:
        # Calculate timestamp for 4 days ago
        startDate = int((datetime.now() - timedelta(days=5)).timestamp())
        
    url = f"{BASE_URL}/token/transfers?receiverAddress={wallet_address}&timeStart={startDate}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def get_wallet_token_balance(owner_address):
    """Fetch token balances for a specific wallet address from Vybe API."""
    url = f"{BASE_URL}/account/token-balance/{owner_address}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status() # Will raise an HTTPError for bad responses (4xx or 5xx)
    return response.json()


if __name__ == "__main__":
    # balance = get_wallet_token_balance("2ZoLadbpbRmuvF3QZh5sQUBngfnA823CaFRMaNaw1kJy")
    # print(balance)
    
    # activity = fetch_wallet_activity("HzsMcybwTDDEdAboNLo9TWT37s8WWuqjcdMGkQxbDuDn")
    # print(activity)


    transactions = fetch_whale_transactions()
    print(transactions)


    # token_stats = fetch_token_stats("6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN")

    # print(token_stats)
