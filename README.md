# token-wise-agent

Кастомный агент для написания кода, построенный на [OpenHands SDK](https://github.com/All-Hands-AI/OpenHands).

Цель дипломной работы — исследовать, как кастомные инструменты сокращают количество
API-вызовов и расход токенов при работе на бенчмарке [SWE-bench](https://www.swebench.com/).

[![CI](https://github.com/AimorYou/token-wise-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/AimorYou/token-wise-agent/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/token-wise-agent)](https://pypi.org/project/token-wise-agent/)

---

## Архитектура

```
agent/cli.py                    ← CLI entry point (twa)
  └── LocalConversation (OpenHands SDK)
        ├── Agent + system_prompt.j2   ← кастомный системный промпт
        │     └── LLM (litellm → Anthropic / OpenAI / любой провайдер)
        ├── BashTool        ← кастомный: stateless subprocess
        ├── GlobTool        ← кастомный: поиск файлов по glob-паттерну
        ├── GrepTool        ← кастомный: regex-поиск с контекстом
        ├── SmartReaderTool ← кастомный: чтение файла с диапазоном строк и контекстом
        ├── SmartEditorTool ← кастомный: редактирование файлов (replace/insert/create/delete/undo)
        ├── SubmitTool      ← кастомный: сигнал завершения задачи (SWE-bench режим)
        └── ThinkTool       ← SDK built-in: внутренние размышления
```

```
token-wise-agent/
├── agent/
│   ├── cli.py                    # CLI entry point
│   ├── config.py                 # Загрузка конфига (.env + YAML + CLI)
│   ├── agent_tracker.py          # Трекинг метрик агента (токены, стоимость, вызовы)
│   ├── trajectory.py             # Сохранение траектории в .traj.json
│   ├── configs/
│   │   ├── agent_config.yaml     # SWE-bench режим: промпты, tools, step_limit
│   │   ├── agent_config_user.yaml# Интерактивный режим
│   │   └── pricing.yaml          # Стоимость токенов по моделям
│   ├── prompts/
│   │   ├── system_prompt.j2      # Промпт для SWE-bench режима
│   │   └── system_prompt_user.j2 # Промпт для интерактивного режима
│   └── tools/
│       ├── bash.py
│       ├── bash_session.py
│       ├── glob.py
│       ├── grep.py
│       ├── smart_reader.py
│       ├── smart_editor.py
│       ├── submit.py
│       └── tree.py               # Авто-инъекция структуры репозитория
├── benchmarks/
│   ├── run_benchmark.py          # SWE-Bench-style раннер
│   └── tasks/                    # 10 задач с багами и тестами
├── tests/
│   └── test_tools.py
├── Dockerfile                    # Образ для запуска агента в изоляции
└── .env.example
```

---

## Установка

### Через pip (рекомендуется)

```bash
pip install token-wise-agent
twa edit          # настройка API ключа
twa               # запуск
```

### Для разработки

Требуется [uv](https://github.com/astral-sh/uv).

```bash
git clone <repo-url>
cd token-wise-agent
uv sync
cp .env.example .env
# Вставьте API ключ в .env
```

---

## Использование

### Интерактивный режим

```bash
twa                              # запустить интерактивный чат
twa -i --working-dir /path/to/project  # другая рабочая директория
```

В интерактивном режиме доступны команды:

| Команда | Действие |
|---------|----------|
| `/confirm` | Переключиться в режим подтверждений (агент спрашивает перед каждым tool call) |
| `/auto` | Вернуться в автоматический режим |
| `exit` / Ctrl+C | Выйти |

В режиме подтверждений: **Enter** — одобрить действие, **любой текст** — отклонить и передать агенту как причину.

### Одноразовый режим (SWE-bench)

```bash
twa "Fix the failing tests in tests/"     # запустить агента на задаче
twa --quiet "задача"                      # без вывода агента
twa --model anthropic/claude-opus-4.7 "задача"
twa --working-dir /path/to/project "задача"
twa --list-tools                          # список инструментов из конфига
```

### Редактирование конфигурации

```bash
twa edit           # редактировать .env (API ключ, модель)
twa edit config    # редактировать agent_config_user.yaml
```

---

## Конфигурация

Три источника конфигурации с чётким разделением:

### `~/.config/token-wise-agent/.env` — секреты и подключение

| Переменная | Описание |
|---|---|
| `AGENT_API_KEY` | API ключ |
| `AGENT_BASE_URL` | Кастомный API endpoint (для OpenAI-совместимых сервисов) |
| `AGENT_MODEL` | litellm model ID (например `anthropic/claude-sonnet-4-6`) |

### `~/.config/token-wise-agent/agent_config_user.yaml` — поведение агента

```yaml
agent:
  system_template: "system_prompt_user.j2"
  llm_params:
    temperature: 0.5
  step_limit: 50
  tools:
    - think
    - bash
    - glob
    - grep
    - smart_reader
    - smart_editor
```

Редактируется через `twa edit config`. Два готовых конфига в пакете:
- `agent_config.yaml` — SWE-bench режим (`step_limit: 30`, `temperature: 0.0`, включён `submit`)
- `agent_config_user.yaml` — интерактивный режим (`step_limit: 50`, `temperature: 0.5`)

### `agent/configs/pricing.yaml` — стоимость токенов

```yaml
# Цена за миллион токенов (USD)
anthropic/claude-sonnet-4-6:
  input: 1.90
  output: 9.54

anthropic/claude-opus-4.7:
  input: 6.10
  output: 30.49
```

Используется для подсчёта стоимости и передаётся в LiteLLM. Добавьте новую модель — стоимость подхватится автоматически.

### CLI аргументы

| Аргумент | Описание |
|---|---|
| `-i` / `--interactive` | Запустить интерактивный режим |
| `--model` | Переопределить модель из `.env` |
| `--max-steps` | Переопределить `step_limit` из YAML |
| `--working-dir` | Рабочая директория (по умолчанию `.`) |
| `--quiet` | Подавить вывод агента |
| `--agent-config` | Путь к альтернативному YAML конфигу |

---

## Инструменты

| Имя | Источник | Описание |
|-----|----------|----------|
| `bash` | Кастомный | Stateless subprocess — каждый вызов независим |
| `bash_session` | Обёртка над TerminalTool | Персистентная bash-сессия (состояние между вызовами) |
| `glob` | Кастомный | Поиск файлов по glob-паттерну (сортировка по mtime) |
| `grep` | Кастомный | Regex-поиск по файлам с N строками контекста |
| `smart_reader` | Кастомный | Чтение файла: диапазон строк, контекст вокруг строки, авто-truncation |
| `smart_editor` | Кастомный | Редактирование файлов: replace, insert, create, delete, undo |
| `submit` | Кастомный | Сигнал завершения — останавливает агента (SWE-bench режим) |
| `think` | SDK built-in | Внутренние размышления перед действием |

> **Алиасы инструментов.** Если модель вызывает `read_file`, `read_files`, `view_file` или `view` —
> они прозрачно перенаправляются на `smart_reader` без лишних ошибок и потери шагов.

---

## Бенчмарк

10 SWE-Bench-style задач. Структура каждой задачи:

```
task_XXX/
├── issue.md       — описание бага
├── src/           — код с багом
├── tests/         — тесты (видны агенту)
└── gold_tests/    — золотые тесты (скрыты, запускаются после submit)
```

### Локальный запуск

```bash
uv run python benchmarks/run_benchmark.py              # все задачи
uv run python benchmarks/run_benchmark.py task_001     # одна задача
uv run python benchmarks/run_benchmark.py --quiet task_001
uv run python benchmarks/run_benchmark.py --model anthropic/claude-opus-4.7 task_001
uv run python benchmarks/run_benchmark.py --save results.json
```

### Docker-режим (изолированное окружение)

```bash
uv run python benchmarks/run_benchmark.py --docker --docker-build task_001
uv run python benchmarks/run_benchmark.py --docker task_001 task_003
uv run python benchmarks/run_benchmark.py --docker --docker-image myrepo/agent:v1
```

В Docker-режиме код задачи монтируется в `/testbed`, агентский код живёт в `/app` образа.
API-ключи пробрасываются через `--env-file ~/.config/token-wise-agent/.env`.

---

## Качество кода

Проект использует [ruff](https://github.com/astral-sh/ruff) для линтинга и форматирования.

```bash
uv run ruff check .        # линтинг
uv run ruff format .       # форматирование
uv run pytest tests/ -v    # тесты
```

Pre-commit хуки (опционально):

```bash
uv run pre-commit install
```

CI запускается автоматически на каждый push в `master` и на Pull Request.

---

## Трекинг метрик

После каждого запуска (одноразовый режим) выводится таблица и сохраняется `METRICS.json` в рабочей директории:

```
           Agent Summary
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Metric             ┃       Value ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Model              │ anthropic/… │
│ Latency            │       90.0s │
│ LLM calls          │           7 │
│ Total tool calls   │          14 │
│ Tool errors        │           0 │
│                    │             │
│ Input tokens       │     120,000 │
│ Output tokens      │       3,200 │
│                    │             │
│ Total cost         │     $0.0414 │
└────────────────────┴─────────────┘
```

Полная траектория каждого запуска сохраняется в `~/.config/token-wise-agent/`:

```
~/.config/token-wise-agent/
├── last_twa_run.traj.json          # последний одноразовый запуск
└── run_YYYY-MM-DD_HH-MM-SS/
    ├── task_001.traj.json
    └── task_002.traj.json
```

---

## Добавление нового инструмента

1. Создай файл в `agent/tools/` (шаблон — `smart_reader.py`)
2. Добавь импорт в `agent/tools/__init__.py`
3. Добавь имя тула в `tools:` в нужном `agent_config.yaml`
