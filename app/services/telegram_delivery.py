import httpx


class TelegramDeliveryError(RuntimeError):
    pass


class TelegramDelivery:
    def __init__(self, token: str, client: httpx.Client | None = None):
        if not token:
            raise ValueError("Telegram bot token is required")
        self.token = token
        self.client = client or httpx.Client(timeout=20.0)
        self._owns_client = client is None

    def send_message(self, chat_id: int, text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        response = self.client.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
        if response.status_code >= 400:
            raise TelegramDeliveryError(f"Telegram API HTTP {response.status_code}")
        payload = response.json()
        if not payload.get("ok"):
            raise TelegramDeliveryError("Telegram API rejected sendMessage")
        return True

    def close(self) -> None:
        if self._owns_client:
            self.client.close()


class FakeTelegramDelivery:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> bool:
        self.messages.append((chat_id, text))
        return True
