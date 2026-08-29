from types import SimpleNamespace

from app.collectors import ixyt


LIVE_PAGE_HTML = '''
<html><body>
  <table>
    <tr>
      <td>Брешемо чисту правду</td>
      <td><a href="/event/breshuemo-chistu-pravdu">ДЕТАЛЬНІШЕ</a></td>
      <td>2026.09.07, 18:00</td>
      <td><a href="/event/breshuemo-chistu-pravdu">Квитки</a></td>
    </tr>
    <tr>
      <td>МАКС КІДРУК</td>
      <td><a href="/event/maks-kidruk">ДЕТАЛЬНІШЕ</a></td>
      <td>2026.11.18, 18:00</td>
      <td><a href="/event/maks-kidruk">Квитки</a></td>
    </tr>
  </table>
</body></html>
'''


def test_ixyt_contract_points_to_ternopil_catalog():
    assert ixyt.SOURCE_NAME == "iXYt.info"
    assert ixyt.BASE_URL == "https://ixyt.info/ua/Ukraine/Ternopil"


def test_ixyt_parses_observed_current_catalog_date_rows(monkeypatch):
    calls = {}

    def fake_get(url, **kwargs):
        calls.update(url=url, **kwargs)
        return SimpleNamespace(text=LIVE_PAGE_HTML, raise_for_status=lambda: None)

    monkeypatch.setattr(ixyt.httpx, "get", fake_get)

    result = ixyt.collect(timeout=7.5)

    assert len(result) == 2
    assert result[0].title == "Брешемо чисту правду"
    assert result[0].start_at.isoformat() == "2026-09-07T18:00:00"
    assert result[0].source_url.endswith("/event/breshuemo-chistu-pravdu")
    assert result[1].title == "МАКС КІДРУК"
    assert result[1].start_at.isoformat() == "2026-11-18T18:00:00"
    assert calls["url"] == ixyt.BASE_URL
    assert calls["timeout"] == 7.5


def test_ixyt_keeps_legacy_day_first_format_supported():
    assert ixyt._parse_start("07.09.2026, 18:00", __import__("datetime").datetime(2026, 8, 29, 12, 0)) == __import__("datetime").datetime(2026, 9, 7, 18, 0)
