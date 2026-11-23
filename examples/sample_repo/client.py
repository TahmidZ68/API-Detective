"""Sample Python API integration with common integration defects for repository inspection."""

import os
import requests

API_BASE = "https://api.orders.example.com/v1"
API_TOKEN = os.getenv("ORDERS_API_TOKEN")
WEBHOOK_SECRET = os.environ.get("MISSING_WEBHOOK_SECRET")


def fetch_customer_orders(customer_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer Bearer {API_TOKEN}",
        "Accept": "application/json",
    }
    response = requests.get(f"{API_BASE}/orders", headers=headers, verify=False)
    return response.json()
