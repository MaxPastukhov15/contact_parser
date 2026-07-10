# TERRA DOK Lead Generation Pipeline

Инструмент для автоматизированного сбора B2B-лидов компании **«ТЕРРА ДОК»** — производителя премиальных деревянных оконных конструкций (дуб, лиственница, сосна).

## Цель

Сформировать структурированную базу контактов для последующей отправки коммерческих презентаций строительным компаниям, архитектурным бюро, дизайнерским студиям и реставрационным мастерским.

## Архитектура

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────┐
│  Discovery  │───▶│  Enrichment  │───▶│  Filtering  │───▶│  Export   │
│  (API/HTML) │    │  (search)    │    │  (stop/val) │    │  (Polars) │
└─────────────┘    └──────────────┘    └─────────────┘    └───────────┘
       │                   │                   │
       ▼                   ▼                   ▼
    SQLite (state manager / dedup)
```

### Этапы пайплайна

1. **Discovery** — сбор данных через API 2ГИС, Яндекс.Карты, Google Places + HTML-парсинг отраслевых каталогов (archi.ru, moscow-architects.ru, fis.ru, supl.biz).
2. **Гео-экспансия** — старт с МСК + СПб; если <1000 компаний — добор из Краснодара, Новосибирска, Екатеринбурга.
3. **Enrichment** — если у компании нет сайта, выполняется поисковый запрос `[Название] [Город] официальный сайт`.
4. **Фильтрация** — удаление компаний по стоп-словам (ПВХ, алюминий, пластиковые окна и т.д.), валидация телефонов (`7-xxx-xxx-xx-xx`) и email.
5. **Экспорт** — выгрузка в CSV (разделитель `;`) через Polars.

## Установка

```bash
git clone <repo> contact_parser
cd contact_parser

# Виртуальное окружение + зависимости
python -m venv venv
venv\Scripts\activate    # Windows
pip install -e ".[dev]"

# Настройка API-ключей
copy .env.example .env   # Windows
# Отредактируйте .env, вписав ключи:
#   GEO_2GIS_API_KEY
#   YANDEX_MAPS_API_KEY
#   GOOGLE_PLACES_API_KEY
```

## Запуск

```bash
python main.py
# или
run_pipeline.bat
```

## Тестирование

```bash
python -m pytest tests -v
# или
run_tests.bat
```

## Структура проекта

```
contact_parser/
├── main.py                     # Точка входа
├── config/
│   ├── settings.py             # Конфигурация (API-ключи, URLs, лимиты)
│   ├── regions.py              # Регионы сбора (primary + secondary)
│   └── stop_words.py           # Стоп-слова (20+ regex-паттернов)
├── src/
│   ├── models.py               # Dataclass Company
│   ├── discovery/              # Модуль сбора
│   │   ├── base.py             # BaseScraper (backoff, UA-ротация)
│   │   ├── geo_services.py     # 2GIS / Яндекс / Google Places API
│   │   └── catalogs.py         # archi.ru / moscow-architects / fis.ru / supl.biz
│   ├── enrichment/             # Добор URL через поиск
│   ├── filtering/              # Стоп-слова + валидаторы
│   ├── storage/                # SQLite state manager (aiosqlite)
│   ├── export/                 # Polars → CSV
│   └── pipeline/               # Оркестратор
└── tests/
    ├── test_validators.py      # Тесты телефонов и email
    ├── test_stop_words.py      # Тесты фильтрации
    └── test_geo_expansion.py   # Тесты расширения географии
```

## Выходные данные

CSV-файл с колонками:

| Колонка | Описание |
|---|---|
| Название компании | Юридическое или торговое наименование |
| Чем занимается | Краткое описание деятельности |
| Категория | Строительство / Архитектура / Проектирование / Дизайн / Реставрация |
| Рубрика | Исходная рубрика из источника |
| Электронный адрес | Корпоративный email (info@, sales@ — приоритет) |
| Номер телефона | Формат `7-xxx-xxx-xx-xx` |
| Адрес сайта | Главная страница |
| Регион | Город / область |
| Адрес офиса | Фактический адрес |
