# Task 015 — Config Merger

| Свойство | Значение |
|---|---|
| **Тип** | bugfix |
| **Сложность** | hard |
| **Файлы с багом** | `src/confmerge/merge.py`, `src/confmerge/diff.py`, `src/confmerge/patch.py` |
| **Тесты (visible)** | `tests/test_merge.py` |
| **Gold-тесты** | `gold_tests/test_deep_operations.py` |

## Описание

Три взаимосвязанных бага в утилите конфиг-менеджера:
1. deep_merge "merge" стратегия теряет хвост длинного списка
2. compute_diff не рекурсит глубже 2 уровней вложенности
3. apply_patch с некорректным diff затирает неизменённые ключи

## Запуск тестов

```bash
cd benchmarks/tasks/task_015_config_merger
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Рекурсивная обработка вложенных структур
- Понимание diff/patch roundtrip
- Multi-file трассировка (3 файла, баги связаны)
