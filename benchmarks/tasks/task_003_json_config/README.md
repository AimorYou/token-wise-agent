# Task 007 — JSON Config

| Свойство | Значение |
|---|---|
| **Тип** | feature |
| **Сложность** | medium |
| **Файлы для изменения** | `src/config_loader.py` |
| **Связанные файлы** | `src/utils.py`, `src/app.py` |
| **Тесты (visible)** | `tests/test_config_loader.py` |
| **Gold-тесты** | `gold_tests/test_config_loader.py` |

## Описание

Загрузчик конфигурации поддерживает только YAML. Нужно добавить поддержку
JSON-файлов. Ветка `.json` в `load_config()` содержит заглушку
`raise ValueError(...)` вместо реального парсинга.

Агент должен: добавить `import json`, заменить `raise` на `json.load()`,
убедиться что `merge_defaults()` и `validate_config()` из `utils.py` по-прежнему
вызываются.

## Запуск тестов

```bash
cd benchmarks/tasks/task_007_json_config
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Feature addition
- Изменение существующего API
- Интеграция с существующими утилитами
