"""Field descriptors for Model."""

from __future__ import annotations


class Field:
    """Base field."""

    sql_type: str = "TEXT"

    def __init__(self, primary_key: bool = False, default=None, null: bool = True):
        self.primary_key = primary_key
        self.default = default
        self.null = null
        self.name: str = ""       # set by ModelMeta
        self.model_name: str = "" # set by ModelMeta


class IntField(Field):
    sql_type = "INTEGER"


class StringField(Field):
    sql_type = "TEXT"


class BoolField(Field):
    sql_type = "INTEGER"  # SQLite stores bools as 0/1


class ForeignKey(Field):
    """Simple FK — stores an integer referencing another Model's id."""

    sql_type = "INTEGER"

    def __init__(self, to: str, **kwargs):
        super().__init__(**kwargs)
        self.to = to  # table name of the referenced model
