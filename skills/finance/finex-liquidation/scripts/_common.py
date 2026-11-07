"""Общие помощники агента FinEx: хранилище, HTTP, MOEX ISS, курсы ЦБ, справочник фондов. Только stdlib."""
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (finex-liquidation-agent)"}
ISS = "https://iss.moex.com/iss"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------- Справочник фондов ----------
# Публичные данные: тикер Мосбиржи, ISIN, зонтичный ICAV (оба — Ирландия), валюта класса паёв.
# ISIN не зашиты: они попадают в funds.json хранилища при импорте отчёта (сопоставление по названию фонда)
# или вручную `portfolio.py fund TICKER --isin ... --ccy ...`. ccy = None — валюта класса не сверена.
FUNDS_ICAV = "FinEx Funds ICAV (in liquidation), C55449"
PB_ICAV = "FinEx Physically Backed Funds ICAV (in liquidation), C108592"
FUNDS = {
    "FXGD": {"name": "FinEx Gold ETF", "isin": None, "ccy": "USD", "icav": PB_ICAV},
    "FXKZ": {"name": "FinEx FFIN Kazakhstan Equity ETF", "isin": None, "ccy": None, "icav": PB_ICAV},
    "FXUS": {"name": "FinEx USA UCITS ETF", "isin": None, "ccy": "USD", "icav": FUNDS_ICAV},
    "FXIT": {"name": "FinEx USA Information Technology UCITS ETF", "isin": None, "ccy": "USD", "icav": FUNDS_ICAV},
    "FXCN": {"name": "FinEx China UCITS ETF", "isin": None, "ccy": "USD", "icav": FUNDS_ICAV},
    "FXDE": {"name": "FinEx Germany UCITS ETF", "isin": None, "ccy": "EUR", "icav": FUNDS_ICAV},
    "FXMM": {"name": "FinEx Cash Equivalents UCITS ETF (RUB Hedged)", "isin": None, "ccy": "RUB", "icav": FUNDS_ICAV},
    "FXRE": {"name": "FinEx US REIT UCITS ETF", "isin": None, "ccy": "USD", "icav": FUNDS_ICAV},
    # Ниже — названия и валюты не сверены (уточнить по списку суб-фондов в уведомлениях ликвидаторов)
    "FXTB": {"name": "FinEx Cash Equivalents UCITS ETF (USD)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXRL": {"name": "FinEx Russian RTS Equity UCITS ETF", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXWO": {"name": "FinEx Global Equity UCITS ETF", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXRW": {"name": "FinEx Global Equity UCITS ETF (RUB Hedged)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXRB": {"name": "FinEx Russian Rouble Bonds (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXRU": {"name": "FinEx Russian Eurobonds (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXTP": {"name": "FinEx US TIPS UCITS ETF (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXIP": {"name": "FinEx US TIPS UCITS ETF RUB Hedged (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXEM": {"name": "FinEx Emerging Markets (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXDM": {"name": "FinEx Developed Markets (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXES": {"name": "FinEx (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
    "FXRD": {"name": "FinEx (уточнить)", "isin": None, "ccy": None, "icav": FUNDS_ICAV},
}


# Сопоставление названия фонда из отчёта брокера/депозитария с тикером (порядок важен: частное раньше общего)
NAME_RULES = [
    (r"gold", "FXGD"), (r"kazakhstan", "FXKZ"), (r"germany", "FXDE"), (r"information technology", "FXIT"),
    (r"reit", "FXRE"), (r"china", "FXCN"), (r"cash equivalents.*rub", "FXMM"), (r"cash equivalents", "FXTB"),
    (r"rts", "FXRL"), (r"global equity.*rub", "FXRW"), (r"global equity", "FXWO"), (r"\busa ucits", "FXUS"),
]


def ticker_by_name(name):
    low = (name or "").lower()
    for pat, t in NAME_RULES:
        if re.search(pat, low):
            return t
    return None


def ccy_by_name(name):
    m = re.search(r"\b(USD|EUR|RUB|KZT)\b", name or "", re.I)
    return m.group(1).upper() if m else None


# ---------- Хранилище ----------
def desk_root():
    """Корень хранилища: ~/finex-desk или переменная FINEX_DESK. Личные данные живут только здесь."""
    root = os.environ.get("FINEX_DESK") or os.path.join(os.path.expanduser("~"), "finex-desk")
    os.makedirs(root, exist_ok=True)
    return root


def path(*parts, mkdir=True):
    p = os.path.join(desk_root(), *parts)
    if mkdir:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def load_json(name, default):
    p = path(name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(name, data):
    p = path(name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def append_jsonl(name, rec):
    with open(path(name), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(name):
    p = path(name)
    out = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def journal(text, source=""):
    """Общая хронология событий (только добавление)."""
    with open(path("journal.md"), "a", encoding="utf-8") as f:
        f.write(f"- {now()} — {text}" + (f" ({source})" if source else "") + "\n")


def funds():
    """Справочник + поправки пользователя из funds.json."""
    out = {k: dict(v) for k, v in FUNDS.items()}
    for k, v in load_json("funds.json", {}).items():
        out.setdefault(k, {}).update({kk: vv for kk, vv in v.items() if vv is not None})
    return out


def portfolio():
    return load_json("portfolio.json", {"positions": {}})


def tracked(tickers=None):
    """Тикеры из аргумента, иначе из портфеля."""
    if tickers:
        return [t.upper() for t in tickers]
    pos = portfolio()["positions"]
    if not pos:
        raise SystemExit("Портфель пуст. Добавьте: python portfolio.py add FXUS 100  или  portfolio.py import <отчёт брокера>")
    return sorted(pos)


# ---------- Время, числа ----------
def today():
    return _dt.date.today().isoformat()


def now():
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def num(x, default=None):
    try:
        return float(str(x).replace(",", ".").replace(" ", "").replace(" ", ""))
    except (TypeError, ValueError):
        return default


def sha(text):
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:16]


def fmt(x, d=2):
    if x is None:
        return "—"
    return f"{x:,.{d}f}".replace(",", " ")


# ---------- HTTP ----------
def fetch(url, timeout=40, binary=False):
    req = urllib.request.Request(url, headers=UA)
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if binary:
                    return raw
                cs = r.headers.get_content_charset() or "utf-8"
                return raw.decode(cs, "replace")
        except Exception as e:  # сеть нестабильна — повторяем
            last = e
    raise RuntimeError(f"{url}: {last}")


def html_text(html):
    """Грубое извлечение текста из HTML: без скриптов/стилей, по абзацам."""
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr|article|section|blockquote)>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    import html as _h
    text = _h.unescape(text)
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def links(html, base):
    out = []
    for href, label in re.findall(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html):
        url = urllib.parse.urljoin(base, href.strip())
        out.append((url, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", label)).strip()))
    # ссылки на PDF вне <a> (JSON в странице)
    for m in re.findall(r'https?://[^\s"\'<>]+?\.pdf', html, re.I):
        out.append((m, ""))
    return out


# ---------- MOEX ISS ----------
def iss(path_, **params):
    params.setdefault("iss.meta", "off")
    url = f"{ISS}{path_}?{urllib.parse.urlencode(params)}"
    return json.loads(fetch(url))


def iss_table(block):
    if not block:
        return []
    return [dict(zip(block["columns"], row)) for row in block["data"]]


# ---------- Курсы ЦБ РФ ----------
def cbr_rates(date=None):
    """{'USD': руб, 'EUR': руб, ...} на дату (официальный курс ЦБ). date — YYYY-MM-DD."""
    q = ""
    if date:
        d = _dt.date.fromisoformat(date)
        q = "?date_req=" + d.strftime("%d/%m/%Y")
    raw = fetch("https://www.cbr.ru/scripts/XML_daily.asp" + q, binary=True)
    root = ET.fromstring(raw)
    out = {"RUB": 1.0, "_date": root.get("Date")}
    for v in root.iter("Valute"):
        code = v.findtext("CharCode")
        val = num(v.findtext("Value"))
        nom = num(v.findtext("Nominal"), 1)
        if code and val:
            out[code] = val / nom
    return out
