# SWE-Bench-style Benchmark Tasks

Задачи для тестирования code-агентов. Каждая задача — мини-репозиторий с:
- `issue.md` — описание бага (как GitHub issue)
- `src/` — исходный код с багом
- `tests/` — существующие тесты (видны агенту, проходят на багнутом коде)
- `gold_tests/` — gold-тесты для оценки (скрыты от агента, падают на багнутом коде)

## Задачи

| # | Задача | Тема | Сложность |
|---|--------|------|-----------|
| 1 | `task_001_timeseries` | Timeseries rolling window | Medium |
| 2 | `task_002_cache_invalidation` | LRU cache invalidation | Medium |
| 3 | `task_003_json_config` | Config loader (feature) | Medium |
| 4 | `task_004_cli_batch` | CLI batch mode (feature + bug) | Medium |
| 5 | `task_005_log_sorting` | Log aggregation / timezone | Medium-Hard |
| 6 | `task_006_async_pipeline` | Async pipeline ordering | Hard |
| 7 | `task_007_plugin_system` | Dynamic plugin discovery | Hard |
| 8 | `task_008_eventbus_race` | Thread safety / race condition | Hard |
| 9 | `task_009_orm_query_planner` | ORM query builder / SQL joins | Hard |
| 10 | `task_010_config_merger` | Deep merge / diff / patch | Hard |

## Зависимости

`numpy`, `pandas`, `pyyaml` (в dev-зависимостях проекта).

## Запуск

```bash
# Все задачи (логи агента по умолчанию)
uv run python benchmarks/run_benchmark.py

# Одна задача
uv run python benchmarks/run_benchmark.py task_001

# Без логов
uv run python benchmarks/run_benchmark.py --quiet task_001

# Другая модель
uv run python benchmarks/run_benchmark.py --model anthropic/claude-opus-4-6 task_001

# Другой конфиг
uv run python benchmarks/run_benchmark.py --agent-config configs/agent_config_user.yaml task_001

# Сохранить результаты в JSON
uv run python benchmarks/run_benchmark.py --save results.json
```

## Как это работает

```
run_benchmark.py
  │
  ├── 1. Копирует задачу во /tmp БЕЗ gold_tests/
  │      (агент видит src/ + tests/, но НЕ видит gold_tests/)
  │
  ├── 2. Читает issue.md → передаёт агенту как task
  │      (агент оборачивает через instance_template из configs/agent_config.yaml)
  │
  ├── 3. Запускает агента: run.py --working-dir /tmp/... <issue>
  │      (агент может запускать tests/ для проверки)
  │
  ├── 4. Проверяет SUBMISSION.json (создаёт submit tool)
  │      → агент явно сигнализирует завершение
  │
  ├── 5. Читает METRICS.json (steps, tokens, cost)
  │
  └── 6. Копирует gold_tests/ → pytest gold_tests/
         → PASS/FAIL (оценка по gold-тестам)
```

## Два типа тестов (как в SWE-Bench)

| | `tests/` | `gold_tests/` |
|---|----------|---------------|
| Видимость | Агент видит и может запускать | Скрыты от агента |
| Состояние на багнутом коде | **Проходят** | **Падают** |
| Назначение | Понимание кодовой базы | Оценка правильности фикса |
| Аналог в SWE-Bench | Existing tests | FAIL_TO_PASS tests |

## Метрики для сбора

- Потраченные токены (input/output)
- Количество API-вызовов (steps)
- Время до решения
- Submitted / Not submitted
- Pass / Fail
