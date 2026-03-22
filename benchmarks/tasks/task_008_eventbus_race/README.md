# Task 013 — Eventbus Race Condition

| Свойство | Значение |
|---|---|
| **Тип** | bugfix (concurrency) |
| **Сложность** | hard |
| **Файлы с багом** | `src/eventbus/handlers.py`, `src/eventbus/middleware.py`, `src/eventbus/bus.py` |
| **Тесты (visible)** | `tests/test_bus.py` |
| **Gold-тесты** | `gold_tests/test_concurrency.py` |

## Описание

Race condition в in-process event bus: `HandlerRegistry` и `MiddlewareChain`
не используют блокировки, что приводит к `RuntimeError`, `IndexError` и
пропуску хэндлеров при concurrent `emit()` + `subscribe()`.

## Запуск тестов

```bash
cd benchmarks/tasks/task_013_eventbus_race
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Thread safety, locking primitives
- Понимание iteration-during-mutation
- Multi-file fix (3 файла)
