import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.jobs.daily_digest import build_tomorrow_digest
from app.services.telegram_delivery import TelegramDelivery


KYIV = ZoneInfo("Europe/Kyiv")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured")

    now = datetime.now(timezone.utc).astimezone(KYIV)
    digest = build_tomorrow_digest(now)

    delivery = TelegramDelivery(token)
    try:
        delivery.send_message(int(chat_id), digest)
    finally:
        delivery.close()

    print(f"Daily digest delivered for {now.date().isoformat()} (Kyiv time)")


if __name__ == "__main__":
    main()
