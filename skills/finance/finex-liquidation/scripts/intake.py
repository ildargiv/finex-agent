"""Приём информации, которую пользователь приносит сам: пересланные сообщения из закрытых Telegram-групп,
письма и ответы брокеров/депозитариев, предложения выкупа, ответы ликвидаторов, скриншоты, файлы.
Всё ложится в <FINEX_DESK>/inbox/ с датой, источником и статусом проверки.

  python intake.py add --source "TG: группа пайщиков FinEx" --text "..." [--tags выкуп,FXUS] [--status 💬]
  python intake.py add --source "БКС, письмо" --file письмо.pdf        # файл копируется в inbox/files/
  echo "длинный текст" | python intake.py add --source "Кит Финанс" --stdin
  python intake.py list [--days 30] [--tag выкуп]
  python intake.py status <id> ✅|❌|⚠️|💬 [--note "чем подтверждено"]

Статусы: ✅ подтверждено первоисточником, ⚠️ частично/косвенно, 💬 слух/не проверено, ❌ опровергнуто.
Если в сообщении есть котировка или предложение выкупа — агент дополнительно записывает его в
prices.py quote (источник = это сообщение), а если цифры СЧА/выплат — в payout.py nav.
"""
import argparse
import datetime as dt
import os
import shutil
import sys

from _common import append_jsonl, read_jsonl, journal, path, now, sha, today

STATUSES = ("✅", "⚠️", "💬", "❌")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    a1 = sub.add_parser("add")
    a1.add_argument("--source", required=True, help="откуда: группа/канал/компания/человек")
    a1.add_argument("--text")
    a1.add_argument("--stdin", action="store_true")
    a1.add_argument("--file")
    a1.add_argument("--date", help="дата исходного сообщения, если известна")
    a1.add_argument("--tags", default="")
    a1.add_argument("--status", default="💬", choices=STATUSES)
    a2 = sub.add_parser("list")
    a2.add_argument("--days", type=int, default=3650)
    a2.add_argument("--tag")
    a3 = sub.add_parser("status")
    a3.add_argument("id")
    a3.add_argument("status", choices=STATUSES)
    a3.add_argument("--note", default="")
    a = ap.parse_args()

    if a.cmd == "add":
        text = a.text or (sys.stdin.read() if a.stdin else "")
        stored = None
        if a.file:
            stored = path("inbox", "files", f"{today()}_{os.path.basename(a.file)}")
            shutil.copy2(a.file, stored)
        if not text and not stored:
            raise SystemExit("Нужен --text, --stdin или --file")
        rec = {"id": sha(now() + a.source + (text or stored))[:8], "added": now(), "date": a.date,
               "source": a.source, "text": text, "file": stored,
               "tags": [t.strip() for t in a.tags.split(",") if t.strip()], "status": a.status, "notes": []}
        append_jsonl("inbox/inbox.jsonl", rec)
        with open(path("inbox", f"{today()}.md"), "a", encoding="utf-8") as f:
            f.write(f"\n### [{rec['id']}] {a.status} {a.source} — {a.date or rec['added']}\n"
                    f"{text}\n" + (f"Файл: {stored}\n" if stored else "") +
                    (f"Теги: {', '.join(rec['tags'])}\n" if rec['tags'] else ""))
        journal(f"Входящее [{rec['id']}] от «{a.source}» {a.status}", "inbox")
        print(f"Сохранено [{rec['id']}] -> {path('inbox', 'inbox.jsonl')}")
    elif a.cmd == "status":
        recs = read_jsonl("inbox/inbox.jsonl")
        hit = False
        for r in recs:
            if r["id"] == a.id:
                r["status"] = a.status
                r.setdefault("notes", []).append(f"{now()} {a.status} {a.note}".strip())
                hit = True
        if not hit:
            raise SystemExit(f"Нет записи {a.id}")
        p = path("inbox", "inbox.jsonl")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            import json
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(p + ".tmp", p)
        journal(f"Входящее [{a.id}] -> {a.status} {a.note}")
        print(f"[{a.id}] -> {a.status}")
    else:
        since = (dt.datetime.now() - dt.timedelta(days=getattr(a, "days", 3650))).strftime("%Y-%m-%d")
        tag = getattr(a, "tag", None)
        for r in read_jsonl("inbox/inbox.jsonl"):
            if r["added"][:10] < since or (tag and tag not in r["tags"]):
                continue
            print(f"  [{r['id']}] {r['status']} {r['added']} «{r['source']}» {', '.join(r['tags'])}\n"
                  f"      {(r['text'] or '')[:300]}" + (f"\n      файл: {r['file']}" if r.get('file') else ""))


if __name__ == "__main__":
    main()
