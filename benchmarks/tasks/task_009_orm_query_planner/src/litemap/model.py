"""Base Model class with metaclass magic."""

from __future__ import annotations

from typing import Any, Dict, List, Type

from .fields import Field, ForeignKey
from .connection import ConnectionManager
from .query import QuerySet


class ModelMeta(type):
    """Metaclass that collects Field descriptors and sets up table info."""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name == "Model":
            return cls

        fields: Dict[str, Field] = {}
        for attr, value in namespace.items():
            if isinstance(value, Field):
                value.name = attr
                value.model_name = name.lower()
                fields[attr] = value

        cls._fields = fields  # type: ignore[attr-defined]
        cls._table_name = name.lower()  # type: ignore[attr-defined]
        return cls


class Model(metaclass=ModelMeta):
    """Base model — subclasses automatically get a QuerySet manager."""

    _fields: Dict[str, Field] = {}
    _table_name: str = ""

    id = Field(primary_key=True)

    def __init__(self, **kwargs):
        for name, field in self.__class__._fields.items():
            setattr(self, name, kwargs.get(name, field.default))
        self.id = kwargs.get("id")

    # ---------------------------------------------------------------- class API

    @classmethod
    def create_table(cls):
        cols = {"id": "INTEGER PRIMARY KEY AUTOINCREMENT"}
        for name, field in cls._fields.items():
            col_def = field.sql_type
            if not field.null:
                col_def += " NOT NULL"
            if isinstance(field, ForeignKey):
                col_def += f" REFERENCES {field.to}(id)"
            cols[name] = col_def
        ConnectionManager.get().create_table(cls._table_name, cols)

    @classmethod
    def insert(cls, **kwargs) -> "Model":
        field_names = [k for k in kwargs if k in cls._fields]
        placeholders = ", ".join("?" for _ in field_names)
        cols = ", ".join(field_names)
        vals = tuple(kwargs[k] for k in field_names)
        mgr = ConnectionManager.get()
        cur = mgr.execute(
            f"INSERT INTO {cls._table_name} ({cols}) VALUES ({placeholders})",
            vals,
        )
        mgr.commit()
        return cls(id=cur.lastrowid, **kwargs)

    @classmethod
    @property
    def objects(cls) -> QuerySet:
        """Return a fresh QuerySet for this model."""
        return QuerySet(cls)
