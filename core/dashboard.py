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
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
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
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
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
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
            },
        },
    )
    if wallet_address in user["wallets"]:
        user["wallets"].remove(wallet_address)
        _save_dashboard(data)
        return True
    return False


def set_whale_alert_threshold(user_id, threshold):
    data = _load_dashboard()
    user = data.setdefault(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
            },
        },
    )
    user["whale_alert"]["threshold"] = threshold
    _save_dashboard(data)


def get_whale_alert_threshold(user_id):
    data = _load_dashboard()
    user = data.get(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
            },
        },
    )
    return user["whale_alert"].get("threshold")


def set_whale_alerts_enabled(user_id, enabled):
    data = _load_dashboard()
    user = data.setdefault(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
            },
        },
    )
    user["whale_alert"]["enabled"] = enabled
    _save_dashboard(data)


def get_whale_alerts_enabled(user_id):
    data = _load_dashboard()
    user = data.get(
        str(user_id),
        {
            "wallets": [],
            "whale_alert": {
                "threshold": None,
                "enabled": False,
                "last_alerted_signature": None,
            },
        },
    )
    return user["whale_alert"].get("enabled", False)
