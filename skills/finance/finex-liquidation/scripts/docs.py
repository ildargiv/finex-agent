"""Официальные документы ликвидации: следит за страницами (сайт FinEx, ликвидатор, регуляторы, биржа),
находит НОВЫЕ PDF и изменения страниц, скачивает PDF в <FINEX_DESK>/docs/ и извлекает текст.

  python docs.py                    # проверить все страницы, показать новое
  python docs.py --list             # что уже в архиве (docs/index.jsonl)
  python docs.py --sources          # список отслеживаемых страниц
  python docs.py --add URL [--label "..."]   # добавить страницу (сохраняется в sources.json)
  python docs.py --get URL [--name 2026-10-update]   # скачать конкретный PDF/страницу в архив
  python docs.py --read URL_ИЛИ_ФАЙЛ --summary "главное из документа"   # отметить прочитанным

Страницы с JS-подгрузкой могут не отдавать список документов — тогда агент открывает их браузером
и сохраняет найденные PDF через --get. Для PDF нужен pypdf (pip install pypdf); без него PDF
сохраняется, но текст не извлекается.
"""
import argparse
import io
import os
import re
import urllib.parse

from _common import (fetch, html_text, links, sha, load_json, save_json, append_jsonl, read_jsonl,
                     journal, path, today, now)

DEFAULT_SOURCES = [
    {"url": "https://finexetf.com/library/liquidation-notices/", "label": "FinEx: уведомления о ликвидации"},
    {"url": "https://finexetf.com/library/", "label": "FinEx: библиотека документов"},
    {"url": "https://finexetf.com/library/fact-sheets/", "label": "FinEx: фактшиты (СЧА по фондам)"},
    {"url": "https://finexetf.com/library/financial-statements/", "label": "FinEx: финансовая отчётность ICAV"},
    {"url": "https://finexetf.com/library/legal-reports/", "label": "FinEx: юридические документы"},
    {"url": "https://finexetf.com/library/others/", "label": "FinEx: прочее"},
    {"url": "https://finexetf.com/about/", "label": "FinEx: о компании / ликвидаторы"},
    {"url": "https://finex-etf.ru/", "label": "FinEx: русский сайт"},
    {"url": "https://www.teneo.com/", "label": "Teneo (ликвидатор) — найти страницу дела и заменить"},
    {"url": "https://www.centralbank.ie/news-media/press-releases", "label": "Центральный банк Ирландии: пресс-релизы"},
    {"url": "https://www.moex.com/ru/news/", "label": "Мосбиржа: новости"},
    {"url": "https://www.nsd.ru/publications/news/", "label": "НРД: новости"},
]
KEYWORDS = re.compile(r"finex|ликвид|liquidat|icav|teneo|sanarus|FX[A-Z]{2}\b", re.I)


def sources():
    return load_json("sources.json", {"docs": DEFAULT_SOURCES}).get("docs", DEFAULT_SOURCES)


def save_sources(lst):
    s = load_json("sources.json", {})
    s["docs"] = lst
    save_json("sources.json", s)


def pdf_text(raw):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        r = PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception as e:
        return f"[не удалось извлечь текст: {e}]"


def slug(url):
    name = os.path.basename(urllib.parse.urlparse(url).path) or "page"
    return re.sub(r"[^\w.\-]+", "_", name)[:120]


def archive(url, name=None, label=""):
    """Скачать документ в docs/, извлечь текст, записать в индекс. Возвращает запись или None, если уже есть."""
    known = {d["url"] for d in read_jsonl("docs/index.jsonl")}
    if url in known:
        return None
    raw = fetch(url, binary=True)
    is_pdf = raw[:4] == b"%PDF"
    base = name or f"{today()}_{slug(url)}"
    if is_pdf and not base.lower().endswith(".pdf"):
        base += ".pdf"
    fn = path("docs", base)
    with open(fn, "wb") as f:
        f.write(raw)
    text = pdf_text(raw) if is_pdf else html_text(raw.decode("utf-8", "replace"))
    txt = None
    if text:
        txt = fn.rsplit(".", 1)[0] + ".txt"
        with open(txt, "w", encoding="utf-8") as f:
            f.write(text)
    rec = {"url": url, "label": label, "file": fn, "text": txt, "found": now(), "bytes": len(raw),
           "pdf": is_pdf, "status": "не прочитан"}
    append_jsonl("docs/index.jsonl", rec)
    journal(f"Документ: {label or base}", url)
    return rec


def check():
    state = load_json("docs/pages.json", {})
    new_docs, changed, errors = [], [], []
    for s in sources():
        url = s["url"]
        try:
            page = fetch(url)
        except Exception as e:
            errors.append(f"{url}: {e}")
            continue
        text = html_text(page)
        h = sha(text)
        prev = state.get(url, {})
        if prev and prev.get("hash") != h:
            changed.append(s)
            old = set(prev.get("lines", []))
            s["_new_lines"] = [ln for ln in text.split("\n") if len(ln) > 30 and sha(ln) not in old][:15]
        state[url] = {"hash": h, "checked": now(), "lines": [sha(ln) for ln in text.split("\n") if len(ln) > 30]}
        for link, label in links(page, url):
            if not link.lower().split("?")[0].endswith(".pdf"):
                continue
            if "finex" not in url and not KEYWORDS.search(link + " " + label):
                continue  # на чужих сайтах берём только PDF про FinEx
            try:
                rec = archive(link, label=label or s["label"])
            except Exception as e:
                errors.append(f"{link}: {e}")
                continue
            if rec:
                new_docs.append(rec)
    save_json("docs/pages.json", state)
    return new_docs, changed, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sources", action="store_true")
    ap.add_argument("--add")
    ap.add_argument("--label", default="")
    ap.add_argument("--get")
    ap.add_argument("--name")
    ap.add_argument("--read")
    ap.add_argument("--summary", default="")
    a = ap.parse_args()

    if a.read:
        import json
        recs = read_jsonl("docs/index.jsonl")
        hit = [r for r in recs if a.read in (r["url"], r["file"]) or a.read in r["file"]]
        if not hit:
            raise SystemExit("Нет такого документа в архиве (docs.py --list)")
        for r in hit:
            r["status"] = "прочитан"
            r["summary"] = a.summary
        p = path("docs", "index.jsonl")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(p + ".tmp", p)
        journal(f"Прочитан документ: {hit[0].get('label') or hit[0]['file']}: {a.summary}", hit[0]["url"])
        print("Отмечено прочитанным")
        return

    if a.add:
        lst = sources()
        if a.add not in [s["url"] for s in lst]:
            lst.append({"url": a.add, "label": a.label or a.add})
            save_sources(lst)
        print(f"Отслеживаю: {a.add}")
        return
    if a.sources:
        for s in sources():
            print(f"  {s['label']}\n    {s['url']}")
        return
    if a.get:
        rec = archive(a.get, a.name, a.label)
        print(f"Сохранено: {rec['file']}" + (f"\n  текст: {rec['text']}" if rec and rec['text'] else "") if rec
              else "Уже в архиве")
        return
    if a.list:
        for d in read_jsonl("docs/index.jsonl"):
            print(f"  {d['found']}  [{d.get('status')}] {d.get('label') or ''}\n    {d['url']}\n    {d['file']}")
        return

    new_docs, changed, errors = check()
    print(f"=== Документы: новых {len(new_docs)}, изменённых страниц {len(changed)} ===")
    for d in new_docs:
        print(f"  ⚑ НОВЫЙ: {d.get('label')}\n    {d['url']}\n    файл: {d['file']}" + (f"\n    текст: {d['text']}" if d.get('text') else ""))
    for s in changed:
        print(f"  ✎ изменилась страница: {s['label']} — {s['url']}")
        for ln in s.get("_new_lines", []):
            print(f"      + {ln[:200]}")
    for e in errors:
        print(f"  ! недоступно: {e}")
    if not new_docs and not changed:
        print("  нового нет (первый запуск только запоминает страницы)")


if __name__ == "__main__":
    main()
    import wiki  # база знаний Obsidian: заметки фондов и документов, index (references/wiki.md)
    wiki.safe_sync()
