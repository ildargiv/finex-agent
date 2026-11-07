"""Портфель паёв FinEx пользователя. Хранится ТОЛЬКО локально: <FINEX_DESK>/portfolio.json (~/finex-desk).

  python portfolio.py list                          # позиции и справочные данные фондов
  python portfolio.py add FXUS 100 [--note "..."]   # добавить/изменить количество
  python portfolio.py remove FXUS
  python portfolio.py import отчёт.ods|.xlsx|.csv   # вытащить ISIN и количество из отчёта депозитария/брокера
  python portfolio.py import отчёт.ods --dry-run    # только показать, что найдено
  python portfolio.py fund FXKZ --isin IE00... --ccy USD --name "..."   # уточнить справочник фондов
  python portfolio.py funds                         # весь справочник известных фондов FinEx

Импорт ищет строки с ISIN фондов FinEx (IE...), тикер определяет по ISIN из funds.json или по названию фонда
(Gold -> FXGD, Germany -> FXDE, ...), количество берёт из ПОСЛЕДНЕЙ целой числовой ячейки
строки (обычно «исходящий/плановый остаток»). Результат обязательно покажи пользователю для проверки.
Личные данные (ФИО, номер счёта) из отчёта не читаются и не сохраняются.
"""
import argparse
import csv
import html
import re
import sys
import zipfile

from _common import funds, portfolio, save_json, load_json, journal, num, path, ticker_by_name, ccy_by_name

ISIN_RE = re.compile(r"\b(IE[0-9A-Z]{9}[0-9])\b")


def rows_from_file(fn):
    low = fn.lower()
    if low.endswith((".ods", ".xlsx")):
        z = zipfile.ZipFile(fn)
        if low.endswith(".ods"):
            x = z.read("content.xml").decode("utf-8")
            for row in re.findall(r"(?s)<table:table-row\b.*?</table:table-row>", x):
                cells = re.findall(r"(?s)<table:table-cell\b[^>]*?(?:/>|>.*?</table:table-cell>)", row)
                yield [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in cells]
        else:
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                ss = z.read("xl/sharedStrings.xml").decode("utf-8")
                shared = [html.unescape(re.sub(r"<[^>]+>", "", si)) for si in re.findall(r"(?s)<si>(.*?)</si>", ss)]
            for name in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet")):
                x = z.read(name).decode("utf-8")
                for row in re.findall(r"(?s)<row\b.*?</row>", x):
                    out = []
                    for attrs, body in re.findall(r"(?s)<c\b([^>]*)>(.*?)</c>", row):
                        v = re.search(r"(?s)<v>(.*?)</v>", body) or re.search(r"(?s)<t[^>]*>(.*?)</t>", body)
                        val = html.unescape(v.group(1)) if v else ""
                        if 't="s"' in attrs and val.isdigit() and int(val) < len(shared):
                            val = shared[int(val)]
                        out.append(val.strip())
                    yield out
    else:
        with open(fn, encoding="utf-8-sig", errors="replace") as f:
            sample = f.read(4096)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t") if sample else csv.excel
            for r in csv.reader(f, dialect):
                yield [c.strip() for c in r]


def parse_report(fn):
    by_isin = {v["isin"]: k for k, v in funds().items() if v.get("isin")}
    found = {}
    for cells in rows_from_file(fn):
        line = " | ".join(cells)
        m = ISIN_RE.search(line)
        if not m:
            continue
        isin = m.group(1)
        after = cells[[i for i, c in enumerate(cells) if isin in c][0] + 1:]
        ints = [num(c) for c in after if re.fullmatch(r"[\d\s ]+([.,]0+)?", c or "")]
        qty = ints[-1] if ints else None
        name = next((c for c in cells if c and "finex" in c.lower()), "")
        t = by_isin.get(isin) or ticker_by_name(name)
        found[isin] = {"isin": isin, "ticker": t, "qty": qty, "name": name.split(",")[0], "ccy": ccy_by_name(name)}
    return list(found.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    sub.add_parser("funds")
    a1 = sub.add_parser("add")
    a1.add_argument("ticker")
    a1.add_argument("qty", type=float)
    a1.add_argument("--note")
    a2 = sub.add_parser("remove")
    a2.add_argument("ticker")
    a3 = sub.add_parser("import")
    a3.add_argument("file")
    a3.add_argument("--dry-run", action="store_true")
    a4 = sub.add_parser("fund")
    a4.add_argument("ticker")
    a4.add_argument("--isin")
    a4.add_argument("--ccy")
    a4.add_argument("--name")
    a4.add_argument("--icav")
    a = ap.parse_args()
    pf = portfolio()
    pos = pf["positions"]
    ref = funds()

    if a.cmd == "add":
        t = a.ticker.upper()
        if t not in ref:
            print(f"! {t} нет в справочнике — уточни ISIN/валюту: portfolio.py fund {t} --isin ... --ccy ...", file=sys.stderr)
        pos[t] = {"qty": a.qty, **({"note": a.note} if a.note else {})}
        save_json("portfolio.json", pf)
        journal(f"Портфель: {t} = {a.qty:g} шт.")
        print(f"{t}: {a.qty:g} шт. -> {path('portfolio.json')}")
    elif a.cmd == "remove":
        pos.pop(a.ticker.upper(), None)
        save_json("portfolio.json", pf)
        print(f"{a.ticker.upper()} удалён из портфеля")
    elif a.cmd == "import":
        items = parse_report(a.file)
        if not items:
            raise SystemExit("В файле не найдено ISIN фондов FinEx (IE...). Проверь формат или добавь позиции вручную.")
        for it in items:
            mark = it["ticker"] or "??? (неизвестный ISIN — portfolio.py fund <ТИКЕР> --isin ...)"
            print(f"  {mark:<8} {it['isin']}  {fmtq(it['qty'])} шт.  {it['name']}")
        if a.dry_run:
            return
        over = load_json("funds.json", {})
        for it in items:
            if it["ticker"] and it["qty"] is not None:
                pos[it["ticker"]] = {"qty": it["qty"], "isin": it["isin"]}
                rec = over.setdefault(it["ticker"], {})
                rec["isin"] = it["isin"]
                if it["ccy"] and not ref.get(it["ticker"], {}).get("ccy"):
                    rec["ccy"] = it["ccy"]
        save_json("portfolio.json", pf)
        save_json("funds.json", over)
        journal(f"Портфель импортирован из отчёта: {len(items)} позиций")
        print(f"Сохранено -> {path('portfolio.json')}. Проверь количества с пользователем!")
    elif a.cmd == "fund":
        t = a.ticker.upper()
        over = load_json("funds.json", {})
        rec = over.setdefault(t, {})
        for k in ("isin", "ccy", "name", "icav"):
            v = getattr(a, k)
            if v:
                rec[k] = v.upper() if k in ("isin", "ccy") else v
        save_json("funds.json", over)
        print(f"{t}: {funds()[t]}")
    elif a.cmd == "funds":
        for t, f in sorted(ref.items()):
            print(f"  {t:<6} {f.get('isin') or '—':<13} {f.get('ccy') or '—':<4} {f.get('name')}")
    else:
        if not pos:
            print("Портфель пуст. portfolio.py add FXUS 100  или  portfolio.py import <отчёт>")
            return
        for t, p in sorted(pos.items()):
            f = ref.get(t, {})
            print(f"  {t:<6} {fmtq(p['qty']):>10} шт.  {f.get('isin') or '—':<13} {f.get('ccy') or '—':<4} {f.get('name', '')}")


def fmtq(q):
    return "—" if q is None else f"{q:,.0f}".replace(",", " ")


if __name__ == "__main__":
    main()
