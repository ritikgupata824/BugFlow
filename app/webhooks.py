import requests


def send_webhook(event: str, data: dict):
    webhook_url = "https://httpbin.org/post"

    payload = {
        "event": event,
        "data": data
    }

    response = requests.post(
        webhook_url,
        json=payload,
        timeout=10
    )

    return {
        "status_code": response.status_code,
        "success": response.ok
    }