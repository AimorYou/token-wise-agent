# Task 014 — ORM Query Planner

| Свойство | Значение |
|---|---|
| **Тип** | bugfix |
| **Сложность** | hard |
| **Файлы с багом** | `src/litemap/query.py` |
| **Тесты (visible)** | `tests/test_query.py` |
| **Gold-тесты** | `gold_tests/test_join_queries.py` |

## Описание

Query planner в мини-ORM неправильно резолвит таблицы при комбинации
`join() + filter() + exclude() + order_by()`. Exclude применяется к колонке
не той таблицы, order_by не добавляет table prefix.

## Запуск тестов

```bash
cd benchmarks/tasks/task_014_orm_query_planner
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Понимание SQL query building
- Table aliasing / column resolution
- Chained lazy query API
