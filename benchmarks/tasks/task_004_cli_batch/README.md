# Task 009 — CLI Batch Mode

| Свойство | Значение |
|---|---|
| **Тип** | feature + bugfix |
| **Сложность** | medium |
| **Файлы для изменения** | `src/cli.py`, `src/file_utils.py` |
| **Связанные файлы** | `src/processor.py` |
| **Тесты (visible)** | `tests/test_cli_batch.py` |
| **Gold-тесты** | `gold_tests/test_cli_batch.py` |

## Описание

CLI обрабатывает один файл. Нужно добавить `--batch` флаг для обработки
всех поддерживаемых файлов в директории.

Два бага:
1. `cli.py` — отсутствует `--batch` аргумент и логика batch-обработки
2. `file_utils.py` — `list_supported_files()` не фильтрует по расширению
   (возвращает все файлы вместо `.txt` / `.csv`)

## Запуск тестов

```bash
cd benchmarks/tasks/task_009_cli_batch
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Feature addition (CLI parsing)
- Multi-file bugfix
- Переиспользование существующего кода
