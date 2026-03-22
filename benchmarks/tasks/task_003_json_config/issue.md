# Feature: Add JSON config support to config loader

## Description

The current configuration loader only supports YAML files. We want to allow
loading configuration from JSON files as well.

## Expected behavior

`load_config(path)` should detect whether the file is YAML or JSON based on
the file extension (`.yaml` / `.yml` → YAML, `.json` → JSON) and parse it
accordingly.

The change should **not** break existing YAML functionality. After loading,
the config should still be validated and merged with defaults by the existing
utility functions.

## Notes

- `config_loader.py` contains the main `load_config()` function.
- `utils.py` provides `merge_defaults()` and `validate_config()`.
- `app.py` uses `load_config` — it should not need changes.

## Tests currently failing in

`tests/test_config_loader.py`
