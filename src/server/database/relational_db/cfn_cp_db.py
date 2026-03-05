import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

# Defaults reuse the same Postgres server but different database name
CFN_CP_DB_DEFAULT = "cfn_cp"
CFN_CP_USER_DEFAULT = "postgresUser"
CFN_CP_PASSWORD_DEFAULT = "postgresPW"
CFN_CP_HOST_DEFAULT = "localhost"
CFN_CP_PORT_DEFAULT = "5432"


class CfnCpDB:
    """
    Sync Postgres connection manager for the cfn_cp database.
    Implements singleton pattern for application-wide database access.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CfnCpDB, cls).__new__(cls)
            cls._instance._engine = None
            cls._instance._session_factory = None
            cls._instance.logger = logging.getLogger(__name__)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self.logger.debug("Initializing CfnCpDB instance")

    def init(self, db_name: str = None, user: str = None, password: str = None, host: str = None, port: str = None):
        """Initialize the cfn_cp database connection and sessionmaker.

        Args:
            db_name: Database name (default: from CFN_CP_DB or 'cfn_cp')
            user: Database user (default: from POSTGRES_USER or 'postgresUser')
            password: Database password (default: from POSTGRES_PASSWORD or 'postgresPW')
            host: Database host (default: from POSTGRES_HOST or 'localhost')
            port: Database port (default: from POSTGRES_PORT or '5432')

        Raises:
            Exception: If there's an error initializing the database connection
        """
        try:
            if self._engine is None or self._session_factory is None:
                db_name = db_name or os.getenv("CFN_CP_DB", os.getenv("DB_NAME", CFN_CP_DB_DEFAULT))
                user = user or os.getenv("POSTGRES_USER", CFN_CP_USER_DEFAULT)
                password = password or os.getenv("POSTGRES_PASSWORD", CFN_CP_PASSWORD_DEFAULT)
                host = host or os.getenv("POSTGRES_HOST", CFN_CP_HOST_DEFAULT)
                port = port or os.getenv("POSTGRES_PORT", CFN_CP_PORT_DEFAULT)

                url = f"postgresql://{user}:***@{host}:{port}/{db_name}"
                url_with_password = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

                self.logger.debug(f"CfnCpDB connecting to {url}")

                self._engine = create_engine(
                    url_with_password,
                    echo=os.getenv("DB_ECHO", "False").lower() == "true",
                    poolclass=QueuePool,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                )

                self.verify_connectivity()

                self._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
                self.logger.debug("CfnCpDB session factory created successfully")

                self.logger.info(f"Successfully connected to cfn_cp database at {url}")

        except Exception as e:
            self.logger.error(f"Failed to initialize cfn_cp database connection: {str(e)}")
            self._engine = None
            self._session_factory = None
            raise

    def get_session(self) -> Session:
        """Get a database session for cfn_cp.

        Returns:
            Session: A new database session

        Raises:
            RuntimeError: If the database has not been initialized
        """
        if self._session_factory is None:
            self.logger.error("Attempted to get cfn_cp session before database initialization")
            raise RuntimeError(
                "CfnCpDB not initialized. Call init() before getting a session. "
                "This should be done during application startup in main.py"
            )

        session = self._session_factory()
        try:
            return session
        except Exception as e:
            self.logger.error(f"Error creating cfn_cp database session: {str(e)}")
            session.rollback()
            raise
        finally:
            session.close()

    def close(self):
        """Close the database connection."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @property
    def engine(self):
        """Get the engine instance."""
        if self._engine is None:
            raise RuntimeError("CfnCpDB not initialized. Call init() first.")
        return self._engine

    @property
    def session_factory(self):
        """Get the session factory."""
        if self._session_factory is None:
            raise RuntimeError("CfnCpDB not initialized. Call init() first.")
        return self._session_factory

    def verify_connectivity(self) -> None:
        """Verify database connectivity by executing a simple query.

        Raises:
            RuntimeError: If the database connection fails
        """
        if self._engine is None:
            raise RuntimeError("CfnCpDB engine not initialized. Call init() first.")

        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
        except SQLAlchemyError as e:
            raise RuntimeError(f"CfnCpDB connection failed: {str(e)}")
