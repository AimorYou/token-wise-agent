# SWE-Bench-style Benchmark Tasks

Задачи для тестирования code-агентов. Каждая задача — мини-репозиторий с:
- `issue.md` — описание бага (как GitHub issue)
- `src/` — исходный код с багом
- `tests/` — существующие тесты (видны агенту, проходят на багнутом коде)
- `gold_tests/` — gold-тесты для оценки (скрыты от агента, падают на багнутом коде)

## Задачи

| # | Задача | Баг | Файл(ы) | Сложность |
|---|--------|-----|---------|-----------|
| 1 | `task_001_timeseries` | Off-by-one в `rolling_mean` | `src/timeseries.py` | Medium |
| 2 | `task_002_cache_invalidation` | `invalidate()` не удаляет из кэша | `src/cache.py` | Medium |
| 3 | `task_003_json_config` | Нет поддержки JSON конфигов | `src/config_loader.py` | Medium |
| 4 | `task_004_cli_batch` | Нет `--batch` флага + фильтрация файлов | `src/cli.py`, `src/file_utils.py` | Medium |
| 5 | `task_005_log_sorting` | Timezone-naive парсинг | `src/time_utils.py` | Medium-Hard |
| 6 | `task_006_async_pipeline` | `asyncio.gather` ordering | `src/loader.py` | Hard |
| 7 | `task_007_plugin_system` | Import path + instance bugs | `src/plugin_loader.py`, `src/plugin_registry.py` | Hard |
| 8 | `task_008_eventbus_race` | Race condition: no locks в registry/middleware | `src/eventbus/handlers.py`, `middleware.py`, `bus.py` | Hard |
| 9 | `task_009_orm_query_planner` | Table prefix в exclude/order_by после join | `src/litemap/query.py` | Hard |
| 10 | `task_010_config_merger` | Потеря хвоста списков + shallow diff >2 уровней | `src/confmerge/merge.py`, `diff.py`, `patch.py` | Hard |

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
uv run python benchmarks/run_benchmark.py --agent-config custom.yaml task_001

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
  │      (агент оборачивает через instance_template из agent_config.yaml)
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
| Состояние на багнутом коде | **Проходят** ✅ | **Падают** ❌ |
| Назначение | Понимание кодовой базы | Оценка правильности фикса |
| Аналог в SWE-Bench | Existing tests | FAIL_TO_PASS tests |

## Метрики для сбора

- Потраченные токены (input/output)
- Количество API-вызовов (steps)
- Время до решения
- Submitted / Not submitted
- Pass / Fail
