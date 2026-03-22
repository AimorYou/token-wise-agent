# Task 011 — Async Pipeline

| Свойство | Значение |
|---|---|
| **Тип** | bugfix + concurrency |
| **Сложность** | hard |
| **Файлы с багом** | `src/loader.py` |
| **Связанные файлы** | `src/pipeline.py`, `src/processor.py`, `src/utils.py` |
| **Тесты (visible)** | `tests/test_pipeline_order.py` |
| **Gold-тесты** | `gold_tests/test_pipeline_order.py` |

## Описание

Асинхронный загрузчик файлов использует `results.append()` внутри
конкурентных задач. Порядок append зависит от времени завершения
каждой задачи (симулируется `asyncio.sleep` пропорционально размеру файла),
поэтому итоговый список не совпадает с порядком входных путей.

Downstream-компоненты (`processor.py`, `utils.py`) назначают порядковые
номера по позиции в списке — сломанный порядок каскадно ломает весь pipeline.

**Правильное решение**: использовать `asyncio.gather()` который возвращает
результаты в порядке входных awaitable, а не в порядке завершения. Либо
собирать результаты в индексированную структуру.

## Запуск тестов

```bash
cd benchmarks/tasks/task_011_async_pipeline
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Async/await reasoning
- Понимание `asyncio.gather` vs mutable shared state
- Multi-file tracing (4 файла)
- Сохранение concurrency при исправлении
