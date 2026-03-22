# Race condition при concurrent emit + subscribe

## Что происходит

При одновременном вызове `bus.emit()` и `bus.subscribe()` из разных тредов:

1. Иногда хэндлер **не вызывается**, хотя подписка прошла до `emit()` (по wall clock).
2. Иногда — `RuntimeError: dictionary changed size during iteration` в `HandlerRegistry.get_handlers()`.
3. Middleware chain тоже не потокобезопасна — при добавлении middleware во время обработки события падает с `IndexError`.

## Как воспроизвести

```python
import threading
from src.eventbus import EventBus, Event

bus = EventBus()
results = []
bus.subscribe("test", lambda e: results.append(1))

# 100 тредов одновременно subscribe + emit
barrier = threading.Barrier(200)

def subscribe_thread():
    barrier.wait()
    bus.subscribe("test", lambda e: None)

def emit_thread():
    barrier.wait()
    bus.emit(Event(name="test"))

threads = [threading.Thread(target=subscribe_thread) for _ in range(100)]
threads += [threading.Thread(target=emit_thread) for _ in range(100)]
for t in threads: t.start()
for t in threads: t.join()

# Ожидаем len(results) == 100, но часто меньше или RuntimeError
```

## Что ожидается

- `subscribe()`, `emit()`, и `bus.use()` должны быть потокобезопасны.
- Хэндлеры, подписанные до emit, всегда вызываются.
- Добавление middleware во время обработки событий не должно вызывать crash.

## Затронутые файлы

- `src/eventbus/handlers.py` — `HandlerRegistry` не защищён блокировками
- `src/eventbus/middleware.py` — `MiddlewareChain.execute()` итерирует `_middlewares` без снэпшота
- `src/eventbus/bus.py` — `EventBus.emit()` и `EventBus.subscribe()` вызывают незащищённые методы
