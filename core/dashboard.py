import json
import os
from threading import Lock

DASHBOARD_FILE = os.path.join(os.path.dirname(__file__), "..", "user_dashboard.json")
_dashboard_lock = Lock()


def _load_dashboard():
    if not os.path.exists(DASHBOARD_FILE):
        return {}
    with open(DASHBOARD_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def _save_dashboard(data):
    with _dashboard_lock:
        with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def get_user_dashboard(user_id):
    data = _load_dashboard()
    return data.get(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "tokens": {},
            },
        },
    )


def add_tracked_wallet(user_id, wallet_address):
    data = _load_dashboard()
    user = data.setdefault(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "tokens": {},
            },
        },
    )
    if wallet_address not in user["wallets"]:
        user["wallets"].append(wallet_address)
        _save_dashboard(data)
        return True
    return False


def remove_tracked_wallet(user_id, wallet_address):
    data = _load_dashboard()
    user = data.setdefault(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "tokens": {},
            },
        },
    )
    if wallet_address in user["wallets"]:
        user["wallets"].remove(wallet_address)
        _save_dashboard(data)
        return True
    return False


def clear_user_dashboard(user_id):
    """Remove all dashboard data for a user."""
    data = _load_dashboard()
    if str(user_id) in data:
        del data[str(user_id)]
        _save_dashboard(data)
        return True
    return False


# --- Whale Alert Token Management ---
def add_tracked_whale_alert_token(
    user_id, token_address, enabled=True, threshold=50000
):
    data = _load_dashboard()
    user = data.setdefault(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "tokens": {},
            },
        },
    )
    whale_alert = user["whale_alert"]
    if "tokens" not in whale_alert or not isinstance(whale_alert["tokens"], dict):
        whale_alert["tokens"] = {}
    if token_address not in whale_alert["tokens"]:
        whale_alert["tokens"][token_address] = {
            "enabled": enabled,
            "threshold": threshold,
        }
        _save_dashboard(data)
        return True
    return False


def remove_tracked_whale_alert_token(user_id, token_address):
    data = _load_dashboard()
    user = data.setdefault(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "tokens": {},
            },
        },
    )
    whale_alert = user["whale_alert"]
    if "tokens" not in whale_alert or not isinstance(whale_alert["tokens"], dict):
        whale_alert["tokens"] = {}
    if token_address in whale_alert["tokens"]:
        del whale_alert["tokens"][token_address]
        _save_dashboard(data)
        return True
    return False


def get_tracked_whale_alert_tokens(user_id):
    data = _load_dashboard()
    user = data.get(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "tokens": {},
            },
        },
    )
    whale_alert = user["whale_alert"]
    if "tokens" not in whale_alert or not isinstance(whale_alert["tokens"], dict):
        return []
    return list(whale_alert["tokens"].keys())


def get_token_alert_settings(user_id, token_address):
    data = _load_dashboard()
    user = data.get(str(user_id), {})
    whale_alert = user.get("whale_alert", {})
    tokens = whale_alert.get("tokens", {})
    return tokens.get(token_address, {"enabled": False, "threshold": 50000})


def set_token_alert_enabled(user_id, token_address, enabled):
    data = _load_dashboard()
    user = data.setdefault(str(user_id), {"wallets": [], "whale_alert": {"tokens": {}}})
    whale_alert = user["whale_alert"]
    if "tokens" not in whale_alert or not isinstance(whale_alert["tokens"], dict):
        whale_alert["tokens"] = {}
    if token_address not in whale_alert["tokens"]:
        whale_alert["tokens"][token_address] = {"enabled": enabled, "threshold": 50000}
    else:
        whale_alert["tokens"][token_address]["enabled"] = enabled
    _save_dashboard(data)


def set_token_alert_threshold(user_id, token_address, threshold):
    data = _load_dashboard()
    user = data.setdefault(str(user_id), {"wallets": [], "whale_alert": {"tokens": {}}})
    whale_alert = user["whale_alert"]
    if "tokens" not in whale_alert or not isinstance(whale_alert["tokens"], dict):
        whale_alert["tokens"] = {}
    if token_address not in whale_alert["tokens"]:
        whale_alert["tokens"][token_address] = {"enabled": True, "threshold": threshold}
    else:
        whale_alert["tokens"][token_address]["threshold"] = threshold
    _save_dashboard(data)


def set_whale_alerts_enabled(user_id, enabled):
    # Deprecated function, kept for compatibility but does nothing
    pass


def get_whale_alerts_enabled(user_id):
    # Deprecated function, kept for compatibility but always returns True
    return True
