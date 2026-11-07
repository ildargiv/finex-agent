"""Рыночная цена паёв: последняя биржевая цена с MOEX ISS + котировки и предложения выкупа, которые
агент находит сам или приносит пользователь (внебиржевой рынок, брокеры, частные покупатели).

  python prices.py                        # по портфелю: последняя цена MOEX и последние котировки
  python prices.py FXUS FXIT              # выбранные
  python prices.py moex FXUS              # подробно по режимам торгов MOEX (когда и где была последняя сделка)
  python prices.py quote FXUS 2100 --kind buyback --source "БКС: выкуп с дисконтом 30%" [--ccy RUB] [--date 2026-11-06]
  python prices.py quote FXUS 2100 --discount 30 --source "..."   # цена указана как дисконт к СЧА — запомнить и дисконт
  python prices.py history FXUS          # все сохранённые котировки

kind: last (сделка), bid (покупают), offer (продают), buyback (предложение выкупа брокером/покупателем).
Торги на Мосбирже остановлены в 2022, бумаги исключены из списка; цена MOEX — историческая, всегда
показывай её дату. Актуальная «рыночная» цена сейчас — это предложения выкупа (bid/buyback).
"""
import argparse
import datetime as dt

from _common import iss, iss_table, append_jsonl, read_jsonl, journal, tracked, today, fmt, num


def moex_last(t):
    """Последняя сделка по всем режимам: dict(date, close, ccy, board) или None."""
    boards = iss_table(iss(f"/securities/{t}.json", **{"iss.only": "boards"}).get("boards"))
    boards = [b for b in boards if b.get("history_till")]
    if not boards:
        return None, boards
    best = None
    for b in sorted(boards, key=lambda b: b["history_till"], reverse=True)[:4]:
        till = dt.date.fromisoformat(b["history_till"][:10])
        frm = (till - dt.timedelta(days=45)).isoformat()
        rows = iss_table(iss(f"/history/engines/{b['engine']}/markets/{b['market']}/boards/{b['boardid']}/securities/{t}.json",
                             **{"from": frm, "till": till.isoformat(), "iss.only": "history"}).get("history"))
        for r in reversed(rows):
            px = num(r.get("CLOSE")) or num(r.get("LEGALCLOSEPRICE")) or num(r.get("WAPRICE"))
            if px:
                cand = {"date": r["TRADEDATE"], "price": px, "ccy": r.get("CURRENCYID") or b.get("currencyid") or "RUB",
                        "board": b["boardid"], "volume": num(r.get("VOLUME"))}
                if not best or cand["date"] > best["date"] or (cand["date"] == best["date"] and cand["ccy"] in ("SUR", "RUB")):
                    best = cand
                break
    if best and best["ccy"] == "SUR":
        best["ccy"] = "RUB"
    return best, boards


def latest_quote(t):
    q = [r for r in read_jsonl("prices.jsonl") if r["ticker"] == t]
    return sorted(q, key=lambda r: (r.get("date") or "", r.get("added") or ""))[-1] if q else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="*")
    ap.add_argument("--kind", default="bid", choices=["last", "bid", "offer", "buyback"])
    ap.add_argument("--source", default="")
    ap.add_argument("--ccy", default="RUB")
    ap.add_argument("--date")
    ap.add_argument("--discount", type=float, help="дисконт к СЧА в %, если цена объявлена так")
    a = ap.parse_args()
    args = a.args

    if args and args[0] == "quote":
        if len(args) < 3:
            raise SystemExit("prices.py quote TICKER ЦЕНА --source ...")
        t, px = args[1].upper(), num(args[2])
        rec = {"ticker": t, "price": px, "ccy": a.ccy.upper(), "kind": a.kind, "source": a.source,
               "date": a.date or today(), "added": today(), **({"discount_to_nav": a.discount} if a.discount else {})}
        append_jsonl("prices.jsonl", rec)
        journal(f"Котировка {t}: {a.kind} {px} {a.ccy}" + (f" (дисконт {a.discount}%)" if a.discount else ""), a.source)
        print(f"Сохранено: {rec}")
        return
    if args and args[0] == "history":
        for r in read_jsonl("prices.jsonl"):
            if len(args) < 2 or r["ticker"] == args[1].upper():
                print(f"  {r['date']} {r['ticker']:<6} {r['kind']:<8} {fmt(r['price'])} {r['ccy']}  {r.get('source', '')}")
        return
    if args and args[0] == "moex":
        for t in [x.upper() for x in args[1:]] or tracked():
            best, boards = moex_last(t)
            print(f"\n{t}: последняя сделка {best}")
            for b in boards:
                print(f"   {b['boardid']:<6} {b.get('market')} {b.get('currencyid') or ''} история {b.get('history_from')} — {b.get('history_till')} торгуется={b.get('is_traded')}")
        return

    print(f"{'Тикер':<6} {'MOEX посл.':>12} {'дата':<10}   {'котировка':>12} {'вид':<8} {'дата':<10} источник")
    for t in [x.upper() for x in args] or tracked():
        try:
            best, _ = moex_last(t)
        except Exception as e:
            best = None
            print(f"  ! MOEX: {e}")
        q = latest_quote(t)
        mx = f"{fmt(best['price'])} {best['ccy']}" if best else "—"
        md = best["date"] if best else ""
        qq = f"{fmt(q['price'])} {q['ccy']}" if q else "—"
        print(f"{t:<6} {mx:>12} {md:<10}   {qq:>12} {q['kind'] if q else '':<8} {q['date'] if q else '':<10} {q.get('source', '') if q else ''}")


if __name__ == "__main__":
    main()
