"""Gold tests — join + filter + exclude + order_by combinations.

These tests FAIL on the buggy code because:
1. exclude() after join() resolves columns against the wrong table
2. order_by() after join() does not add table prefix → ambiguous column
3. filter with __ lookup on own table after join doesn't prefix table
"""
import pytest

from src.litemap import ConnectionManager, IntField, StringField, BoolField, ForeignKey
from src.litemap.model import Model


# ------------------------------------------------------------------ models

class Customer(Model):
    name = StringField()
    age = IntField()
    active = BoolField(default=True)


class Purchase(Model):
    name = StringField()   # item name — also exists in Customer → ambiguous!
    status = StringField()
    total = IntField()
    customer_id = ForeignKey(to="customer")


# ------------------------------------------------------------------ fixtures

@pytest.fixture(autouse=True)
def _setup_db():
    ConnectionManager.reset()
    ConnectionManager.get(":memory:")
    Customer.create_table()
    Purchase.create_table()
    yield
    ConnectionManager.reset()


@pytest.fixture
def data():
    alice = Customer.insert(name="Alice", age=30, active=True)
    bob = Customer.insert(name="Bob", age=17, active=True)
    carol = Customer.insert(name="Carol", age=25, active=False)

    Purchase.insert(name="Widget", status="paid", total=100, customer_id=alice.id)
    Purchase.insert(name="Gadget", status="pending", total=50, customer_id=alice.id)
    Purchase.insert(name="Widget", status="paid", total=200, customer_id=bob.id)
    Purchase.insert(name="Doohickey", status="cancelled", total=10, customer_id=carol.id)

    return {"alice": alice, "bob": bob, "carol": carol}


# ------------------------------------------------------------------ tests

class TestJoinFilterExclude:
    def test_join_filter_by_joined_table(self, data):
        """Filter purchases by status via join — basic sanity."""
        rows = Purchase.objects.join(Customer).filter(purchase__status="paid").all()
        assert len(rows) == 2

    def test_exclude_applies_to_primary_table_after_join(self, data):
        """exclude(total__lt=100) must exclude based on Purchase.total,
        not Customer columns.

        BUG: Without table prefix, 'total' is ambiguous or resolves
        to the wrong table.
        """
        rows = (
            Purchase.objects
            .join(Customer)
            .filter(purchase__status="paid")
            .exclude(total__lt=100)
            .all()
        )
        # Exclude total < 100 → keep total >= 100
        totals = {r["total"] for r in rows}
        assert totals == {100, 200}

    def test_exclude_with_ambiguous_name_after_join(self, data):
        """After join(Customer), exclude(name='Widget') must target Purchase.name.

        Both Purchase and Customer have a 'name' column.
        BUG: Without table prefix, 'name' is ambiguous.
        """
        rows = (
            Purchase.objects
            .join(Customer)
            .exclude(name="Widget")
            .all()
        )
        # Exclude purchases named "Widget" → Gadget($50) + Doohickey($10)
        names = {r["name"] for r in rows}
        assert "Widget" not in names
        assert len(rows) == 2

    def test_filter_and_exclude_combined_with_join(self, data):
        """Paid purchases from customers aged >= 18."""
        rows = (
            Purchase.objects
            .join(Customer)
            .filter(purchase__status="paid")
            .exclude(customer__age__lt=18)
            .all()
        )
        # paid: Alice(100), Bob(200)
        # exclude age<18: Bob out → only Alice's paid purchase ($100)
        assert len(rows) == 1
        assert rows[0]["total"] == 100


class TestJoinOrderBy:
    def test_order_by_uses_primary_table_prefix(self, data):
        """order_by('name') after join must sort by Purchase.name, not Customer.name.

        BUG: order_by does not prefix column with table name when join
        is active. The generated SQL must contain 'purchase.name' in
        ORDER BY, not bare 'name'.
        """
        qs = Purchase.objects.join(Customer).order_by("name")
        sql, _ = qs._build_sql()
        # After fix, ORDER BY should reference purchase.name explicitly
        assert "purchase.name" in sql.lower(), (
            f"ORDER BY must use table-qualified column name. Got SQL: {sql}"
        )

    def test_order_by_desc_uses_primary_table_prefix(self, data):
        qs = Purchase.objects.join(Customer).order_by("-name")
        sql, _ = qs._build_sql()
        assert "purchase.name" in sql.lower(), (
            f"ORDER BY must use table-qualified column name. Got SQL: {sql}"
        )

    def test_filter_exclude_order_by_all_together(self, data):
        """Full chain: join + filter + exclude + order_by."""
        rows = (
            Purchase.objects
            .join(Customer)
            .filter(purchase__status="paid")
            .exclude(customer__age__lt=18)
            .order_by("-name")
            .all()
        )
        assert len(rows) == 1
        assert rows[0]["total"] == 100
