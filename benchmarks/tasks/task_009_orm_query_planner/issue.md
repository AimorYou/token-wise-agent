# Неправильные результаты при chained .filter().exclude() с join

## Что происходит

При использовании цепочки `.join(OtherModel).filter(...).exclude(...)`:

1. **exclude() резолвит колонку в неправильную таблицу.** Например, `Order.objects.join(Customer).exclude(age__lt=18)` — exclude должен применяться к `Customer.age`, но из-за отсутствия table prefix в SQL колонка `age` резолвится неправильно или вызывает ошибку.

2. **order_by() после join() падает с `ambiguous column name`.** Например, `Order.objects.join(Customer).order_by("total")` — поскольку `total` не префиксится именем таблицы, SQLite не может определить к какой таблице относится колонка.

3. **В простых случаях без join всё работает нормально.**

## Как воспроизвести

```python
from src.litemap.model import Model
from src.litemap import IntField, StringField, ForeignKey, ConnectionManager

class Customer(Model):
    name = StringField()
    age = IntField()

class Order(Model):
    status = StringField()
    total = IntField()
    customer_id = ForeignKey(to="customer")

# Setup...

# Это ломается:
orders = (
    Order.objects
    .join(Customer)
    .filter(order__status="paid")
    .exclude(customer__age__lt=18)  # exclude резолвит колонку неправильно
    .order_by("total")               # ambiguous column name
    .all()
)
```

## Что ожидается

- `exclude()` после `join()` должен корректно резолвить таблицу для колонки
- `order_by()` после `join()` должен добавлять table prefix к колонкам
- `filter()` с `__` lookup на собственную таблицу после join должен работать корректно

## Затронутые файлы

- `src/litemap/query.py` — `QuerySet._parse_lookup()`, `_build_sql()`, `order_by()`
