# Task 003 — Timeseries

| Свойство | Значение |
|---|---|
| **Тип** | bugfix |
| **Сложность** | easy |
| **Файлы с багом** | `src/timeseries.py` |
| **Тесты (visible)** | `tests/test_timeseries.py` |
| **Gold-тесты** | `gold_tests/test_timeseries.py` |

## Описание

Функция `rolling_mean()` использует окно размером `window + 1` вместо
`window` из-за ошибки в вычислении индексов среза.

## Запуск тестов

```bash
cd benchmarks/tasks/task_003_timeseries
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Off-by-one ошибка
- Однофайловый bugfix
