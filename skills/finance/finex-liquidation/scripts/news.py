"""Новости о ликвидации FinEx из Google News RSS (RU и EN) и своих RSS-лент -> <FINEX_DESK>/news.jsonl без дублей.

  python news.py                     # новое с прошлого запуска
  python news.py --days 30 --all     # всё за 30 дней
  python news.py --tickers           # плюс запросы по тикерам из портфеля
  python news.py --add-query '"FinEx" НРД'    # свой запрос (запоминается)
  python news.py --add-feed URL               # свой RSS (запоминается)

Скрипт только собирает заголовки. ⚑-новости агент открывает и сверяет с первоисточником
(уведомления ликвидаторов, суд, ЦБ Ирландии, НРД, брокер) — см. references/sources.md.
"""
import argparse
import email.utils
import re
import urllib.parse
import xml.etree.ElementTree as ET

from _common import fetch, load_json, save_json, append_jsonl, read_jsonl, journal, sha, today, portfolio
import datetime as dt

GNEWS = "https://news.google.com/rss/search?{}"
DEFAULT_QUERIES = [
    ("FinEx ликвидация", "ru"),
    ("FinEx выплаты пайщикам", "ru"),
    ("FinEx Teneo", "ru"),
    ("фонды FinEx НРД", "ru"),
    ('"FinEx" ICAV liquidation', "en"),
    ('"FinEx" Teneo liquidators', "en"),
]
IMPORTANT = re.compile(
    r"выплат|распредел|лиценз|разрешени|санкц|OFAC|ЦБ Ирланд|Central Bank|суд|court|ликвидатор|liquidator|"
    r"Teneo|НРД|NSD|Euroclear|Clearstream|СЧА|NAV|стоимост|выкуп|дисконт|брокер|срок|дата|KYC|заявлен|"
    r"distribution|licen[cs]e|payment|redemption", re.I)


def gnews_url(q, lang, days):
    p = {"q": f"{q} when:{days}d", "hl": "ru" if lang == "ru" else "en",
         "gl": "RU" if lang == "ru" else "IE", "ceid": "RU:ru" if lang == "ru" else "IE:en"}
    return GNEWS.format(urllib.parse.urlencode(p))


def parse_rss(raw, feed):
    out = []
    root = ET.fromstring(raw)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src = it.find("source")
        source = src.text.strip() if src is not None and src.text else urllib.parse.urlparse(feed).netloc
        if title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        pub = it.findtext("pubDate")
        try:
            pub = email.utils.parsedate_to_datetime(pub).date().isoformat() if pub else None
        except (TypeError, ValueError):
            pub = None
        out.append({"title": title, "link": (it.findtext("link") or "").strip(), "source": source, "published": pub})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tickers", action="store_true")
    ap.add_argument("--add-query")
    ap.add_argument("--add-feed")
    a = ap.parse_args()

    cfg = load_json("sources.json", {})
    nc = cfg.setdefault("news", {"queries": [], "feeds": []})
    if a.add_query:
        nc["queries"].append(a.add_query)
    if a.add_feed:
        nc["feeds"].append(a.add_feed)
    if a.add_query or a.add_feed:
        save_json("sources.json", cfg)

    queries = list(DEFAULT_QUERIES) + [(q, "ru") for q in nc["queries"]]
    if a.tickers:
        queries += [(f'"{t}" FinEx', "ru") for t in portfolio()["positions"]]
    feeds = [gnews_url(q, lang, a.days) for q, lang in queries] + nc["feeds"]

    seen = {r["id"] for r in read_jsonl("news.jsonl")}
    new, errors = [], []
    for url in feeds:
        try:
            items = parse_rss(fetch(url).encode("utf-8"), url)
        except Exception as e:
            errors.append(str(e)[:200])
            continue
        for it in items:
            k = sha(re.sub(r"\W+", " ", it["title"].lower()))
            if k in seen or not it["title"]:
                continue
            seen.add(k)
            rec = {"id": k, "first_seen": today(), **it, "important": bool(IMPORTANT.search(it["title"]))}
            append_jsonl("news.jsonl", rec)
            new.append(rec)
    if new:
        journal(f"Новости: +{len(new)} (⚑ {sum(r['important'] for r in new)})", "news.jsonl")

    if a.all:
        since = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
        shown = [r for r in read_jsonl("news.jsonl") if (r.get("published") or r["first_seen"]) >= since]
    else:
        shown = new
    shown.sort(key=lambda r: r.get("published") or "", reverse=True)
    print(f"=== Новости FinEx: новых {len(new)} ===")
    for r in shown[:60]:
        print(f"  {'⚑' if r['important'] else ' '} {r.get('published') or '????-??-??'} [{r['source']}] {r['title']}\n      {r['link']}")
    for e in errors:
        print(f"  ! лента недоступна: {e}")
    if not shown:
        print("  нет " + ("новостей за окно" if a.all else "новых новостей"))


if __name__ == "__main__":
    main()
