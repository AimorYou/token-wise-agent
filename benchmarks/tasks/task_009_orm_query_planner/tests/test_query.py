"""Existing tests for litemap QuerySet — simple cases without join.

All these tests pass on the current (buggy) code because
the bugs only manifest when join() is combined with filter/exclude/order_by.
"""
import pytest

from src.litemap import ConnectionManager, IntField, StringField, BoolField, ForeignKey
from src.litemap.model import Model


# ------------------------------------------------------------------ models

class Department(Model):
    name = StringField()


class Employee(Model):
    name = StringField()
    age = IntField()
    active = BoolField(default=True)
    department_id = ForeignKey(to="department")


# ------------------------------------------------------------------ fixtures

@pytest.fixture(autouse=True)
def _setup_db():
    """Fresh in-memory database for each test."""
    ConnectionManager.reset()
    ConnectionManager.get(":memory:")
    Department.create_table()
    Employee.create_table()
    yield
    ConnectionManager.reset()


@pytest.fixture
def sample_data():
    eng = Department.insert(name="Engineering")
    hr = Department.insert(name="HR")
    Employee.insert(name="Alice", age=30, active=True, department_id=eng.id)
    Employee.insert(name="Bob", age=17, active=True, department_id=eng.id)
    Employee.insert(name="Carol", age=25, active=False, department_id=hr.id)
    return {"eng": eng, "hr": hr}


# ------------------------------------------------------------------ tests

class TestBasicFilter:
    def test_filter_eq(self, sample_data):
        rows = Employee.objects.filter(name="Alice").all()
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_filter_gt(self, sample_data):
        rows = Employee.objects.filter(age__gt=20).all()
        names = {r["name"] for r in rows}
        assert names == {"Alice", "Carol"}

    def test_filter_lt(self, sample_data):
        rows = Employee.objects.filter(age__lt=18).all()
        assert len(rows) == 1
        assert rows[0]["name"] == "Bob"

    def test_chained_filters(self, sample_data):
        rows = Employee.objects.filter(age__gt=20).filter(active=True).all()
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"


class TestExclude:
    def test_exclude_eq(self, sample_data):
        rows = Employee.objects.exclude(name="Alice").all()
        names = {r["name"] for r in rows}
        assert "Alice" not in names
        assert len(rows) == 2

    def test_exclude_lt(self, sample_data):
        rows = Employee.objects.exclude(age__lt=18).all()
        names = {r["name"] for r in rows}
        assert "Bob" not in names


class TestOrderBy:
    def test_order_by_asc(self, sample_data):
        rows = Employee.objects.order_by("age").all()
        ages = [r["age"] for r in rows]
        assert ages == sorted(ages)

    def test_order_by_desc(self, sample_data):
        rows = Employee.objects.order_by("-age").all()
        ages = [r["age"] for r in rows]
        assert ages == sorted(ages, reverse=True)


class TestCount:
    def test_count_all(self, sample_data):
        assert Employee.objects.count() == 3

    def test_count_filtered(self, sample_data):
        assert Employee.objects.filter(active=True).count() == 2


class TestFirst:
    def test_first_exists(self, sample_data):
        row = Employee.objects.filter(name="Bob").first()
        assert row is not None
        assert row["name"] == "Bob"

    def test_first_empty(self, sample_data):
        row = Employee.objects.filter(name="Nobody").first()
        assert row is None
