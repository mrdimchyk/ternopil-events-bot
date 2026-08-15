from datetime import datetime
from pathlib import Path

import httpx

from app.collectors.karabas import JINA_PREFIX, _month_urls

OUT = Path("karabas-production-responses")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    headers = {
        "User-Agent": "TernopilEventsBot/1.0 (+https://github.com/mrdimchyk/ternopil-events-bot)",
        "Accept": "text/plain,text/markdown,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.7",
    }

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for index, url in enumerate(_month_urls(now)):
            path = OUT / f"{index:02d}.txt"
            jina_url = JINA_PREFIX + url
            try:
                response = client.get(jina_url)
                path.write_text(
                    f"REQUEST: {jina_url}\nSTATUS: {response.status_code}\n\n{response.text}",
                    encoding="utf-8",
                )
            except Exception as exc:
                path.write_text(
                    f"REQUEST: {jina_url}\nERROR: {type(exc).__name__}: {exc}\n",
                    encoding="utf-8",
                )


if __name__ == "__main__":
    main()
