from datetime import datetime

from app.collectors.ternopilcity import _extract_rows, _find_latest_plan


def test_find_latest_plan_uses_real_homepage_link_contract():
    html = """
    <div id="news">
      <a href="/news/101519.html">Зведений робочий план міського голови та виконавчих органів Тернопільської міської ради на серпень 2026 року</a>
      <a href="/news/102577.html">Зведений робочий план міського голови та виконавчих органів Тернопільської міської ради на вересень 2026 року</a>
    </div>
    """
    assert _find_latest_plan("https://ternopilcity.gov.ua/", html) == "https://ternopilcity.gov.ua/news/102577.html"


def test_extract_rows_parses_observed_work_plan_table():
    html = """
    <table>
      <tr><td>1.</td><td>Музична програма присвячена Дню знань</td><td>01.09.2026 16.00 год</td><td>Тернопільська музична школа № 2 ім. Михайла Вербицького, Нижній зал, вул. Захисників України, 4</td></tr>
      <tr><td>2.</td><td>Проведення Загальнонаціонального уроку пам’яті</td><td>Перший тиждень вересня</td><td>Заклади освіти</td></tr>
    </table>
    """
    events = _extract_rows("https://ternopilcity.gov.ua/news/102577.html", html)
    assert len(events) == 1
    assert events[0].title == "Музична програма присвячена Дню знань"
    assert events[0].start_at == datetime(2026, 9, 1, 16, 0)
    assert "Захисників України" in (events[0].venue or "")
    assert events[0].source_url.endswith("/102577.html")


def test_extract_rows_deduplicates_identical_rows():
    row = "<tr><td>1.</td><td>Подія</td><td>03.09.2026 11.00 год</td><td>Центр Garta</td></tr>"
    events = _extract_rows("https://ternopilcity.gov.ua/news/102577.html", f"<table>{row}{row}</table>")
    assert len(events) == 1
