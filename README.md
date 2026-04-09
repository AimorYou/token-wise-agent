# token-wise-agent

Кастомный агент для написания кода, построенный на [OpenHands SDK](https://github.com/All-Hands-AI/OpenHands).

Цель дипломной работы — исследовать, как кастомные инструменты сокращают количество
API-вызовов и расход токенов при работе на бенчмарке [SWE-bench](https://www.swebench.com/).

---

## Архитектура

```
run.py                          ← entry point
  └── LocalConversation (OpenHands SDK)
        ├── Agent + system_prompt.j2   ← кастомный системный промпт
        │     └── LLM (litellm → Anthropic / OpenAI / любой провайдер)
        ├── BashSessionTool ← обёртка над TerminalTool (персистентная bash-сессия)
        ├── BashTool        ← кастомный: stateless subprocess
        ├── GlobTool        ← кастомный: поиск файлов по glob-паттерну
        ├── GrepTool        ← кастомный: regex-поиск с контекстом
        ├── SmartReaderTool ← кастомный: чтение файла с диапазоном строк и контекстом
        ├── SmartEditorTool ← кастомный: редактирование файлов (patch/replace/insert/undo)
        └── SubmitTool      ← кастомный: сигнал завершения задачи
```

```
token-wise-agent/
├── agent/
│   ├── config.py                 # Загрузка конфига (.env + YAML + CLI)
│   ├── agent_tracker.py          # Трекинг метрик агента (токены, стоимость, вызовы)
│   ├── prompts/
│   │   └── system_prompt.j2      # Jinja2 системный промпт
│   └── tools/
│       ├── bash.py               # Stateless subprocess bash
│       ├── bash_session.py       # Обёртка над TerminalTool (персистентная сессия)
│       ├── glob.py               # Поиск файлов по glob-паттерну
│       ├── grep.py               # Regex-поиск по файлам с контекстом
│       ├── smart_reader.py       # Чтение файла с диапазоном строк и контекстом
│       ├── smart_editor.py       # Редактирование файлов (patch/replace/insert/undo)
│       └── submit.py             # Сигнал завершения задачи
├── configs/
│   ├── agent_config.yaml         # Конфиг для SWE-bench: промпты, tools, step_limit
│   └── agent_config_user.yaml    # Конфиг для пользовательского режима
├── benchmarks/
│   ├── run_benchmark.py          # SWE-Bench-style раннер
│   └── tasks/                    # 10 задач с багами и тестами
├── tests/
│   └── test_tools.py             # Юнит-тесты инструментов
├── run.py                        # Entry point
├── .env                          # Секреты (не в git)
└── .env.example
```

---

## Установка

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

```bash
# Запустить агента (SWE-bench конфиг по умолчанию)
uv run run.py "Fix the failing tests in tests/"

# Тихий режим
uv run run.py --quiet "задача"

# Другая модель
uv run run.py --model anthropic/claude-opus-4-6 "задача"

# Пользовательский конфиг (с think/finish/bash_session)
uv run run.py --agent-config configs/agent_config_user.yaml "задача"  # с think/bash_session

# Указать рабочую директорию
uv run run.py --working-dir /path/to/project "задача"

# Список инструментов из текущего конфига
uv run run.py --list-tools
```

---

## Конфигурация

Три источника конфигурации с чётким разделением:

### `.env` — секреты и подключение

| Переменная | Описание |
|---|---|
| `AGENT_API_KEY` | API ключ |
| `AGENT_BASE_URL` | Кастомный API endpoint (для OpenAI-совместимых сервисов) |
| `AGENT_MODEL` | litellm model ID (по умолчанию `anthropic/claude-sonnet-4-6`) |

### `configs/agent_config.yaml` — поведение агента

```yaml
agent:
  system_template: "system_prompt.j2"
  instance_template: |
    ...
  llm_params:
    temperature: 0.0
  step_limit: 30
  cost_limit: 0
  timeout: 600
  tools:                    # Whitelist доступных инструментов
    - bash
    - glob
    - grep
    - smart_reader
    - smart_editor
    - submit
```

Два готовых конфига:
- `configs/agent_config.yaml` — SWE-bench режим (без think)
- `configs/agent_config_user.yaml` — пользовательский (с think/bash_session)

### CLI аргументы — рантайм-оверрайды

| Аргумент | Описание |
|---|---|
| `--model` | Переопределить модель из `.env` |
| `--max-steps` | Переопределить `step_limit` из YAML |
| `--working-dir` | Рабочая директория (по умолчанию `.`) |
| `--quiet` | Подавить вывод агента |
| `--agent-config` | Путь к альтернативному YAML конфигу |

---

## Инструменты

| Имя | Источник | Описание |
|-----|----------|----------|
| `bash_session` | Обёртка над TerminalTool | Персистентная bash-сессия (состояние между вызовами) |
| `bash` | Кастомный | Stateless subprocess — каждый вызов независим |
| `glob` | Кастомный | Поиск файлов по glob-паттерну (сортировка по mtime) |
| `grep` | Кастомный | Regex-поиск по файлам с N строками контекста |
| `smart_reader` | Кастомный | Чтение файла: диапазон строк, контекст вокруг строки, авто-truncation |
| `smart_editor` | Кастомный | Редактирование файлов: patch, replace, insert, create, delete, undo |
| `submit` | Кастомный | Сигнал завершения — останавливает агента |
| `think` | SDK built-in | Внутренний "размышление" |

---

## Бенчмарк

10 SWE-Bench-style задач для тестирования агента. Подробности — в [benchmarks/README.md](benchmarks/README.md).

```bash
# Все задачи (логи агента по умолчанию)
uv run python benchmarks/run_benchmark.py

# Одна задача
uv run python benchmarks/run_benchmark.py task_001

# Без логов агента
uv run python benchmarks/run_benchmark.py --quiet task_001

# Сохранить результаты
uv run python benchmarks/run_benchmark.py --save results.json
```

---

## Трекинг метрик

После каждого запуска выводится таблица и создаётся `METRICS.json` в рабочей директории:

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

---

## Добавление нового инструмента

1. Создай файл в `agent/tools/` (шаблон — `smart_reader.py`)
2. Добавь импорт в `agent/tools/__init__.py`
3. Добавь имя тула в `tools:` в `agent_config.yaml`

---

## Тесты

```bash
uv run pytest tests/ -v
```
