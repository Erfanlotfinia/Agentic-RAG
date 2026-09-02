import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from src.db.interfaces.base import BaseDatabase
from src.schemas.database.config import PostgreSQLSettings

logger = logging.getLogger(__name__)

Base = declarative_base()


class PostgreSQLDatabase(BaseDatabase):
    """PostgreSQL database implementation backed by an Alembic-managed schema."""

    def __init__(self, config: PostgreSQLSettings):
        self.config = config
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None

    def startup(self) -> None:
        """Connect and refuse to serve against an unmigrated/incomplete schema."""
        try:
            logger.info(
                "Attempting to connect to PostgreSQL at: %s",
                self.config.database_url.split("@", 1)[1] if "@" in self.config.database_url else "localhost",
            )
            self.engine = create_engine(
                self.config.database_url,
                echo=self.config.echo_sql,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_pre_ping=True,
            )
            self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            tables = set(inspect(self.engine).get_table_names())
            missing = {"papers", "alembic_version"} - tables
            if missing:
                raise RuntimeError(
                    "Falco database schema is not migrated; missing table(s): "
                    f"{', '.join(sorted(missing))}. Run `alembic upgrade head` before starting services."
                )

            logger.info("PostgreSQL schema ready (database=%s)", self.engine.url.database)
        except Exception:
            logger.exception("Failed to initialize PostgreSQL database")
            if self.engine:
                self.engine.dispose()
            self.engine = None
            self.session_factory = None
            raise

    def teardown(self) -> None:
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL database connections closed")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call startup() first.")
        session = self.session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
