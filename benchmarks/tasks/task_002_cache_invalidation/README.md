# Task 006 — Cache Invalidation

| Свойство | Значение |
|---|---|
| **Тип** | bugfix |
| **Сложность** | medium |
| **Файлы с багом** | `src/cache.py` |
| **Связанные файлы** | `src/storage.py`, `src/service.py` |
| **Тесты (visible)** | `tests/test_cache_invalidation.py` |
| **Gold-тесты** | `gold_tests/test_cache_invalidation.py` |

## Описание

LRU-кэш возвращает устаревшие данные после обновления через `DataService.set()`.
Метод `service.set()` корректно вызывает `cache.invalidate(key)`, но сам
`invalidate()` в `cache.py` содержит баг — он не удаляет значение из
внутреннего словаря (`pass` вместо `del`).

Агент должен проследить цепочку вызовов через три файла:
`service.py` → `cache.py` → найти пустой `invalidate()`.

## Запуск тестов

```bash
cd benchmarks/tasks/task_006_cache_invalidation
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Multi-file reasoning
- Чтение и использование инструментов (grep, reader)
- Bugfix в неочевидном месте
