# Источники и проверка

## Первоисточники (решают)
| Что | Где |
|---|---|
| Уведомления ликвидаторов, приказы суда | https://finexetf.com/library/liquidation-notices/ , https://finexetf.com/library/ (раздел Legal reports, Others). Страница грузит список скриптом — если `docs.py` не видит PDF, открой браузером и сохрани `docs.py --get <URL PDF>` |
| Пример прямых ссылок на PDF | https://cdn.finexetf.com/documents/FinEx_Physically_Backed_Funds_ICAV_-_Notice_of_Termination_-_Shareholders.pdf , https://cdn.finexetf.com/documents/FinEx_Funds_ICAV_-_Update_to_Shareholders__RU_-_October_2026.pdf , https://cdn.finexetf.com/documents/sh_notice_eng_ru.pdf |
| СЧА по фондам | https://finexetf.com/library/fact-sheets/ , https://finexetf.com/library/financial-statements/ |
| Русский сайт | https://finex-etf.ru/ (заглушка, ссылки на finexetf.com) |
| Ликвидатор | Teneo Restructuring (Ireland): Finex.Liquidation@teneo.com; найди страницу дела на teneo.com и добавь `docs.py --add` |
| Регулятор фонда | Центральный банк Ирландии: https://www.centralbank.ie (реестр фондов, пресс-релизы, санкционные разрешения) |
| Реестр компаний Ирландии | CRO: https://core.cro.ie (C55449, C108592 — статус, документы ликвидации) |
| Суд | High Court of Ireland: https://www.courts.ie (списки дел, решения по FinEx / Teneo) |
| Санкции | ЕС Рег. 269/2014; OFAC (home.treasury.gov — лицензии GL); OFSI (gov.uk) |
| Россия | НРД: https://www.nsd.ru/publications/news/ (корпоративные действия по ISIN), Мосбиржа: https://www.moex.com, ЦБ РФ (разъяснения по заблокированным активам) |
| Брокер пользователя | Официальные сообщения брокера (личный кабинет, рассылка) — пользователь пересылает, `intake.py` |

## СМИ (агрегирует `news.py`)
Коммерсантъ, РБК, Интерфакс, Frank Media, pravo.ru, investfunds.ru, Т—Ж, Banki.ru, Рамблер/Финансы; англоязычные — Irish Times, Irish Independent, Bloomberg, Reuters.

## Форумы и каналы (`forums.py`)
- Smart-Lab: https://smart-lab.ru/trading/finex-etf (основная ветка), https://smart-lab.ru/forum/<ТИКЕР>
- Т-Пульс (сообщения инвесторов в Т-Инвестициях) — скриптом не читается (robots), смотри вручную/браузером.
- Telegram: публичные каналы через `https://t.me/s/<канал>` (например, t.me/s/UnblockLegal — юристы по разблокировке).
  Закрытые группы пайщиков пользователь пересылает сам → `intake.py`.
- Брокеры, публиковавшие памятки: КИТ Финанс (brokerkf.ru), БКС, Т-Банк, Финам, Альфа.

## Статусы проверки
- ✅ подтверждено первоисточником (ссылка на документ/страницу)
- ⚠️ частично/косвенно (несколько независимых СМИ или официальный ответ брокера, но не документ ликвидаторов)
- 💬 слух, мнение, не проверено
- ❌ опровергнуто (чем)

## Правила
- Форумное сообщение о «выплатах на следующей неделе» без документа — 💬, сколько бы раз его ни повторили.
- Брокер ≠ ликвидатор: брокер описывает свою процедуру; механизм выплат определяют ликвидаторы и суд.
- Переводы СМИ искажают термины (High Court ≠ Верховный суд, bare trust ≠ доверительное управление) — сверяй с английским текстом.
- Предложения выкупа в чатах: проверяй лицензию ЦБ РФ, юрлицо, способ расчёта; аванс/«комиссия вперёд» — признак мошенничества.
