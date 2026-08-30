from datetime import datetime

from app.collectors.twentyminut import _parse_article


HTML = """
<html><body>
<main>
  <h1>Куди піти, що побачити у вихідні 4-5 липня у Тернополі</h1>
  <p>Екскурсії, виставки, благодійний концерт, майстер-класи — у Тернополі цими вихідними буде чимало цікавого.</p>
  <p>4 липня, 12:00</p>
  <p>Екскурсія «Таємниці Старого Замку»</p>
  <p>Учасники завітають до Тернопільського замку.</p>
  <h2>Концерти</h2>
  <p>Благодійний концерт на підтримку ЗСУ «Тобі Україно, Вам Українці!» Муніципального духового оркестру «Оркестра Волі»</p>
  <p>Театральний майдан, Алея пам’яті «Незламні» поблизу скверу ім.Тараса Шевченка</p>
  <p>5 липня, 17.00</p>
  <h2>Майстерклас для дітей у книгарні</h2>
  <p>5 липня, 15:00, м. Тернопіль, вул. Валова 5-9</p>
  <p>Вхід вільний за попередньою реєстрацією у дірект книгарні.</p>
</main>
</body></html>
"""


def test_twentyminut_parses_observed_article_date_and_title_layout():
    events = _parse_article(
        HTML,
        "https://te.20minut.ua/Podii/example.html",
        datetime(2026, 7, 1, 12, 0),
    )
    assert len(events) == 3
    assert events[0].title == "Екскурсія «Таємниці Старого Замку»"
    assert events[0].start_at == datetime(2026, 7, 4, 12, 0)
    assert events[1].title.startswith("Благодійний концерт на підтримку ЗСУ")
    assert events[1].start_at == datetime(2026, 7, 5, 17, 0)
    assert events[2].title == "Майстерклас для дітей у книгарні"
    assert events[2].start_at == datetime(2026, 7, 5, 15, 0)
    assert events[2].venue == "м. Тернопіль, вул. Валова 5-9"


def test_twentyminut_does_not_emit_past_events():
    events = _parse_article(
        HTML,
        "https://te.20minut.ua/Podii/example.html",
        datetime(2026, 7, 5, 18, 0),
    )
    assert events == []
