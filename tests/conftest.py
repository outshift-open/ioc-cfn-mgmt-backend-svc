"""Pytest fixtures and minimal test DB bootstrap."""
import contextlib
import hashlib
import os
import time

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models import Base
from server.database.relational_db.models.api_key import ApiKey
from server.database.relational_db.models.cognitive_fabric_node import CognitiveFabricNode
from server.database.relational_db.models.multi_agentic_system import MultiAgenticSystem
from server.database.relational_db.models.user import User
from server.database.relational_db.models.workspace import Workspace
from server.database.relational_db.models.workspace_invitation import (
    WorkspaceInvitation,
)
from server.database.relational_db.models.workspace_member import WorkspaceMember
from server.main import app
from server.schemas.api_key import ApiKeyCreate
from server.services.api_key import api_key_service

os.environ.setdefault("POSTGRES_DB", "ioc_test")
os.environ.setdefault("POSTGRES_USER", "postgresUser")
os.environ.setdefault("POSTGRES_PASSWORD", "postgresPW")
os.environ.setdefault("POSTGRES_HOST", "localhost")


def _ensure_test_database_exists(max_wait_seconds: int = 20) -> None:
    """Ensure the test database exists on the configured host.

    - Respects POSTGRES_HOST (e.g., 'tkf-relational-db' in CI)
    - Tries candidate ports: POSTGRES_PORT, 5432, 5455
    - Tries bootstrap DBs: 'postgres', 'tkf', 'template1'
    - Retries until max_wait_seconds for containers to become ready
    """
    db_name = os.environ.get("POSTGRES_DB", "tkf_test")
    user = os.environ.get("POSTGRES_USER", "postgresUser")
    password = os.environ.get("POSTGRES_PASSWORD", "postgresPW")
    host = os.environ.get("POSTGRES_HOST", "localhost")

    candidate_ports = []
    if os.environ.get("POSTGRES_PORT"):
        candidate_ports.append(str(os.environ["POSTGRES_PORT"]))
    for p in ("5432", "5455"):
        if p not in candidate_ports:
            candidate_ports.append(p)

    bootstrap_dbs = ("postgres", "tkf", "template1")

    deadline = time.time() + max_wait_seconds
    last_error = None

    while time.time() < deadline:
        for port in candidate_ports:
            for bootstrap_db in bootstrap_dbs:
                try:
                    conn = psycopg2.connect(
                        dbname=bootstrap_db,
                        user=user,
                        password=password,
                        host=host,
                        port=int(port),
                    )
                except Exception as e:
                    last_error = e
                    continue

                try:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                        exists = cur.fetchone() is not None
                        if not exists:
                            cur.execute(f'CREATE DATABASE "{db_name}"')
                    os.environ["POSTGRES_PORT"] = str(port)
                    return
                except Exception as e:
                    last_error = e
                finally:
                    with contextlib.suppress(Exception):
                        conn.close()
        time.sleep(1)

    if last_error:
        print(
            f"Test DB bootstrap warning: could not ensure '{db_name}' exists on "
            f"{host}:{candidate_ports}. Last error: {last_error}"
        )
    else:
        print(
            f"Test DB bootstrap warning: could not ensure '{db_name}' exists on "
            f"{host}:{candidate_ports} (no connection attempts succeeded)"
        )


@pytest.fixture
def dev_api_key(setup_test_environment):
    """Get the API key created for dev-user during setup."""
    # The API key is created in setup_test_environment
    # We need to get it from the database
    db = RelationalDB()
    session = db.session_factory()
    try:
        api_key = session.query(ApiKey).filter(ApiKey.user_id == "dev-user", ApiKey.deleted_at.is_(None)).first()
        if api_key:
            # We need to return the actual key, but we only have the hash
            # For testing, we'll use a known key that we'll set up
            return "ioc_dev_test_key_12345678901234567890123456789012"
        return None
    finally:
        session.close()


@pytest.fixture
def client(setup_test_environment, dev_api_key):
    """Create an authenticated test client for the FastAPI app after DB setup."""
    test_client = TestClient(app)
    # Set default API key header for all requests
    if dev_api_key:
        test_client.headers = {"X-API-Key": dev_api_key}
    return test_client


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up clean database per test session."""
    os.environ["POSTGRES_DB"] = "tkf_test"
    os.environ.setdefault("POSTGRES_USER", "postgresUser")
    os.environ.setdefault("POSTGRES_PASSWORD", "postgresPW")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    _ensure_test_database_exists()
    try:
        db = RelationalDB()
        db.init()
        Base.metadata.drop_all(bind=db.engine)
        Base.metadata.create_all(bind=db.engine)

        session = db.session_factory()

        # Create dev-user for testing
        from server.common import encrypt_data, get_global_encryption_key
        key = get_global_encryption_key()
        encrypted_password = encrypt_data("dev", key)

        dev_user = User(
            id="dev-user",
            username="dev-user",
            password=encrypted_password,
            domain="test.local",
            role="admin",
        )
        session.add(dev_user)
        session.commit()

        # Create API key for dev-user with a known key for testing
        test_api_key = "ioc_dev_test_key_12345678901234567890123456789012"
        key_hash = hashlib.sha256(test_api_key.encode()).hexdigest()
        key_preview = f"{test_api_key[:15]}..."

        dev_api_key = ApiKey(
            user_id="dev-user",
            key_hash=key_hash,
            key_preview=key_preview,
            name="Test API Key"
        )
        session.add(dev_api_key)
        session.commit()

        session.close()
    except Exception as e:
        print(f"Database setup failed: {e}")
        pass

    yield

    try:
        db = RelationalDB()
        session = db.session_factory()
        try:
            session.query(WorkspaceInvitation).delete()
            session.query(WorkspaceMember).delete()
            session.query(ApiKey).delete()
            session.query(User).delete()
            session.query(CognitiveFabricNode).delete()
            session.query(MultiAgenticSystem).delete()
            session.query(Workspace).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        pass


@pytest.fixture
def sample_workspace_data():
    """Sample workspace data for testing."""
    return {"name": "Test Workspace"}


@pytest.fixture
def created_workspace(client, sample_workspace_data):
    """Create a workspace and return its ID."""
    response = client.post("/api/workspaces", json=sample_workspace_data)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def test_user():
    """Create a test user in the database and return user data."""
    import uuid

    from server.common import encrypt_data, get_global_encryption_key

    db = RelationalDB()
    session = db.session_factory()
    try:
        user_id = str(uuid.uuid4())
        password = "testpassword"
        key = get_global_encryption_key()
        encrypted_password = encrypt_data(password, key)

        user = User(
            id=user_id,
            username="testuser",
            password=encrypted_password,
            domain="test.local",
            role="viewer",  # Non-admin role
        )
        session.add(user)
        session.commit()

        return {
            "id": user_id,
            "username": "testuser",
            "domain": "test.local",
            "role": "viewer",
            "email": "testuser@test.local",
        }
    finally:
        session.close()


@pytest.fixture
def admin_user():
    """Create an admin user in the database and return user data."""
    import uuid

    from server.common import encrypt_data, get_global_encryption_key

    db = RelationalDB()
    session = db.session_factory()
    try:
        user_id = str(uuid.uuid4())
        password = "adminpassword"
        key = get_global_encryption_key()
        encrypted_password = encrypt_data(password, key)

        user = User(
            id=user_id,
            username="adminuser",
            password=encrypted_password,
            domain="test.local",
            role="admin",  # Admin role
        )
        session.add(user)
        session.commit()

        return {
            "id": user_id,
            "username": "adminuser",
            "domain": "test.local",
            "role": "admin",
            "email": "adminuser@test.local",
        }
    finally:
        session.close()
