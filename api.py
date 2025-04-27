import os

import requests
from dotenv import load_dotenv

load_dotenv()

# Base URLs for Vybe API
BASE_URL = "https://api.vybenetwork.xyz"
HEADERS = {"accept": "application/json", "x-api-key": os.getenv("VYBE_API_KEY")}


def fetch_transactions(min_amount_usd=50000, limit=2):
    """Fetch whale transactions from Vybe API."""
    url = f"{BASE_URL}/token/transfers?min_amount_usd={min_amount_usd}&limit={limit}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def fetch_token_stats(token_address):
    """Fetch token stats from Vybe API."""
    url = f"{BASE_URL}/token/{token_address}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def fetch_wallet_activity(wallet_address, limit=5):
    """Fetch wallet activity from Vybe API."""
    url = f"{BASE_URL}/token/transfers?address={wallet_address}&limit={limit}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    # Example usage
    transactions = fetch_transactions()
    print("Transactions:", transactions)

    