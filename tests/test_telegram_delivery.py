import httpx
import pytest

from app.services.telegram_delivery import FakeTelegramDelivery, TelegramDelivery, TelegramDeliveryError


def test_fake_delivery_records_message_once_per_call():
    delivery = FakeTelegramDelivery()
    assert delivery.send_message(123, "hello") is True
    assert delivery.messages == [(123, "hello")]


def test_real_delivery_sends_expected_telegram_request():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    delivery = TelegramDelivery("test-token", client=client)
    assert delivery.send_message(123456, "Привіт") is True
    assert requests[0].url == "https://api.telegram.org/bottest-token/sendMessage"
    assert requests[0].content == b"chat_id=123456&text=%D0%9F%D1%80%D0%B8%D0%B2%D1%96%D1%82&parse_mode=HTML"
    client.close()


def test_real_delivery_rejects_http_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    delivery = TelegramDelivery("test-token", client=client)
    with pytest.raises(TelegramDeliveryError):
        delivery.send_message(123456, "hello")
    client.close()


def test_real_delivery_rejects_telegram_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": False})))
    delivery = TelegramDelivery("test-token", client=client)
    with pytest.raises(TelegramDeliveryError):
        delivery.send_message(123456, "hello")
    client.close()
