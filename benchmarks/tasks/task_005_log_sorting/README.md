# Task 010 — Log Sorting

| Свойство | Значение |
|---|---|
| **Тип** | bugfix |
| **Сложность** | medium-hard |
| **Файлы с багом** | `src/time_utils.py` |
| **Связанные файлы** | `src/log_parser.py`, `src/aggregator.py` |
| **Тесты (visible)** | `tests/test_log_sorting.py` |
| **Gold-тесты** | `gold_tests/test_log_sorting.py` |

## Описание

Утилита агрегации логов некорректно сортирует записи из разных таймзон.
`parse_timestamp()` в `time_utils.py` отбрасывает информацию о таймзоне
и возвращает наивный `datetime`, из-за чего сортировка идёт по локальному
времени вместо абсолютного (UTC).

Агент должен: исправить `parse_timestamp()` чтобы он возвращал
timezone-aware `datetime`, используя `datetime.fromisoformat()` или ручной
парсинг offset.

## Запуск тестов

```bash
cd benchmarks/tasks/task_010_log_sorting
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Reasoning через несколько модулей
- Работа с datetime/timezone
- Баг в вспомогательном модуле, влияющий на весь pipeline
