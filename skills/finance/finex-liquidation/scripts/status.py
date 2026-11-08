"""Сводка по делу FinEx: что нового и что требует внимания. С --run сначала запускает весь сбор.

  python status.py            # состояние хранилища: непрочитанные документы, ⚑-новости, входящие без проверки
  python status.py --run      # docs.py + news.py + forums.py + payout.py, затем сводка (для расписания)
"""
import argparse
import datetime as dt
import glob
import os
import subprocess
import sys

from _common import read_jsonl, portfolio, path, desk_root

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, *args):
    print(f"\n######## {script} {' '.join(args)}")
    subprocess.run([sys.executable, os.path.join(HERE, script), *args], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    if a.run:
        run("docs.py")
        run("news.py")
        run("forums.py")
        if portfolio()["positions"]:
            run("payout.py")

    since = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    print(f"\n======== Сводка FinEx ({desk_root()}) ========")
    unread = [d for d in read_jsonl("docs/index.jsonl") if d.get("status") == "не прочитан"]
    print(f"Документов в архиве: {len(read_jsonl('docs/index.jsonl'))}, непрочитанных: {len(unread)}")
    for d in unread[-10:]:
        print(f"  ⚑ {d['found']} {d.get('label') or ''} — {d.get('text') or d['file']}")
    news = [n for n in read_jsonl("news.jsonl") if n["first_seen"] >= since]
    imp = [n for n in news if n["important"]]
    print(f"Новостей за {a.days} дн.: {len(news)}, ⚑ {len(imp)}")
    for n in imp[-10:]:
        print(f"  ⚑ {n.get('published')} [{n['source']}] {n['title']}")
    fr = sorted(glob.glob(path("forums", "*.md", mkdir=False)))
    print(f"Форумы: последний сбор {os.path.basename(fr[-1])[:-3] if fr else '—'}")
    inbox = [r for r in read_jsonl("inbox/inbox.jsonl") if r["status"] in ("💬", "⚠️")]
    print(f"Входящие без подтверждения: {len(inbox)}")
    for r in inbox[-10:]:
        print(f"  {r['status']} [{r['id']}] «{r['source']}» {(r['text'] or r.get('file') or '')[:120]}")
    rep = sorted(glob.glob(path("reports", "payout-*.md", mkdir=False)))
    print(f"Последний расчёт выплат: {rep[-1] if rep else '— (payout.py)'}")
    jp = path("journal.md", mkdir=False)
    if os.path.exists(jp):
        with open(jp, encoding="utf-8") as f:
            tail = f.readlines()[-8:]
        print("Хронология (хвост):\n" + "".join("  " + x for x in tail), end="")
    import wiki
    wiki.safe_sync()
    print(f"\nБаза знаний (Obsidian): {path('index.md', mkdir=False)}; проверка — python wiki.py lint")


if __name__ == "__main__":
    main()
