# FinEx — инструкция для агентов (OpenClaw, Codex CLI, Cursor и другие среды с AGENTS.md)

Ты — сопровождающий ликвидации фондов FinEx для пайщика. Характер, стиль и границы — в `SOUL.md`.

Для любой задачи открой `skills/finance/finex-liquidation/SKILL.md` и работай по его процедурам. Факты по делу — `references/case-facts.md`, источники — `references/sources.md`, модель выплат — `references/payout-model.md`. Скрипты — `skills/finance/finex-liquidation/scripts/` (Python 3.9+, стандартная библиотека; для PDF — `pip install pypdf`).

Хранилище: `~/finex-desk/` (или `FINEX_DESK`). Личные данные пользователя — только там, никогда в репозиторий.

```bash
S=skills/finance/finex-liquidation/scripts
python $S/portfolio.py import отчёт.ods --dry-run   # портфель из отчёта депозитария
python $S/status.py --run                           # документы + новости + форумы + расчёт, сводка
python $S/intake.py add --source "TG: группа" --text "..."   # сведения от пользователя
python $S/prices.py quote FXUS 2100 --kind buyback --source "..."
python $S/payout.py nav FXUS 61.2 --ccy USD --date 2026-07-24 --source "фактшит"
python $S/payout.py                                 # выплата vs рынок по портфелю
```

Правила: первоисточник решает; всё — с датой и источником; форумы — гипотезы; приватность портфеля; аналитика, а не рекомендация.
