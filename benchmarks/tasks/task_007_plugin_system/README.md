# Task 012 — Plugin System

| Свойство | Значение |
|---|---|
| **Тип** | feature + refactor |
| **Сложность** | hard |
| **Файлы с багами** | `src/plugin_loader.py`, `src/plugin_registry.py` |
| **Связанные файлы** | `src/app.py`, `src/plugins/example_plugin.py`, `src/plugins/math_plugin.py` |
| **Тесты (visible)** | `tests/test_plugin_discovery.py` |
| **Gold-тесты** | `gold_tests/test_plugin_discovery.py` |

## Описание

Система плагинов содержит **три взаимосвязанных бага**:

1. **`plugin_loader.py`** — `discover_plugins()` импортирует только
   `example_plugin` явно; динамический fallback строит путь модуля через
   `os.path.join` (`"src/plugins/math_plugin"`) вместо точечной нотации
   (`"src.plugins.math_plugin"`), что вызывает `ModuleNotFoundError`.

2. **`plugin_loader.py`** — ошибка `ModuleNotFoundError` молча
   подавляется `except ... pass`, поэтому плагин `math` никогда не
   загружается.

3. **`plugin_registry.py`** — `get_plugin(name)` возвращает **класс**
   вместо **экземпляра**, из-за чего `app.run_plugin()` падает с
   `TypeError` при вызове `plugin.execute()`.

## Запуск тестов

```bash
cd benchmarks/tasks/task_012_plugin_system
python -m pytest tests/ -v          # existing (pass on buggy code)
python -m pytest gold_tests/ -v     # gold (fail on buggy code)
```

## Что проверяет

- Динамический импорт (`importlib`)
- Архитектурный refactor
- Reasoning через 5 модулей
- Множественные баги в разных файлах
