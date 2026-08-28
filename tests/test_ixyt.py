from types import SimpleNamespace

from app.collectors import ixyt


LIVE_PAGE_HTML = '''
<html><body>
  <table>
    <tr>
      <td>Брешемо чисту правду</td>
      <td><a href="/event/breshuemo-chistu-pravdu">MORE</a></td>
      <td>07.09.2026, 18:00</td>
    </tr>
    <tr>
      <td>Гра</td>
      <td><a href="/event/gra">MORE</a></td>
      <td>18.11.2026, 18:00</td>
    </tr>
  </table>
</body></html>
'''


def test_ixyt_contract_points_to_ternopil_catalog():
    assert ixyt.SOURCE_NAME == "iXYt.info"
    assert ixyt.BASE_URL == "https://ixyt.info/ua/Ukraine/Ternopil"


def test_ixyt_parses_observed_more_link_event_rows(monkeypatch):
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
    assert result[1].title == "Гра"
    assert result[1].start_at.isoformat() == "2026-11-18T18:00:00"
    assert calls["url"] == ixyt.BASE_URL
    assert calls["timeout"] == 7.5
