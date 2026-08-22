from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class JsonStateStore(Protocol):
    def get(self, namespace: str, key: str) -> dict | None: ...

    def put(self, namespace: str, key: str, payload: dict) -> None: ...

    def list(self, namespace: str) -> list[dict]: ...


class InMemoryJsonStateStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict] = {}

    def get(self, namespace: str, key: str) -> dict | None:
        return self._items.get((namespace, key))

    def put(self, namespace: str, key: str, payload: dict) -> None:
        self._items[(namespace, key)] = payload

    def list(self, namespace: str) -> list[dict]:
        return [
            payload
            for (item_namespace, _), payload in self._items.items()
            if item_namespace == namespace
        ]


class SQLAlchemyJsonStateStore:
    """Small SQL store compatible with SQLite for demos and PostgreSQL in production."""

    def __init__(self, database_url: str) -> None:
        from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine

        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.metadata = MetaData()
        self.table = Table(
            "marketcraft_state",
            self.metadata,
            Column("namespace", String(64), primary_key=True),
            Column("item_key", String(128), primary_key=True),
            Column("payload", JSON, nullable=False),
        )
        self.metadata.create_all(self.engine)

    def get(self, namespace: str, key: str) -> dict | None:
        from sqlalchemy import select

        statement = select(self.table.c.payload).where(
            self.table.c.namespace == namespace, self.table.c.item_key == key
        )
        with self.engine.connect() as connection:
            return connection.execute(statement).scalar_one_or_none()

    def put(self, namespace: str, key: str, payload: dict) -> None:
        from sqlalchemy import delete, insert

        condition = (
            (self.table.c.namespace == namespace) & (self.table.c.item_key == key)
        )
        with self.engine.begin() as connection:
            connection.execute(delete(self.table).where(condition))
            connection.execute(
                insert(self.table).values(
                    namespace=namespace, item_key=key, payload=payload
                )
            )

    def list(self, namespace: str) -> list[dict]:
        from sqlalchemy import select

        statement = select(self.table.c.payload).where(
            self.table.c.namespace == namespace
        )
        with self.engine.connect() as connection:
            return list(connection.execute(statement).scalars().all())


@lru_cache
def get_state_store() -> JsonStateStore:
    settings = get_settings()
    if settings.persistence_mode == "database":
        return SQLAlchemyJsonStateStore(settings.database_url)
    return InMemoryJsonStateStore()
