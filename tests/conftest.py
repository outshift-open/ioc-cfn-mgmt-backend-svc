"""Pytest fixtures and minimal test DB bootstrap."""
import contextlib
import os
import time

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models import Base
from server.database.relational_db.models.api_key import ApiKey
from server.database.relational_db.models.cognitive_fabric_node import (
    CognitiveFabricNode,
)
from server.database.relational_db.models.multi_agentic_system import MultiAgenticSystem
from server.database.relational_db.models.user import User
from server.database.relational_db.models.workspace import Workspace
from server.database.relational_db.models.workspace_invitation import (
    WorkspaceInvitation,
)
from server.database.relational_db.models.workspace_member import WorkspaceMember
from server.main import app

os.environ.setdefault("POSTGRES_DB", "ioc_test")
os.environ.setdefault("POSTGRES_USER", "postgresUser")
os.environ.setdefault("POSTGRES_PASSWORD", "postgresPW")
os.environ.setdefault("POSTGRES_HOST", "localhost")


def _ensure_test_database_exists(max_wait_seconds: int = 20) -> None:
    """Ensure the test database exists on the configured host.

    - Respects POSTGRES_HOST (e.g., 'ioc-mgmt-relational-db' in CI)
    - Tries candidate ports: POSTGRES_PORT, 5432
    - Tries bootstrap DBs: 'postgres', 'cfn_mgmt', 'template1'
    - Retries until max_wait_seconds for containers to become ready
    """
    db_name = os.environ.get("POSTGRES_DB", "ioc_test")
    user = os.environ.get("POSTGRES_USER", "postgresUser")
    password = os.environ.get("POSTGRES_PASSWORD", "postgresPW")
    host = os.environ.get("POSTGRES_HOST", "localhost")

    candidate_ports = []
    if os.environ.get("POSTGRES_PORT"):
        candidate_ports.append(str(os.environ["POSTGRES_PORT"]))
    for p in ("5432",):
        if p not in candidate_ports:
            candidate_ports.append(p)

    bootstrap_dbs = ("postgres", "cfn_mgmt", "template1")

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
def client(setup_test_environment):
    """Create an authenticated test client for the FastAPI app after DB setup."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up clean database per test session."""
    os.environ["POSTGRES_DB"] = "ioc_test"
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

        # Create admin (mock user returned by disabled auth)
        # Note: The mock auth in server.authn.auth returns ID: "00000000-0000-0000-0000-000000000000"
        from server.common import hash_password
        hashed_password = hash_password("admin")
        admin_user = User(
            id="00000000-0000-0000-0000-000000000000",
            username="admin",
            password=hashed_password,
            domain="mock.local",
            role="admin",
        )
        session.add(admin_user)

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
def sample_cfn():
    """Register a test CFN and return its ID."""
    return "test-cfn-123"


@pytest.fixture
def registered_cfn(client):
    """Register a CFN without creating a workspace, return cfn_id."""
    import uuid

    cfn_id = f"test-cfn-{uuid.uuid4().hex[:8]}"
    cfn_data = {
        "cfn_id": cfn_id,
        "cfn_name": f"Test CFN {cfn_id}",
        "cfn_config": {"memory": "4GB", "max_connections": 100},
    }
    cfn_response = client.post("/api/cognitive-fabric-nodes/register", json=cfn_data)
    assert cfn_response.status_code == 201
    return cfn_id


@pytest.fixture
def created_cfn(client, sample_cfn):
    """Create a CFN node and a workspace that uses it, return tuple (workspace_id, cfn_id)."""
    cfn_data = {
        "cfn_id": sample_cfn,
        "cfn_name": "Test CFN Node",
        "cfn_config": {"memory": "4GB", "max_connections": 100},
    }
    cfn_response = client.post("/api/cognitive-fabric-nodes/register", json=cfn_data)
    assert cfn_response.status_code == 201
    cfn_id = cfn_response.json()["cfn_id"]

    ws_response = client.post("/api/workspaces/create", json={"name": "Test Workspace", "cfn_id": cfn_id})
    assert ws_response.status_code == 201
    workspace_id = ws_response.json()["id"]

    return (workspace_id, cfn_id)


@pytest.fixture
def sample_workspace_data(registered_cfn):
    """Sample workspace data for testing (includes required CFN)."""
    return {"name": "Test Workspace", "cfn_id": registered_cfn}


@pytest.fixture
def created_workspace(client, sample_workspace_data):
    """Create a workspace and return its ID."""
    response = client.post("/api/workspaces/create", json=sample_workspace_data)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def admin_user():
    """Create an admin user in the database and return user data."""
    import uuid

    from server.common import hash_password

    db = RelationalDB()
    session = db.session_factory()
    try:
        user_id = str(uuid.uuid4())
        password = "adminpassword"
        hashed_password = hash_password(password)

        user = User(
            id=user_id,
            username="adminuser",
            password=hashed_password,
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
