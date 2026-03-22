"""Lazy QuerySet with chained filters, excludes, joins, and ordering."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from .connection import ConnectionManager
from .exceptions import QueryError

if TYPE_CHECKING:
    from .model import Model


class QuerySet:
    """Lazy SQL builder — builds and executes the query only on iteration."""

    def __init__(self, model: Type["Model"]):
        self._model = model
        self._table = model._table_name
        self._filters: List[Tuple[str, str, Any]] = []   # (col, op, value)
        self._excludes: List[Tuple[str, str, Any]] = []
        self._order_by: List[str] = []
        self._join: Optional[Tuple[str, str, str]] = None  # (other_table, our_fk, other_pk)
        self._join_model: Optional[Type["Model"]] = None

    # ---------------------------------------------------------------- cloning

    def _clone(self) -> "QuerySet":
        qs = QuerySet(self._model)
        qs._filters = list(self._filters)
        qs._excludes = list(self._excludes)
        qs._order_by = list(self._order_by)
        qs._join = self._join
        qs._join_model = self._join_model
        return qs

    # ---------------------------------------------------------------- public API

    def filter(self, **kwargs) -> "QuerySet":
        qs = self._clone()
        for key, value in kwargs.items():
            col, op = self._parse_lookup(key)
            qs._filters.append((col, op, value))
        return qs

    def exclude(self, **kwargs) -> "QuerySet":
        qs = self._clone()
        for key, value in kwargs.items():
            col, op = self._parse_lookup(key)
            qs._excludes.append((col, op, value))
        return qs

    def order_by(self, *fields: str) -> "QuerySet":
        qs = self._clone()
        for f in fields:
            # BUG: does not add table prefix when a join is active,
            # so ambiguous column names cause "ambiguous column name" error.
            if f.startswith("-"):
                qs._order_by.append(f"{f[1:]} DESC")
            else:
                qs._order_by.append(f"{f} ASC")
        return qs

    def join(self, other_model: Type["Model"]) -> "QuerySet":
        """LEFT JOIN *other_model* via the ForeignKey in the current model."""
        from .fields import ForeignKey

        qs = self._clone()
        fk_field = None
        for name, field in self._model._fields.items():
            if isinstance(field, ForeignKey) and field.to == other_model._table_name:
                fk_field = name
                break
        if fk_field is None:
            raise QueryError(
                f"No ForeignKey from {self._model._table_name} to "
                f"{other_model._table_name}"
            )
        qs._join = (other_model._table_name, fk_field, "id")
        qs._join_model = other_model
        return qs

    # ---------------------------------------------------------------- execution

    def all(self) -> List[Dict[str, Any]]:
        sql, params = self._build_sql()
        mgr = ConnectionManager.get()
        rows = mgr.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def count(self) -> int:
        return len(self.all())

    def first(self) -> Optional[Dict[str, Any]]:
        rows = self.all()
        return rows[0] if rows else None

    # ---------------------------------------------------------------- SQL builder

    def _build_sql(self) -> Tuple[str, tuple]:
        parts = [f"SELECT {self._table}.* FROM {self._table}"]
        params: list[Any] = []

        # JOIN
        if self._join:
            other_table, our_fk, other_pk = self._join
            parts.append(
                f"LEFT JOIN {other_table} ON "
                f"{self._table}.{our_fk} = {other_table}.{other_pk}"
            )

        # WHERE (filters)
        where_clauses: list[str] = []
        for col, op, val in self._filters:
            clause, p = self._make_clause(col, op, val)
            where_clauses.append(clause)
            params.append(p)

        # WHERE NOT (excludes)
        # BUG: exclude clauses always use bare column name — they do not
        # resolve the table when a join is active.  This means the column
        # is looked up in the *joined* table, not the primary model table.
        for col, op, val in self._excludes:
            clause, p = self._make_clause(col, op, val)
            where_clauses.append(f"NOT ({clause})")
            params.append(p)

        if where_clauses:
            parts.append("WHERE " + " AND ".join(where_clauses))

        # ORDER BY
        if self._order_by:
            parts.append("ORDER BY " + ", ".join(self._order_by))

        return " ".join(parts), tuple(params)

    # ---------------------------------------------------------------- helpers

    def _parse_lookup(self, key: str) -> Tuple[str, str]:
        """Parse ``field__op`` into ``(column, sql_op)``.

        Supports double-underscore lookups that reference a joined table,
        e.g. ``order__status`` → ``order.status =``.
        """
        ops = {"lt": "<", "gt": ">", "lte": "<=", "gte": ">=", "ne": "!="}

        parts = key.split("__")
        if len(parts) == 3:
            # e.g. order__status__ne → table=order, col=status, op=!=
            table, col, op_name = parts
            return f"{table}.{col}", ops.get(op_name, "=")
        if len(parts) == 2:
            name, maybe_op = parts
            if maybe_op in ops:
                # e.g. age__lt → col=age, op=<
                # BUG: when a join is active, this should prefix with
                # self._table, but it doesn't — so "age__lt" resolves
                # to just "age < ?" which is ambiguous if the joined
                # table also has "age".
                return name, ops[maybe_op]
            # Could be a joined table reference: order__status → order.status =
            if self._join and name == self._join[0]:
                return f"{name}.{maybe_op}", "="
            # Fall back: treat as column with "=" and value
            return f"{name}__{maybe_op}", "="
        return parts[0], "="

    @staticmethod
    def _make_clause(col: str, op: str, val: Any) -> Tuple[str, Any]:
        return f"{col} {op} ?", val
