"""Ожидаемая выплата на пай против рыночной цены: СЧА (NAV) на пай -> удержания ликвидации -> дисконт за
время -> рубли по курсу ЦБ. Три сценария (пессимистичный / базовый / оптимистичный), итог по портфелю.

  python payout.py                         # расчёт по портфелю, отчёт в reports/payout-<дата>.md
  python payout.py FXUS                    # по одному фонду, с разложением удержаний
  python payout.py nav FXUS 61.25 --ccy USD --date 2026-07-24 --source "фактшит FinEx 24.07.2026, URL"
  python payout.py navs [FXUS]             # история введённых СЧА
  python payout.py params                  # показать допущения
  python payout.py params --set base.reserve=5.5 base.fee=3 pess.years=3 rate=8
  python payout.py params --ticker FXCN --set frozen=12   # доля замороженных/непроданных активов фонда, %

Допущения по умолчанию (меняются через params, источник каждого — в references/payout-model.md):
  reserve — % активов, удержанный на ликвидационном счёте (октябрьское уведомление: ~5,5%; на форумах звучит 8,5%)
  fee     — комиссия за погашение паёв, % (требование FinEx ETF Ltd — 3%, может быть оспорено)
  costs   — прочие расходы ликвидации и TAS, % ; frozen_loss — какая часть «замороженных» активов теряется
  years   — лет до выплаты ; rate — годовая ставка дисконтирования валютных денег, %
Это модель, а не обещание: точной суммы на пай ликвидаторы не публиковали.
"""
import argparse
import json

from _common import (append_jsonl, read_jsonl, load_json, save_json, journal, funds, portfolio, tracked,
                     cbr_rates, path, today, fmt, num)
from prices import latest_quote, moex_last

DEFAULTS = {
    "rate": 7.0,
    "scenarios": {
        "pess": {"reserve": 8.5, "fee": 3.0, "costs": 3.0, "frozen_loss": 100.0, "years": 3.0},
        "base": {"reserve": 5.5, "fee": 3.0, "costs": 1.0, "frozen_loss": 50.0, "years": 1.5},
        "opt": {"reserve": 2.0, "fee": 0.0, "costs": 0.5, "frozen_loss": 0.0, "years": 0.75},
    },
    "tickers": {},  # {"FXCN": {"frozen": 12}}
}
NAMES = {"pess": "пессим.", "base": "базовый", "opt": "оптим."}


def params():
    p = load_json("payout_params.json", {})
    out = json.loads(json.dumps(DEFAULTS))
    out["rate"] = p.get("rate", out["rate"])
    for k, v in p.get("scenarios", {}).items():
        out["scenarios"].setdefault(k, {}).update(v)
    out["tickers"].update(p.get("tickers", {}))
    return out


def latest_nav(t):
    navs = [r for r in read_jsonl("nav.jsonl") if r["ticker"] == t]
    return sorted(navs, key=lambda r: (r["date"], r.get("added", "")))[-1] if navs else None


def calc(t, P, fx):
    nav = latest_nav(t)
    if not nav:
        return None
    frozen = num(P["tickers"].get(t, {}).get("frozen"), 0.0) / 100
    rate = P["rate"] / 100
    rate_rub = fx.get(nav["ccy"])
    out = {"ticker": t, "nav": nav, "fx": rate_rub, "frozen": frozen * 100, "sc": {}}
    for k, s in P["scenarios"].items():
        gross = nav["nav"]
        steps = []
        for label, pct in (("резерв", s["reserve"]), ("комиссия погашения", s["fee"]), ("расходы", s["costs"]),
                           ("замороженные активы", frozen * s["frozen_loss"])):
            cut = gross * pct / 100
            gross -= cut
            steps.append((label, pct, cut))
        pv = gross / (1 + rate) ** s["years"]
        out["sc"][k] = {"gross": gross, "pv": pv, "pv_rub": pv * rate_rub if rate_rub else None, "steps": steps,
                        "years": s["years"]}
    return out


def market(t):
    q = latest_quote(t)
    if q:
        return q
    try:
        m, _ = moex_last(t)
    except Exception:
        m = None
    return {"price": m["price"], "ccy": m["ccy"], "kind": "MOEX последняя сделка", "date": m["date"], "source": "MOEX ISS"} if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="*")
    ap.add_argument("--ccy")
    ap.add_argument("--date")
    ap.add_argument("--source", default="")
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--ticker")
    a = ap.parse_args()
    args = a.args

    if args and args[0] == "nav":
        if len(args) < 3 or not a.date or not a.source:
            raise SystemExit("payout.py nav TICKER СЧА_НА_ПАЙ --ccy USD --date YYYY-MM-DD --source '...' (дата и источник обязательны)")
        t = args[1].upper()
        ccy = (a.ccy or funds().get(t, {}).get("ccy") or "").upper()
        if not ccy:
            raise SystemExit(f"Валюта класса паёв {t} неизвестна — укажи --ccy")
        rec = {"ticker": t, "nav": num(args[2]), "ccy": ccy, "date": a.date, "source": a.source, "added": today()}
        append_jsonl("nav.jsonl", rec)
        journal(f"СЧА {t}: {rec['nav']} {ccy} на {a.date}", a.source)
        print(f"Сохранено: {rec}")
        return
    if args and args[0] == "navs":
        for r in read_jsonl("nav.jsonl"):
            if len(args) < 2 or r["ticker"] == args[1].upper():
                print(f"  {r['date']} {r['ticker']:<6} {r['nav']} {r['ccy']}  {r['source']}")
        return
    if args and args[0] == "params":
        p = load_json("payout_params.json", {})
        for kv in a.set:
            k, v = kv.split("=", 1)
            if a.ticker:
                p.setdefault("tickers", {}).setdefault(a.ticker.upper(), {})[k] = num(v)
            elif k == "rate":
                p["rate"] = num(v)
            else:
                sc, field = k.split(".", 1)
                p.setdefault("scenarios", {}).setdefault(sc, {})[field] = num(v)
        if a.set:
            save_json("payout_params.json", p)
            journal(f"Допущения модели выплат: {' '.join(a.set)}" + (f" ({a.ticker})" if a.ticker else ""))
        print(json.dumps(params(), ensure_ascii=False, indent=1))
        return

    P = params()
    fx = cbr_rates()
    tick = [x.upper() for x in args] or tracked()
    pos = portfolio()["positions"]
    lines = [f"# Выплата vs рынок — {today()}", "",
             f"Курсы ЦБ на {fx.get('_date')}: USD {fmt(fx.get('USD'))}, EUR {fmt(fx.get('EUR'))}. "
             f"Ставка дисконтирования {P['rate']}% год.", "",
             "| Фонд | СЧА/пай (дата) | Выплата/пай ₽: пессим. / базовый / оптим. | Рынок ₽ (вид, дата) | Рынок к базовому | Кол-во | Портфель ₽: рынок / базовый |",
             "|---|---|---|---|---|---|---|"]
    tot_mkt = tot_base = tot_p = tot_o = 0.0
    missing = []
    for t in tick:
        r = calc(t, P, fx)
        m = market(t)
        qty = num(pos.get(t, {}).get("qty"), 0) or 0
        if not r:
            missing.append(t)
            lines.append(f"| {t} | нет СЧА — `payout.py nav {t} ...` | — | {fmt(m['price']) + ' ' + m['ccy'] + ' (' + m['kind'] + ', ' + m['date'] + ')' if m else '—'} | — | {qty:g} | — |")
            continue
        sc = r["sc"]
        px_rub = None
        if m:
            px_rub = m["price"] * (fx.get(m["ccy"]) or 1) if m["ccy"] != "RUB" else m["price"]
        base = sc["base"]["pv_rub"]
        gap = f"{(px_rub / base - 1) * 100:+.1f}%" if px_rub and base else "—"
        mk = f"{fmt(px_rub)} ({m['kind']}, {m['date']})" if px_rub else "—"
        lines.append(f"| {t} | {fmt(r['nav']['nav'], 4)} {r['nav']['ccy']} ({r['nav']['date']}) | "
                     f"{fmt(sc['pess']['pv_rub'])} / {fmt(base)} / {fmt(sc['opt']['pv_rub'])} | {mk} | {gap} | {qty:g} | "
                     f"{fmt(px_rub * qty if px_rub else None, 0)} / {fmt(base * qty if base else None, 0)} |")
        if qty:
            tot_mkt += (px_rub or 0) * qty
            tot_base += (base or 0) * qty
            tot_p += (sc["pess"]["pv_rub"] or 0) * qty
            tot_o += (sc["opt"]["pv_rub"] or 0) * qty
        if len(tick) == 1:
            lines += ["", f"Разложение для {t} (в {r['nav']['ccy']} на пай, до дисконтирования):"]
            for k, s in sc.items():
                st = "; ".join(f"{lab} {pct:.2f}% = −{fmt(cut, 4)}" for lab, pct, cut in s["steps"])
                lines.append(f"- {NAMES.get(k, k)}: {st} → {fmt(s['gross'], 4)}; через {s['years']} г. по {P['rate']}% → {fmt(s['pv'], 4)}")
    if tot_base:
        lines += ["", f"**Портфель:** по рынку {fmt(tot_mkt, 0)} ₽; ожидаемая выплата (тек. стоимость) — "
                      f"пессим. {fmt(tot_p, 0)} / базовый {fmt(tot_base, 0)} / оптим. {fmt(tot_o, 0)} ₽."]
    lines += ["", "Допущения: " + "; ".join(f"{NAMES.get(k, k)}: " + ", ".join(f"{kk}={vv}" for kk, vv in v.items())
                                            for k, v in P["scenarios"].items()),
              "Замороженные активы по фондам: " + (", ".join(f"{k} {v.get('frozen')}%" for k, v in P["tickers"].items()) or "не заданы (0%)"),
              "Модель, а не обещание: ликвидаторы не публиковали сумму на пай; выплаты держателям через НРД — только после санкционных разрешений."]
    if missing:
        lines.append(f"Нет СЧА для: {', '.join(missing)} — найди в фактшитах/отчётности ICAV и внеси `payout.py nav`.")
    text = "\n".join(lines)
    fn = path("reports", f"payout-{today()}.md")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n-> {fn}")


if __name__ == "__main__":
    main()
    import wiki  # база знаний Obsidian: заметки фондов и документов, index (references/wiki.md)
    wiki.safe_sync()
