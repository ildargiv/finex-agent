"""Форумы и публичные Telegram-каналы: забирает страницы, вычленяет НОВЫЕ сообщения с прошлого запуска,
кладёт их в <FINEX_DESK>/forums/<дата>.md (статус «💬 не проверено»).

  python forums.py                       # проверить все источники
  python forums.py --sources             # список
  python forums.py --add URL [--label "..."]   # форум, ветка или публичный канал (https://t.me/s/<канал>)
  python forums.py --remove URL

Публичный Telegram-канал читается через веб-превью https://t.me/s/<имя_канала>. Закрытые группы
так не читаются — их пользователь пересылает сам, агент сохраняет через intake.py.
Сообщения форумов — гипотезы, пока не подтверждены первоисточником (references/sources.md).
"""
import argparse
import html as _h
import re

from _common import fetch, html_text, load_json, save_json, journal, sha, path, today, now

DEFAULT_FORUMS = [
    {"url": "https://smart-lab.ru/trading/finex-etf", "label": "Smart-Lab: FinEx ETF (общая ветка)"},
    {"url": "https://smart-lab.ru/forum/FXUS", "label": "Smart-Lab: форум FXUS"},
    {"url": "https://smart-lab.ru/forum/FXIT", "label": "Smart-Lab: форум FXIT"},
    {"url": "https://smart-lab.ru/forum/FXGD", "label": "Smart-Lab: форум FXGD"},
    {"url": "https://t.me/s/UnblockLegal", "label": "Telegram: UnblockLegal (юристы по разблокировке)"},
]
KEY = re.compile(r"finex|финекс|ликвид|выплат|teneo|нрд|выкуп|СЧА|FX[A-Z]{2}", re.I)


def sources():
    return load_json("sources.json", {}).get("forums", DEFAULT_FORUMS)


def save_sources(lst):
    s = load_json("sources.json", {})
    s["forums"] = lst
    save_json("sources.json", s)


def posts(url, page):
    """Список сообщений страницы. Telegram — по блокам сообщений, прочее — абзацы текста."""
    if "t.me/s/" in url:
        out = []
        for block in re.findall(r'(?s)<div class="tgme_widget_message_wrap.*?(?=<div class="tgme_widget_message_wrap|$)', page):
            m = re.search(r'(?s)class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block)
            if not m:
                continue
            text = _h.unescape(re.sub(r"<br\s*/?>", "\n", m.group(1)))
            text = re.sub(r"<[^>]+>", "", text).strip()
            d = re.search(r'datetime="([^"]+)"', block)
            link = re.search(r'class="tgme_widget_message_date" href="([^"]+)"', block)
            out.append({"text": text, "date": d.group(1)[:16] if d else "", "link": link.group(1) if link else url})
        return out
    lines = [ln for ln in html_text(page).split("\n") if len(ln) >= 60]
    return [{"text": ln, "date": "", "link": url} for ln in lines]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", action="store_true")
    ap.add_argument("--add")
    ap.add_argument("--label", default="")
    ap.add_argument("--remove")
    ap.add_argument("--all-text", action="store_true", help="не фильтровать по ключевым словам")
    a = ap.parse_args()

    lst = sources()
    if a.add:
        if a.add not in [s["url"] for s in lst]:
            lst.append({"url": a.add, "label": a.label or a.add})
            save_sources(lst)
        print(f"Отслеживаю: {a.add}")
        return
    if a.remove:
        save_sources([s for s in lst if s["url"] != a.remove])
        print(f"Удалено: {a.remove}")
        return
    if a.sources:
        for s in lst:
            print(f"  {s['label']}\n    {s['url']}")
        return

    seen = load_json("forums/seen.json", {})
    report, errors, total = [], [], 0
    for s in lst:
        url = s["url"]
        try:
            page = fetch(url)
        except Exception as e:
            errors.append(f"{url}: {e}")
            continue
        first = url not in seen
        known = set(seen.get(url, []))
        fresh = []
        for p in posts(url, page):
            h = sha(p["text"])
            if h in known:
                continue
            known.add(h)
            if a.all_text or "t.me/" in url or KEY.search(p["text"]):
                fresh.append(p)
        seen[url] = list(known)[-5000:]
        if first:
            fresh = fresh[-10:]  # первый запуск: только последние сообщения, чтобы не тонуть в архиве
        if fresh:
            total += len(fresh)
            report.append((s, fresh))
    save_json("forums/seen.json", seen)

    if report:
        fn = path("forums", f"{today()}.md")
        with open(fn, "a", encoding="utf-8") as f:
            f.write(f"\n## Сбор {now()}\n")
            for s, fresh in report:
                f.write(f"\n### {s['label']} — {s['url']}\n")
                for p in fresh:
                    f.write(f"- 💬 {p['date']} {p['text'][:1500]}  \n  ({p['link']})\n")
        journal(f"Форумы: +{total} сообщений", fn)
    print(f"=== Форумы/Telegram: новых сообщений {total} ===")
    for s, fresh in report:
        print(f"\n  {s['label']} (+{len(fresh)})")
        for p in fresh[-15:]:
            print(f"    • {p['date']} {p['text'][:300]}")
    for e in errors:
        print(f"  ! недоступно: {e}")


if __name__ == "__main__":
    main()
