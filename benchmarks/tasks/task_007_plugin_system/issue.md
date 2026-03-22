# Feature + Refactor: Plugin system fails to discover dynamically installed plugins

## Description

The application supports a plugin architecture.  Plugins register themselves
via a `@register_plugin` decorator defined in `plugin_registry.py`.

However, plugins that are placed in the `plugins/` package are **not**
automatically discovered.  Currently, `plugin_loader.py` contains a hard-coded
import of only one plugin, so any new plugin added to the directory is silently
ignored.

## Expected behavior

All Python modules inside the `plugins/` directory (excluding `__init__.py`)
should be automatically discovered and imported when
`discover_plugins(plugin_dir)` is called.  Once imported, the `@register_plugin`
decorator will handle registration in the global registry.

### Additional issues

1. The `discover_plugins()` function in `plugin_loader.py` **hard-codes** a
   single import instead of scanning the directory dynamically.
2. The existing dynamic-import stub inside `discover_plugins()` builds the
   **wrong module path** when it tries to use `importlib` — it joins with
   dots incorrectly, producing an `ModuleNotFoundError`.
3. `plugin_registry.py`'s `get_plugin(name)` returns the **class** itself
   instead of an **instance**, which breaks callers that expect to call
   `plugin.execute()` directly.

## Notes

- Keep the `@register_plugin` decorator API unchanged.
- `app.py` calls `discover_plugins()` during initialization and then
  fetches plugins by name — do not change `app.py`.

## Tests currently failing in

`tests/test_plugin_discovery.py`
