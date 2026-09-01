import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from src.db.interfaces.base import BaseDatabase
from src.schemas.database.config import PostgreSQLSettings

logger = logging.getLogger(__name__)


Base = declarative_base()


class PostgreSQLDatabase(BaseDatabase):
    """PostgreSQL database implementation."""

    def __init__(self, config: PostgreSQLSettings):
        self.config = config
        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None

    def startup(self) -> None:
        """Initialize the database connection and ensure registered tables exist."""
        try:
            # Import the model package before create_all so every model that uses
            # this Base is registered in Base.metadata on a fresh installation.
            from src import models as _models  # noqa: F401

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

            assert self.engine is not None
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connection test successful")

            existing_tables = inspect(self.engine).get_table_names()

            # This bootstraps missing tables for a fresh installation. Versioned
            # schema upgrades still require a dedicated migration workflow.
            Base.metadata.create_all(bind=self.engine)

            # Use a fresh inspector so table metadata is not served from the
            # pre-create inspector cache.
            updated_tables = inspect(self.engine).get_table_names()
            new_tables = set(updated_tables) - set(existing_tables)

            if new_tables:
                logger.info("Created new tables: %s", ", ".join(sorted(new_tables)))
            else:
                logger.info("All registered tables already exist - no new tables created")

            logger.info("PostgreSQL database initialized successfully")
            logger.info("Database: %s", self.engine.url.database)
            logger.info("Total tables: %s", ", ".join(updated_tables) if updated_tables else "None")
            logger.info("Database connection established")

        except Exception:
            logger.exception("Failed to initialize PostgreSQL database")
            raise

    def teardown(self) -> None:
        """Close the database connection."""
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL database connections closed")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session context manager."""
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
