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
        ├── BashTool        ← кастомный: stateless subprocess
        ├── GlobTool        ← кастомный: поиск файлов по glob-паттерну
        ├── GrepTool        ← кастомный: regex-поиск с контекстом
        ├── SmartReaderTool ← кастомный: чтение файла с диапазоном строк и контекстом
        ├── SmartEditorTool ← кастомный: редактирование файлов (patch/replace/insert/undo)
        ├── SubmitTool      ← кастомный: сигнал завершения задачи (SWE-bench режим)
        └── ThinkTool       ← SDK built-in: внутренние размышления
```

```
token-wise-agent/
├── agent/
│   ├── config.py                 # Загрузка конфига (.env + YAML + CLI)
│   ├── agent_tracker.py          # Трекинг метрик агента (токены, стоимость, вызовы)
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
│       └── submit.py
├── configs/
│   ├── agent_config.yaml         # SWE-bench режим: промпты, tools, step_limit
│   ├── agent_config_user.yaml    # Интерактивный режим (по умолчанию без задачи)
│   └── pricing.yaml              # Стоимость токенов по моделям
├── benchmarks/
│   ├── run_benchmark.py          # SWE-Bench-style раннер
│   └── tasks/                    # 10 задач с багами и тестами
├── tests/
│   └── test_tools.py
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

### Интерактивный режим

```bash
# Запустить интерактивный чат (по умолчанию если задача не передана)
uv run run.py

# Явный флаг
uv run run.py -i

# Другая рабочая директория
uv run run.py -i --working-dir /path/to/project
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
# Запустить агента на задаче
uv run run.py "Fix the failing tests in tests/"

# Тихий режим (без вывода агента)
uv run run.py --quiet "задача"

# Другая модель
uv run run.py --model anthropic/claude-opus-4-6 "задача"

# Пользовательский конфиг
uv run run.py --agent-config configs/agent_config_user.yaml "задача"

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

### `configs/agent_config.yaml` / `configs/agent_config_user.yaml` — поведение агента

```yaml
agent:
  system_template: "system_prompt.j2"   # промпт из agent/prompts/
  instance_template: |
    ...
  llm_params:
    temperature: 0.0
  step_limit: 30
  cost_limit: 0
  timeout: 600
  tools:
    - bash
    - glob
    - grep
    - smart_reader
    - smart_editor
    - submit
```

Два готовых конфига:
- `configs/agent_config.yaml` — SWE-bench режим (`step_limit: 30`, `temperature: 0.0`)
- `configs/agent_config_user.yaml` — интерактивный режим (`step_limit: 50`, `temperature: 0.5`, без `submit`)

### `configs/pricing.yaml` — стоимость токенов

```yaml
# Цена за миллион токенов (USD)
claude-sonnet-4-6:
  input: 3.45
  output: 17.25
```

Используется для подсчёта стоимости и передаётся в LiteLLM, чтобы избежать предупреждений о неизвестной модели. Добавьте новую модель сюда — стоимость подхватится автоматически.

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
| `smart_editor` | Кастомный | Редактирование файлов: patch, replace, insert, create, delete, undo |
| `submit` | Кастомный | Сигнал завершения — останавливает агента (SWE-bench режим) |
| `think` | SDK built-in | Внутренние размышления перед действием |

---

## Бенчмарк

10 SWE-Bench-style задач для тестирования агента. Подробности — в [benchmarks/README.md](benchmarks/README.md).

```bash
# Все задачи
uv run python benchmarks/run_benchmark.py

# Одна задача
uv run python benchmarks/run_benchmark.py task_001

# Без логов агента
uv run python benchmarks/run_benchmark.py --quiet task_001

# Сохранить результаты
uv run python benchmarks/run_benchmark.py --save results.json
```

Анализ результатов:

```bash
uv run python scripts/analyze_trajectory.py run_2026-04-11_15-40-56
```

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

В интерактивном режиме стоимость показывается после каждого хода.

---

## Добавление нового инструмента

1. Создай файл в `agent/tools/` (шаблон — `smart_reader.py`)
2. Добавь импорт в `agent/tools/__init__.py`
3. Добавь имя тула в `tools:` в нужном `agent_config.yaml`

---

## Тесты

```bash
uv run pytest tests/ -v
```
