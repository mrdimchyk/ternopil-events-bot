import hashlib, re
from datetime import datetime
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from app.collectors.base import RawEvent

BASE_URL = "https://ternopil.karabas.com/"
MONTHS = {"січня":1,"лютого":2,"березня":3,"квітня":4,"травня":5,"червня":6,"липня":7,"серпня":8,"вересня":9,"жовтня":10,"листопада":11,"грудня":12}

def _external_id(url,title,start_at):
    raw=f"{url}|{title}|{start_at.isoformat() if start_at else ''}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

def _clean(text): return " ".join(text.split())

def _parse_date_time(text, now=None):
    m=re.search(r"(\d{1,2}).*?(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня).*?(20\d{2}).*?(\d{1,2}):(\d{2})",text,re.I)
    if not m: return None
    day,month,year,hour,minute=m.groups()
    return datetime(int(year),MONTHS[month.lower()],int(day),int(hour),int(minute))

def collect(timeout=20.0):
    r=httpx.get(BASE_URL,headers={"User-Agent":"TernopilEventsBot/0.1"},timeout=timeout,follow_redirects=True)
    r.raise_for_status(); soup=BeautifulSoup(r.text,"lxml"); results=[]; seen=set()
    for link in soup.select("a[href]"):
        href=urljoin(BASE_URL,link.get("href","")); title=_clean(link.get_text(" ",strip=True))
        if not title or href in seen or "karabas.com" not in href or href.rstrip("/")==BASE_URL.rstrip("/"): continue
        container=link
        for _ in range(4):
            if container.parent: container=container.parent
        block=_clean(container.get_text(" ",strip=True))
        if "Тернопіль" not in block or not re.search(r"\b20\d{2}\b",block) or not re.search(r"\b\d{1,2}:\d{2}\b",block): continue
        start_at=_parse_date_time(block)
        if not start_at: continue
        pm=re.search(r"(\d[\d\s]*)\s*(?:-|–)\s*(\d[\d\s]*)\s*грн|([\d\s]+)\s*грн",block)
        low=block.lower(); category=None
        if "теат" in low: category="theatre"
        elif "стендап" in low: category="standup"
        elif "фестив" in low: category="festival"
        elif "концерт" in low: category="concert"
        results.append(RawEvent(_external_id(href,title,start_at),title,category,start_at,None,None,pm.group(0) if pm else None,href,href))
        seen.add(href)
    return list({e.external_id:e for e in results}.values())
