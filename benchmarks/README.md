# SWE-Bench-style Benchmark Tasks

5 задач для тестирования code-агентов. Каждая задача — мини-репозиторий с:
- `issue.md` — описание бага (как GitHub issue)
- `src/` — исходный код с багом
- `tests/` — тесты, которые падают из-за бага

## Задачи

| # | Задача | Баг | Файл | Сложность |
|---|--------|-----|------|-----------|
| 1 | `task_001_data_merger` | `pd.merge` использует `how="inner"` вместо `how="left"` | `src/merger.py` | Easy |
| 2 | `task_002_array_stats` | `np.std()` без `ddof=1` (population вместо sample std) | `src/stats.py` | Easy |
| 3 | `task_003_timeseries` | Off-by-one в `rolling_mean` — `i - window` вместо `i - window + 1` | `src/timeseries.py` | Medium |
| 4 | `task_004_outlier_detector` | IQR bounds от `mean` вместо `Q1`/`Q3` | `src/detector.py` | Medium |
| 5 | `task_005_data_cleaner` | `median(axis=1)` вместо `median(axis=0)` | `src/cleaner.py` | Easy-Medium |

## Зависимости

Только `numpy` и `pandas` (в dev-зависимостях проекта).

## Запуск

```bash
# Все задачи
uv run python benchmarks/run_benchmark.py

# Конкретная задача
uv run python benchmarks/run_benchmark.py task_001
```

## Использование для тестирования агента

1. Агент получает `issue.md` как описание проблемы
2. Агент анализирует код в `src/`
3. Агент фиксит баг
4. Проверяем: `uv run python -m pytest tests/ -v` из директории задачи

Метрики для сбора:
- Потраченные токены (input/output)
- Количество API-вызовов
- Количество вызовов инструментов
- Время до решения
- Pass/Fail
