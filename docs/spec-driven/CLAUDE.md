# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## User specific instructions
- Make changes in backend service: ioc-cfn-mgmt-backend-svconly
- Do not modify frontend service: ioc-cfn-mgmt-ui-svc

## Repository Overview

This is a multi-service TKF (Trusted Knowledge Fabric) platform with two main services:

1. **ioc-cfn-mgmt-ui-svc** - Next.js frontend (port 3000)
2. **ioc-cfn-mgmt-backend** - FastAPI backend service (port 8000)

### Service Architecture

```
┌─────────────────────┐
│  ioc-cfn-mgmt-ui-svc  │  Next.js 15 + TypeScript
│     Port 3000       │  (Frontend UI)
└──────────┬──────────┘
           │
           ▼
┌────────────────────────┐
│ ioc-cfn-mgmt-backend-svc  │  FastAPI + Python 3.10+
│      Port 8000         │  (Backend Service)
└────────┬───────────────┘
         │
         ▼
    ┌────────┐
    │Postgres│  PostgreSQL 17 + TimescaleDB
    └────────┘
```

The UI connects directly to the Backend service, which manages workspaces, users, API keys, CFN nodes, Multi-Agentic Systems, and interacts with PostgreSQL (relational DB).

**Note:** Neo4j graph database is included in docker-compose but not currently integrated into the application.

## Development Commands

### ioc-cfn-mgmt-ui-svc (Next.js Frontend)

```bash
cd ioc-cfn-mgmt-ui-svc

# Install dependencies
npm install

# Development server
npm run dev

# Build
npm run build
npm start

# Linting
npm run lint:check    # Check only
npm run lint          # Fix issues

# Clean
npm run clean         # Remove .next cache
npm run build:clean   # Clean build
```

**Test credentials:** Username: `admin`, Password: `admin`

### ioc-cfn-mgmt-backend-svc(Backend Service)

Uses **Task** and **Poetry**. Requires PostgreSQL database.

```bash
cd ioc-cfn-mgmt-backend

# Setup - Option 1: With local databases
task run             # Installs deps, applies migrations, generates DEK, runs server

# Setup - Option 2: Start databases with Docker
task docker-compose-db-up    # Start only databases
task run                     # Run service

# Setup - Option 3: Full stack
task docker-compose-full-stack-up       # Start everything

# Development
task dev             # Dev server with hot reload
task install-poetry  # Install dependencies only

# Database migrations
task db-migrate-apply        # Apply migrations
task db-migrate-new          # Create new migration (provide name as argument)

# Testing
task test            # Run all tests

# Alternative: Run tests directly with venv (if task is not available)
.venv/bin/python -m pytest tests/ -v                    # All tests
.venv/bin/python -m pytest tests/test_workspaces.py -v # Specific file
```

**Testing Notes:**
- Tests use pytest with async support (pytest-asyncio, pytest-anyio)
- Test database: PostgreSQL with `tkf_test` database
- DELETE endpoints return 204 (No Content) status code on success, not 200
- The virtual environment is located at `.venv/` in the backend directory

**API Documentation:** http://localhost:8000/docs

**Key endpoints:**

**IAM (Identity and Access Management):**
- API Keys: GET|POST|DELETE `/api/iam/api-keys`
- Users: GET `/api/iam/users`
- Roles: GET `/api/iam/roles`

**Workspaces:**
- Workspaces: GET|POST|PUT|DELETE `/api/workspaces`
- Workspace Members: GET|POST|DELETE `/api/workspaces/{workspace_id}/members`
- Workspace Invitations: GET|POST|DELETE `/api/workspaces/{workspace_id}/invitations`

**Workspace Resources (require workspace membership):**
- Multi-Agentic Systems: GET|POST|DELETE `/api/workspaces/{workspace_id}/multi-agentic-systems`
- Cognitive Fabric Nodes: GET|POST|PUT|DELETE `/api/workspaces/{workspace_id}/cognitive-fabric-node`

**Other Endpoints:**
- Audit Logs: GET `/api/audits`

**API Conventions:**
- POST (Create): Returns 201 Created with resource in response body
- GET (Read): Returns 200 OK with resource(s) in response body
- PUT (Update): Returns 200 OK with updated resource in response body
- DELETE: Returns 204 No Content on success (no response body)

**API Authentication & Authorization:**

### API Keys
- **Scope:** User-scoped (not workspace-scoped)
- **Authentication:** `X-API-Key` header
- **Format:** `ioc_[48-character-random-string]`
- **Security:** SHA-256 hashed in database, full key shown only once on creation

### Authorization Flow
1. API key identifies the user
2. Workspace context specified in API call (path param or body)
3. System checks: "Does this user have access to this workspace?"
4. Access granted if user is in workspace.users[] array (or is admin)

### Workspace Access
- Users can only access workspaces they are members of
- Admin role has global access to all workspaces
- Workspace membership stored in `workspace.users` array

### Role Inheritance
- API keys automatically inherit their user's current role
- When a user's role changes, all their API keys reflect the new role immediately
- Single source of truth: user.role in the User table

### Example API Calls
```bash
# API key in header identifies the user
curl -H "X-API-Key: ioc_xxx..." \
  GET http://localhost:8000/api/workspaces/workspace-123/multi-agentic-systems

# User must be member of workspace-123 or be an admin
```

## Default Workspaces

Every user in the system automatically gets their own "Default Workspace" upon user creation:

### Automatic Workspace Creation

**Admin User (System Startup):**
- When the system starts, the admin user is auto-created
- A "Default Workspace" is automatically created for the admin user
- Admin is set as the workspace creator and added as a workspace admin
- Implementation: `WorkspaceService.create_admin_default_workspace()` in `src/server/main.py`

**Regular Users (Signup Flow):**
- When a user signs up via `POST /api/auth/signup`, a new user account is created
- A "Default Workspace" is automatically created for that user
- User is set as the workspace creator and added as a workspace admin
- Implementation: `auth_service.signup()` in `src/server/services/auth.py`

### Key Characteristics

- **Isolated**: Each user gets their own separate default workspace
- **Named "Default Workspace"**: All default workspaces share this name (but have unique IDs)
- **User is Creator**: The user who owns the workspace is set as `created_by`
- **User is Admin**: The user is automatically added as a workspace member with role "admin"
- **Full Control**: Users have complete control over their default workspace

### Workspace Isolation Example

```
User: admin
  └─> Workspace: "Default Workspace" (ID: aaa-111)

User: john
  └─> Workspace: "Default Workspace" (ID: bbb-222)

User: jane
  └─> Workspace: "Default Workspace" (ID: ccc-333)

Each user only sees their own workspace when they list workspaces.
```

### API Behavior

**After Admin Login:**
```bash
GET /api/workspaces
Headers: Authorization: Bearer <admin-token>
→ Returns: [{ "id": "aaa-111", "name": "Default Workspace", ... }]
```

**After User Signup:**
```bash
POST /api/auth/signup
{ "username": "john", "email": "john@example.com", "password": "..." }
→ Creates user + "Default Workspace" automatically

GET /api/workspaces
Headers: Authorization: Bearer <john-token>
→ Returns: [{ "id": "bbb-222", "name": "Default Workspace", ... }]
```

**Important Notes:**
- Users can create additional workspaces beyond their default workspace
- Multiple users can have workspaces with the same name (workspaces are identified by unique IDs)
- Default workspaces are NOT shared - each user has their own isolated workspace

## User Roles & Workspace Access Control

### Role & Access Control Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER ROLES IN THE SYSTEM                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────────┐         ┌────────────────────┐
│   "admin" role     │         │ "super_admin" role │
│  (Default Role)    │         │  (Future Feature)  │
├────────────────────┤         ├────────────────────┤
│ - Default for all  │         │ - Elevated access  │
│   new users        │         │ - Sees ALL         │
│ - NOT a super      │         │   workspaces       │
│   admin            │         │ - Full system      │
│ - Limited access   │         │   access           │
└────────────────────┘         └────────────────────┘
        │                               │
        ▼                               ▼
Can only see/access            Can see/access ALL
workspaces where:              workspaces (no restrictions)
- Workspace admin OR
- Workspace creator
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WORKSPACE MEMBERSHIP & ACCESS                            │
└─────────────────────────────────────────────────────────────────────────────┘

DATABASE TABLES:
┌──────────────────┐                    ┌─────────────────────┐
│   User Table     │                    │  Workspace Table    │
├──────────────────┤                    ├─────────────────────┤
│ - id             │                    │ - id                │
│ - username       │                    │ - name              │
│ - password       │                    │ - created_by ◄──────┼── Creator tracking
│ - role ◄─────────┼─ System role      │ - config            │
│   (admin/        │   (NOT workspace   │ - created_at        │
│   super_admin)   │    role)           │ - deleted_at        │
└──────────────────┘                    └─────────────────────┘
        │                                         ▲
        │                                         │
        │         ┌───────────────────────────────┘
        │         │
        ▼         ▼
┌─────────────────────────────────┐
│  WorkspaceMember Table          │
├─────────────────────────────────┤
│ - workspace_id (FK)             │
│ - user_id (FK)                  │
│ - role ◄────────────────────────┼── Workspace role (admin/viewer/guest)
│   (admin/viewer/guest)          │
│ - joined_at                     │
│ - deleted_at                    │
└─────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ACCESS CONTROL LOGIC                                 │
└─────────────────────────────────────────────────────────────────────────────┘

User wants to access Workspace X
         │
         ▼
    ┌─────────────────────┐
    │ Is user role =      │───YES──► Grant access to ALL workspaces
    │ "super_admin"?      │
    └─────────────────────┘
         │ NO
         ▼
    ┌─────────────────────┐
    │ Check TWO           │
    │ conditions:         │
    └─────────────────────┘
         │
         ├─► Condition 1: Is user a WORKSPACE ADMIN?
         │   Query: workspace_member.user_id = user.id
         │           AND workspace_member.role = "admin"
         │           AND workspace_member.workspace_id = X
         │
         └─► Condition 2: Is user the CREATOR?
             Query: workspace.created_by = user.id
                    AND workspace.id = X
         │
         ▼
    ┌─────────────────────┐
    │ If EITHER condition │───YES──► Grant access to Workspace X
    │ is TRUE             │
    └─────────────────────┘
         │ NO
         ▼
    Deny access (403 Forbidden)
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REAL-WORLD SCENARIOS                                │
└─────────────────────────────────────────────────────────────────────────────┘

SCENARIO 1: User Creates a Workspace
─────────────────────────────────────
┌──────────────┐    Creates      ┌────────────────┐
│  User A      │───Workspace────►│  Workspace 1   │
│ role: admin  │                 │ created_by: A  │
└──────────────┘                 └────────────────┘
      │                                  ▲
      │    Automatically added           │
      │    as workspace admin            │
      └──────────────────────────────────┘
           (workspace_member table)

Result: User A can see Workspace 1 ✓
        - Reason: Creator AND workspace admin


SCENARIO 2: User Invited as Workspace Admin
────────────────────────────────────────────
┌──────────────┐   Invites     ┌──────────────┐
│  User A      │──────────────►│  User B      │
│ role: admin  │   as "admin"  │ role: admin  │
└──────────────┘   to WS 1     └──────────────┘
      │                                │
      │ Workspace 1                    │
      │ created_by: A                  │ Added as workspace admin
      ▼                                ▼
 Can see WS 1 ✓              Can see WS 1 ✓
 (creator)                   (workspace admin)


SCENARIO 3: User Invited as Viewer
───────────────────────────────────
┌──────────────┐   Invites     ┌──────────────┐
│  User A      │──────────────►│  User C      │
│ role: admin  │   as "viewer" │ role: admin  │
└──────────────┘   to WS 1     └──────────────┘
      │                                │
      │ Workspace 1                    │
      │ created_by: A                  │ Added as viewer (not admin)
      ▼                                ▼
 Can see WS 1 ✓              CANNOT see WS 1 ✗
 (creator)                   (not workspace admin,
                              not creator)


SCENARIO 4: Super Admin Access
───────────────────────────────
┌──────────────┐
│  User S      │
│ role:        │──────────────► Can see ALL workspaces ✓✓✓
│ super_admin  │                (Workspace 1, 2, 3, ...)
└──────────────┘
      │
      └─► No need to be member or creator
          Role grants universal access


SCENARIO 5: Multiple Workspaces
────────────────────────────────
User A (admin)          User B (admin)          User C (admin)
     │                       │                       │
     ├─ Creates WS 1         ├─ Creates WS 2         ├─ Creates WS 3
     │  (creator)            │  (creator)            │  (creator)
     │                       │                       │
     ├─ Sees: WS 1 only ✓    ├─ Sees: WS 2 only ✓    ├─ Sees: WS 3 only ✓
     │                       │                       │
     └─ Cannot see WS 2 ✗    └─ Cannot see WS 1 ✗    └─ Cannot see WS 1 ✗
       Cannot see WS 3 ✗      Cannot see WS 3 ✗      Cannot see WS 2 ✗

ISOLATION: Each user only sees their own workspaces!
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WORKSPACE ROLE HIERARCHY                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Workspace Member Roles (in workspace_member table):

┌────────────────┐
│  admin         │ ◄── Can see workspace in listings
├────────────────┤     Can manage workspace members
│ Permissions:   │     Can modify workspace settings
│ - Full control │     Can delete workspace
│ - Manage users │
│ - All actions  │
└────────────────┘

┌────────────────┐
│  viewer        │ ◄── CANNOT see workspace in listings
├────────────────┤     Can view workspace resources if accessed directly
│ Permissions:   │     Cannot modify workspace
│ - Read only    │
│ - View data    │
└────────────────┘

┌────────────────┐
│  guest         │ ◄── CANNOT see workspace in listings
├────────────────┤     Limited access to specific resources
│ Permissions:   │     Cannot modify workspace
│ - Limited read │
│ - Restricted   │
└────────────────┘

IMPORTANT: Only "admin" workspace members can see the workspace in their
           workspace list. Viewers and guests must be given direct links.
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KEY DISTINCTIONS                                    │
└─────────────────────────────────────────────────────────────────────────────┘

USER ROLE vs WORKSPACE ROLE:

┌─────────────────────────────┐    ┌──────────────────────────────┐
│      USER ROLE              │    │     WORKSPACE ROLE           │
│   (user.role column)        │    │ (workspace_member.role)      │
├─────────────────────────────┤    ├──────────────────────────────┤
│ • System-level role         │    │ • Workspace-level role       │
│ • Values: admin,            │    │ • Values: admin, viewer,     │
│   super_admin               │    │   guest                      │
│ • Controls system access    │    │ • Controls workspace access  │
│ • Default: "admin"          │    │ • Set when user joins        │
│ • NOT workspace-specific    │    │   workspace                  │
└─────────────────────────────┘    └──────────────────────────────┘

Example:
--------
User: Alice
  - user.role = "admin" (system role - default for all users)
  - workspace_member[WS1].role = "admin" (can see & manage WS1)
  - workspace_member[WS2].role = "viewer" (cannot see WS2 in list)

Result: Alice sees only WS1 in her workspace list, even though she's a
        member of both WS1 and WS2. This is because only workspace admins
        and creators can see workspaces in listings.
```

### Workspace Access Summary

**Users can LIST/ACCESS a workspace if:**
1. Their system role is `super_admin`, OR
2. Their workspace role is `admin` in that workspace (in `workspace_member` table), OR
3. They created the workspace (`workspace.created_by` matches their `user_id`)

**Users CANNOT LIST/ACCESS a workspace if:**
- They are a `viewer` or `guest` member (even if they have system role = "admin")
- They are not a member at all
- They didn't create the workspace

**Special Notes:**
- When a user creates a workspace, they are automatically added as a workspace admin
- The `workspace.created_by` field provides a fallback access mechanism
- System role "admin" is the DEFAULT role for all users (not elevated access)
- Only "super_admin" system role bypasses workspace membership checks

## High-Level Architecture

### Frontend Architecture (ioc-cfn-mgmt-ui-svc)

- **Framework:** Next.js 15 with App Router (app directory structure)
- **Routes:**
  - `app/(protected)/*` - Authenticated routes (settings, queries, workspaces, software)
  - `app/(public)/*` - Public routes (login)
  - `app/api/auth/*` - NextAuth API routes
- **State Management:** Zustand (see `src/store/`)
- **Data Fetching:** SWR for caching (see `src/lib/swr-config.ts`)
- **API Client:** Centralized in `src/api/client.ts` with config in `src/api/config.ts`
- **Authentication:** NextAuth configured in `src/lib/auth-config.ts` and `src/lib/auth.ts`
- **UI Components:** shadcn/ui + Radix UI + Tailwind CSS 4
- **Key directories:**
  - `src/components/` - Reusable UI components
  - `src/hooks/` - Custom React hooks
  - `src/providers/` - React context providers
  - `src/types/` - TypeScript type definitions
  - `src/utils/` - Utility functions

**Environment:** Set `CFN_UI_API_BASE_URL` to point to the Backend service (default: http://localhost:8000)

### Backend Service Architecture (ioc-cfn-mgmt-backend)

- **Framework:** FastAPI with PostgreSQL database
- **Core modules:**
  - `src/server/` - Main application
    - `api/` - API route handlers
    - `database/` - Database layer
      - `relational_db/` - PostgreSQL with TimescaleDB
      - `graph_db/` - Neo4j integration (not currently used)
    - `adapters/` - External adapters
    - `schemas/` - Pydantic schemas
    - `services/` - Business logic
    - `utils/` - Utilities
    - `main.py` - Application entry point
  - `src/app_logging/` - Centralized logging
- **Database Management:**
  - Uses **Atlas** for SQL migrations (installed via `task install-atlas`)
  - Migrations stored in `src/server/database/relational_db/migrations/`
  - Data encryption key (DEK) generated via `task generate-dek`
- **Dependencies:**
  - PostgreSQL 17 with TimescaleDB for relational data
  - Neo4j (included in docker-compose but not integrated)

## Common Patterns

### Task Automation

The Backend service uses **Taskfile.yaml** for common operations. View available tasks:

```bash
task --list
```

### Logging

The Backend service uses the centralized `app_logging` module:

```python
from app_logging import setup_logging, get_loggers_info, update_log_level

# Initialize on startup
setup_logging("service-name", default_level="INFO")

# Query loggers
info = get_loggers_info()

# Update log level dynamically
update_log_level("ROOT", "DEBUG")
```

Valid log levels: DEBUG, INFO, WARNING, WARN, ERROR, CRITICAL, TRACE

### Docker Compose

The Backend service has a `docker-compose.yml` that supports profiles:

```bash
# Database only
task docker-compose-db-up

# Full stack
task docker-compose-full-stack-up
```

## Coding Conventions

### Naming Conventions

**File Naming:**
- ✅ Use full descriptive names, not abbreviations
- ✅ Good: `cognitive_fabric_node.py`, `multi_agentic_system.py`
- ❌ Avoid: `cfn.py`, `mas.py`

**Class Naming:**
- ✅ Use full descriptive names with PascalCase
- ✅ Good: `CognitiveFabricNodeService`, `CognitiveFabricNodeStatus`
- ❌ Avoid: `CFNService`, `CFNStatus`

**Service Method Naming:**
Follow standard Python convention - the class name provides context, so method names should be simple action verbs:

```python
# ✅ GOOD - Pythonic and clean
class CognitiveFabricNodeService:
    def create(self, workspace_id, data, user_id):
        """Create a new Cognitive Fabric Node"""
        pass

    def enable(self, workspace_id, node_id, user_id):
        """Enable a disabled Cognitive Fabric Node"""
        pass

    def disable(self, workspace_id, node_id, user_id):
        """Disable a Cognitive Fabric Node"""
        pass

    def delete(self, workspace_id, node_id, user_id):
        """Delete a Cognitive Fabric Node"""
        pass

    def update(self, workspace_id, node_id, data):
        """Update Cognitive Fabric Node"""
        pass

    def get(self, workspace_id, node_id):
        """Get Cognitive Fabric Node details"""
        pass

    def list(self, workspace_id, status_filter=None):
        """List all Cognitive Fabric Nodes"""
        pass

# ❌ AVOID - Redundant and verbose
class CognitiveFabricNodeService:
    def create_cognitive_fabric_node(self, ...):  # Too long
        pass

    def get_cfn(self, ...):  # Abbreviation
        pass
```

**Usage Examples:**
```python
# Clean service calls - context is clear from service name
cognitive_fabric_node_service.create(ws_id, data, user_id)
cognitive_fabric_node_service.disable(ws_id, cfn_id, user_id)
cognitive_fabric_node_service.delete(ws_id, cfn_id, user_id)
multi_agentic_system_service.create(ws_id, data)
workspace_service.create(data, user_id)
workspace_service.exists(ws_id)
user_service.get(user_id)
```

**API Field Naming:**
- API field names may use abbreviations for brevity (part of API contract)
- Examples: `cfn_id`, `cfn_name`, `cfn_config`, `mas_id`
- These are preserved for backward compatibility and API consistency

**Test Class Naming:**
```python
# ✅ GOOD - Descriptive test classes
class TestCognitiveFabricNodeRegistration:
    def test_successful_registration(self):
        pass

# ❌ AVOID - Abbreviated test classes
class TestCFNRegistration:
    pass
```

### Service Patterns

**Service Singletons:**
```python
# In service file (e.g., cognitive_fabric_node.py)
class CognitiveFabricNodeService:
    def register(self, ...):
        pass

# Singleton instance at bottom of file
cognitive_fabric_node_service = CognitiveFabricNodeService()
```

**Service Exports:**
```python
# In services/__init__.py
from .cognitive_fabric_node import cognitive_fabric_node_service, CognitiveFabricNodeService
from .multi_agentic_system import multi_agentic_system_service, MultiAgenticSystemService
from .workspace import workspace_service, WorkspaceService
from .user import user_service, UserService
```

## Prerequisites

### ioc-cfn-mgmt-ui-svc
- Node.js >= 13.8.0
- npm >= 6.14.4

### Backend Service (ioc-cfn-mgmt-backend)
- Python 3.10+
- Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- Task (go-task):
  - macOS: `brew install go-task/tap/go-task`
  - Linux: `snap install task --classic` or `apt install task`
  - npm: `npm install -g @go-task/cli`

### Additional Backend Requirements
- Atlas migration tool (auto-installed via `task install-atlas`)
- PostgreSQL 17 with TimescaleDB extension

## Service Communication

The services communicate directly:
1. Frontend (port 3000) → Backend Service (port 8000)
2. Backend Service → PostgreSQL Database (port 5432)

Configure service URLs via environment variables:
- Frontend: `CFN_UI_API_BASE_URL` (points to Backend service, default: http://localhost:8000)

## Deployment

### Kubernetes with Helm

The Backend service includes Helm charts in `deploy/charts/`:

```bash
# Lint
task helm-lint

# Template review
task helm-template

# Install
helm install ioc-cfn-mgmt-backend-svc./deploy/charts/ioc-cfn-mgmt-backend-svc--namespace tkf-platform

# Upgrade
helm upgrade ioc-cfn-mgmt-backend-svc./deploy/charts/ioc-cfn-mgmt-backend
```

Configure health probes to use `/api/internal/diagnostics/health` endpoint.

### Cognitive Fabric Node (CFN)

**Implementation Date**: January 30, 2026
**Status**: ✅ Complete and Ready for Testing

These services are part of data path. Short Form - CFN.
ioc-mgmt-svc <-> ioc-cfn. This communication contract is purely http REST based.

**Naming Convention Note:**
- API endpoints and field names use abbreviation: `cfn` (e.g., `cfn_id`, `cfn_name`, `/cognitive-fabric-node`)
- Code (classes, files, methods) use full names: `CognitiveFabricNode`, `cognitive_fabric_node.py`
- This follows Python conventions: full descriptive names in code, concise names in APIs

**Endpoints for CFN:**
- Create: POST `/api/workspaces/{workspace_id}/cognitive-fabric-node`
- Enable: PATCH `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/enable`
- Disable: PATCH `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/disable`
- Delete: DELETE `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}`
- Heartbeat: PUT `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat`
- Update: PUT `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}`
- List: GET `/api/workspaces/{workspace_id}/cognitive-fabric-node`
- Get Details: GET `/api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}`

**Note**: CFNs are like IoT devices - they always call the same create endpoint.
Disabled CFNs must be manually enabled before they can reconnect. See [CFN.md](./CFN.md) for detailed lifecycle documentation.

**Note**: We do not implement CFN here. Only the management side is implemented.

#### CFN Design Overview

- CFN initiates the connection to Mgmt service using the management host/port it was configured with
- CFN provides these in JSON format to Mgmt service for registration:
```json
{
  "cfn_id": "cfn-node-001",
  "cfn_name": "production-cfn-1",
  "cfn_config": {
    "memory": "8GB",
    "max_connections": 500
  }
}
```

- Mgmt creates this CFN and returns back the `cloud_config` JSON which CFN applies to its service
- Note: `mgmt_host_ip` and `mgmt_port` stored in the database represent the management backend address, not sent by CFN
- On Mgmt side, it maintains the list of CFN nodes with their last-seen timestamp
- CFN nodes periodically send heartbeat pings to Mgmt to update their last-seen timestamp
- If a CFN node misses heartbeats beyond a threshold (2 minutes), Mgmt marks it as offline
- Mgmt creates a line item in its Postgres DB for each CFN node with its details:
  - Creation creates this entry with `enabled=true` by default
  - Disable sets `enabled=false` (soft disable, ID locked, cannot auto re-enable)
  - Delete sets `deleted_at` timestamp (hard delete, ID can be reused)
  - Updates modify the existing entry (name change is allowed, but `cfn_id` is immutable)
- Mgmt exposes APIs to list all CFN nodes, their status, and details
- CFN can query its own status from Mgmt to get workspace context and config
- CFNs can query all other CFNs in the system within the workspace context

#### CFN Onboarding & Workspace Scoping

**Architectural Decision:** CFNs are workspace-scoped resources.

**Design Rationale:**

The architecture maintains these two key principles:
1. **API Keys remain user-scoped** (not workspace-scoped) - for flexibility and backward compatibility
2. **CFN resources remain workspace-scoped** - for tenant isolation and resource attribution

**Why CFNs are Workspace-Scoped:**
- ✅ **Tenant Isolation**: Maintains strict data boundaries between workspaces (critical for compliance)
- ✅ **Resource Attribution**: Clear ownership, billing, and quotas per workspace
- ✅ **Architectural Consistency**: All workspace resources (Multi-Agentic Systems, CFNs) follow the same pattern
- ✅ **Access Control**: Clean, workspace-based authorization model
- ✅ **Audit Trail**: Per-workspace audit logs for CFN operations

**Why API Keys are User-Scoped:**
- ✅ **Flexibility**: Users can access multiple workspaces with a single API key
- ✅ **Backward Compatibility**: No breaking changes to existing API key system
- ✅ **Cross-Workspace Operations**: Supports users who manage multiple workspaces
- ✅ **Simplified Key Management**: Users don't need separate keys per workspace

**CFN Onboarding Flow:**

When deploying a CFN, it must be configured with three pieces of information:
1. **Management Endpoint**: The backend service endpoint (e.g., `http://localhost:8000`)
2. **API Key**: User-scoped API key for authentication
3. **Workspace ID**: The workspace this CFN belongs to

**Configuration Example:**

```yaml
# CFN Configuration (cfn-config.yaml)
cfn_id: "cfn-node-001"
cfn_name: "production-cfn-1"

# Management connection
mgmt_endpoint: "http://localhost:8000"
api_key: "ioc_[your-api-key]"
workspace_id: "ws-abc-123"  # CFN is deployed with workspace ID

# CFN-specific config
cfn_config:
  memory: "8GB"
  max_connections: 500
```

**Registration Flow:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CFN REGISTRATION FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

1. CFN Deployment
   ↓
   CFN reads config → Gets workspace_id, api_key, mgmt_endpoint

2. CFN Create Call
   ↓
   POST /api/workspaces/{workspace_id}/cognitive-fabric-node
   Headers: X-API-Key: {api_key}
   Body: {cfn_id, cfn_name, cfn_config}

3. Backend Authentication & Authorization
   ↓
   a) Verify API key is valid (identifies user)
   b) Check user has admin access to workspace_id
   c) Workspace admin or creator → Authorized ✓
   d) Non-admin or non-member → Denied ✗

4. Backend Create Logic
   ↓
   a) Check if CFN exists in workspace
   b) New CFN → Create entry (enabled=true, status=offline)
   c) Deleted CFN → Reuse ID to create new CFN (enabled=true, status=offline)
   d) Active CFN → Refresh config (reboot scenario, status reset to offline)
   e) Disabled CFN → Return 403 Forbidden (ID locked, requires manual enable)

5. Backend Response
   ↓
   Returns cloud_config (workspace settings + configuration)

6. CFN Applies Config
   ↓
   CFN applies cloud_config and begins operations

7. CFN Heartbeat
   ↓
   PUT /api/workspaces/{workspace_id}/cognitive-fabric-node/{cfn_id}/heartbeat
   → Status changes from 'offline' to 'online'
```

**Key Points:**

- **CFN knows its `workspace_id` at deployment time** (pre-configured in deployment config)
- API key identifies the user (who must have admin access to the workspace)
- All CFN endpoints include `{workspace_id}` in the path for workspace isolation
- CFNs cannot switch workspaces - they're bound to one workspace for their lifetime
- Multiple CFNs can belong to the same workspace
- CFN is infrastructure **owned by a workspace**, like Multi-Agentic Systems

**Authorization Requirements:**

| Operation       | Required Permission                      |
| --------------- | ---------------------------------------- |
| Create CFN      | Workspace admin or super_admin           |
| Enable CFN      | Workspace admin or super_admin           |
| Disable CFN     | Workspace admin or super_admin           |
| Delete CFN      | Workspace admin or super_admin           |
| Update CFN      | Workspace admin or super_admin           |
| List CFNs       | Workspace admin/viewer or super_admin    |
| Get CFN Details | Workspace admin/viewer or super_admin    |
| Send Heartbeat  | Authenticated user (CFN must be enabled) |

**Alternative Approaches Considered (and rejected):**

1. ❌ **Workspace-Scoped API Keys**:
   - Would require breaking changes to API key system
   - Users would need multiple keys for multiple workspaces
   - Complex key management and less flexible

2. ❌ **Non-Workspace-Scoped CFNs**:
   - Would break tenant isolation (security risk)
   - Hard to attribute resource usage/billing
   - Inconsistent with architecture (Multi-Agentic Systems are workspace-scoped)
   - Who manages a shared CFN? Access control becomes complex
   - Data leakage risk between workspaces

3. ✅ **Current Approach** (CFN pre-configured with workspace_id):
   - Simple: CFN knows its workspace at deployment time
   - Secure: Maintains tenant isolation
   - Consistent: Follows same pattern as other workspace resources
   - Flexible: API keys work across workspaces
   - How IoT devices work: Pre-configured with their tenant/account ID

#### Quick Start

**Step 1: Apply Database Migration**
```bash
cd ioc-cfn-mgmt-backend-svc
task docker-compose-db-up
task db-migrate-apply
```

**Step 2: Run Tests**
```bash
# Run all Cognitive Fabric Node tests (35 tests)
poetry run pytest tests/test_cognitive_fabric_node.py -v
```

**Step 3: Start the Service**
```bash
task dev  # Service starts on http://localhost:8000
```

#### API Examples

**Create a CFN Node**
```bash
export API_KEY="your-api-key"
export WS_ID="your-workspace-id"

# CFN calls this from its configured management endpoint
curl -X POST "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "cfn_id": "cfn-node-001",
    "cfn_name": "my-cfn-node",
    "cfn_config": {"memory": "4GB"}
  }'
```

**Send Heartbeat**
```bash
curl -X PUT "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node/cfn-node-001/heartbeat" \
  -H "X-API-Key: $API_KEY"
```

**List CFN Nodes**
```bash
curl "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node" \
  -H "X-API-Key: $API_KEY"
```

**Disable a CFN Node**
```bash
curl -X PATCH "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node/cfn-node-001/disable" \
  -H "X-API-Key: $API_KEY"
```

**Delete a CFN Node**
```bash
# CFN must be disabled first
curl -X DELETE "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node/cfn-node-001" \
  -H "X-API-Key: $API_KEY"
```

**Re-enable and Reconnect a Disabled CFN**
```bash
# Step 1: Admin enables the CFN
curl -X PATCH "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node/cfn-node-001/enable" \
  -H "X-API-Key: $API_KEY"

# Step 2: CFN reconnects using create endpoint
curl -X POST "http://localhost:8000/api/workspaces/$WS_ID/cognitive-fabric-node" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "cfn_id": "cfn-node-001",
    "cfn_name": "my-cfn-node",
    "cfn_config": {"memory": "8GB"}
  }'
```

#### Database Schema

**Table**: `cognitive_fabric_node`

**Key Fields**:
- `cfn_id` (VARCHAR 255, PRIMARY KEY) - CFN's persistent identifier (immutable)
- `workspace_id` (VARCHAR 36, FOREIGN KEY) - Links to workspace
- `cfn_name` (VARCHAR 255) - Human-readable name (can be updated)
- `mgmt_host_ip` (VARCHAR 255, OPTIONAL) - Management backend IP (not provided by CFN)
- `mgmt_port` (INTEGER, OPTIONAL) - Management backend port (not provided by CFN)
- `cfn_config` (JSONB, OPTIONAL) - CFN's reported configuration
- `cloud_config` (JSONB, OPTIONAL) - Management's desired configuration
- `status` (VARCHAR 50, DEFAULT 'online') - online/offline
- `last_seen` (TIMESTAMP, DEFAULT NOW) - Last heartbeat timestamp
- `enabled` (BOOLEAN, DEFAULT true) - Whether node is enabled
- `created_at`, `updated_at`, `created_by`, `updated_by` - Audit fields
- `deleted_at` (TIMESTAMP, NULLABLE) - Soft delete support

**Note on mgmt_host_ip and mgmt_port**: These fields store the management backend's address
that CFN uses to connect, but they are NOT sent by CFN during registration. They can be set
by the management service if needed for tracking purposes.

**Migration**: `src/server/database/relational_db/migrations/20260130185900_add_cognitive_fabric_node_table.sql`

#### Authorization

**Write Access** (Create, Enable, Disable, Delete, Update):
- Workspace admin or super_admin

**Read Access** (List, Get Details):
- Workspace admin/viewer or super_admin

**Heartbeat**:
- Authenticated only (no admin requirement)
- Disabled nodes cannot send heartbeats (403 Forbidden)

#### IoT-Style Create Endpoint

CFN nodes are like IoT devices - they always call the same create endpoint.
The management service handles different scenarios automatically:

**New CFN:**
- Creates new CFN entry with `enabled=true`, `status='offline'`

**Deleted CFN (ID Reuse):**
- Detects CFN with `deleted_at` set
- Reuses ID to create new CFN: clears `deleted_at`, sets `enabled=true`, `status='offline'`
- Fresh start with new configuration

**Active CFN (Reboot):**
- Allows CFN to refresh config after reboot/reconnection
- Resets status to 'offline' (must send heartbeat to become online again)
- Updates configuration with new values

**Disabled CFN:**
- Returns 403 Forbidden (ID is locked)
- Admin must enable CFN first, then CFN can reconnect

**What Happens on Create:**
- Sets `enabled=true` (unless disabled)
- Sets `status='offline'` (CFN must send heartbeat to become online)
- Updates all configuration fields
- Regenerates `cloud_config`
- Updates `last_seen` timestamp
- Creates audit trail

**Lifecycle Example:**
```bash
# Step 1: Initial Creation
POST /api/workspaces/{ws_id}/cognitive-fabric-node
{ "cfn_id": "cfn-001", "cfn_name": "node-1" }
→ 201 Created (enabled=true, status=offline)

# Step 2: CFN sends heartbeat to become online
PUT /api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/heartbeat
→ 200 OK (status=online)

# Step 3: Disable CFN
PATCH /api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/disable
→ 200 OK (enabled=false, hidden from list, ID locked)

# Step 4: Delete CFN
DELETE /api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001
→ 204 No Content (deleted_at set, ID can be reused)

# Step 5: Create new CFN with same ID (ID reuse)
POST /api/workspaces/{ws_id}/cognitive-fabric-node
{ "cfn_id": "cfn-001", "cfn_name": "node-1-v2" }
→ 201 Created (new CFN, clean slate, status=offline)

# Step 6: CFN sends heartbeat to become online
PUT /api/workspaces/{ws_id}/cognitive-fabric-node/cfn-001/heartbeat
→ 200 OK (status=online)
```

#### Background Monitoring

**Service**: `CFNMonitor` (singleton: `cfn_monitor`)

**Configuration**:
- Check interval: 60 seconds
- Offline threshold: 2 minutes (4 missed heartbeats)

**Behavior**:
- Runs as async background task
- Starts on application startup
- Stops gracefully on shutdown
- Marks online nodes as offline if last_seen > threshold

#### Key Features

- ✅ CFN creation with workspace scoping
- ✅ IoT-style create endpoint (handles new, reboot, and ID reuse scenarios)
- ✅ Separate disable/enable/delete operations for lifecycle management
- ✅ Disabled CFNs cannot auto re-enable (requires manual admin action)
- ✅ ID reuse after deletion (deleted IDs can be reused for new CFNs)
- ✅ Heartbeat monitoring (30s frequency, 2min offline threshold)
- ✅ Automatic offline detection (background job every 60s)
- ✅ Disabled nodes cannot send heartbeats
- ✅ Cloud config generation (workspace + settings)
- ✅ Complete audit trail
- ✅ Soft delete support
- ✅ Comprehensive test coverage (35 tests)

#### Status Flow

- **offline (initial)**: CFN just created, hasn't sent first heartbeat yet (enabled=true, no heartbeat sent)
- **online**: CFN is active, heartbeat within threshold (enabled=true, heartbeat sent within 2min)
- **offline (stale)**: CFN created but heartbeat exceeded 2min threshold (set by background job, enabled=true)
- **disabled**: CFN disabled by admin, cannot send heartbeats (enabled=false, deleted_at null, ID locked)
- **deleted**: CFN deleted (deleted_at set, ID can be reused)

#### Creation and Heartbeat Flow

1. **Creation**: CFN calls create endpoint → Status is "offline", enabled=true
2. **First Heartbeat**: CFN sends heartbeat → Status changes to "online"
3. **Ongoing Heartbeats**: CFN sends heartbeat every 30 seconds → Status remains "online"
4. **Missed Heartbeats**: If CFN doesn't send heartbeat for 2 minutes → Background job marks status as "offline"
5. **Disable**: Admin disables CFN → enabled=false, ID locked, hidden from list
6. **Delete**: Admin deletes CFN (must be disabled first) → deleted_at set, ID can be reused

#### Files Created

**New Files** (7):
1. `src/server/database/relational_db/models/cognitive_fabric_node.py`
2. `src/server/schemas/cognitive_fabric_node.py`
3. `src/server/services/cognitive_fabric_node.py`
4. `src/server/services/cognitive_fabric_node_monitor.py`
5. `src/server/api/endpoints/cognitive_fabric_node.py`
6. `tests/test_cognitive_fabric_node.py`
7. `src/server/database/relational_db/migrations/20260130185900_add_cognitive_fabric_node_table.sql`

**Modified Files** (5):
1. `src/server/api/api.py` - Registered cognitive_fabric_node_router
2. `src/server/main.py` - Integrated cognitive_fabric_node_monitor
3. `src/server/services/__init__.py` - Exported cognitive_fabric_node_service
4. `src/server/services/audit.py` - Added COGNITIVE_FABRIC_NODE resource type
5. `tests/conftest.py` - Added CognitiveFabricNode model to cleanup

**Service Methods:**
- `cognitive_fabric_node_service.create()` - Create new node or refresh active node
- `cognitive_fabric_node_service.enable()` - Re-enable disabled node
- `cognitive_fabric_node_service.disable()` - Disable node (soft disable)
- `cognitive_fabric_node_service.delete()` - Delete node (hard delete)
- `cognitive_fabric_node_service.update()` - Update node name/config
- `cognitive_fabric_node_service.get()` - Get node details
- `cognitive_fabric_node_service.list()` - List nodes
- `cognitive_fabric_node_service.heartbeat()` - Send heartbeat

## Authorization & RBAC

**Implementation Date**: February 10, 2026
**Status**: ✅ Enabled

The backend service implements Role-Based Access Control (RBAC) using Open Policy Agent (OPA) style Rego policies via the `regopy` library.

### RBAC Architecture

```
API Endpoint
    │
    ├─ 1. Authentication (get_auth_user)
    │     └─> Validates JWT token or API key
    │
    ├─ 2. Authorization (authz_service.require_permission)
    │     ├─> Loads user context
    │     ├─> Evaluates Rego policies
    │     └─> Returns allow/deny decision
    │
    └─ 3. Business Logic (service layer)
          └─> Executes if authorized
```

### System Roles

| Role            | Description                | Access Level                                                |
| --------------- | -------------------------- | ----------------------------------------------------------- |
| **admin**       | Default role for all users | Full access to resources they have workspace membership for |
| **viewer**      | Read-only role             | Can list and view resources, cannot modify                  |
| **guest**       | Minimal access role        | No permissions by default                                   |
| **super_admin** | Future feature             | Global access to all workspaces (bypasses membership)       |

**Important:** The "admin" role is the DEFAULT role for all new users. It does NOT grant elevated privileges - users still need workspace membership to access workspace resources.

### Permission Matrix

#### Cognitive Fabric Nodes

| Operation                                          | Admin | Viewer | Guest |
| -------------------------------------------------- | ----- | ------ | ----- |
| create, enable, disable, delete, update, heartbeat | ✅     | ❌      | ❌     |
| list, get                                          | ✅     | ✅      | ❌     |

#### Multi-Agentic Systems

| Operation              | Admin | Viewer | Guest |
| ---------------------- | ----- | ------ | ----- |
| create, update, delete | ✅     | ❌      | ❌     |
| list, get              | ✅     | ✅      | ❌     |

#### Workspaces

| Operation              | Admin | Viewer | Guest |
| ---------------------- | ----- | ------ | ----- |
| create, update, delete | ✅     | ❌      | ❌     |
| get, list              | ✅     | ✅      | ❌     |

#### API Keys

| Operation      | Admin | Viewer | Guest |
| -------------- | ----- | ------ | ----- |
| create, delete | ✅     | ❌      | ❌     |
| get, list      | ✅     | ✅      | ❌     |

### Policy Files Structure

```
src/server/authz/
├── authz_service.py           # Main authorization service
├── authz.rego                 # Main policy (delegates to roles)
├── roles/                     # Role-specific policies
│   ├── admin.rego            # Admin role permissions
│   ├── viewer.rego           # Viewer role permissions
│   └── guest.rego            # Guest role permissions (denies all)
└── operations/                # Operation-specific permission sets
    ├── workspaces.rego       # Workspace operations
    ├── api_keys.rego         # API key operations
    ├── users.rego            # User operations
    ├── iam.rego              # IAM operations
    ├── cognitive_fabric_node.rego  # CFN operations
    └── multi_agentic_system.rego   # MAS operations
```

### Using RBAC in API Endpoints

```python
from server.authz.authz_service import authz_service

@router.post("/workspaces/{workspace_id}/cognitive-fabric-node/register")
def register_cfn_node(workspace_id: str, cfn_data: dict, auth_user: dict):
    # Check workspace exists
    check_workspace_exists(workspace_id)

    # Check RBAC permissions
    authz_service.require_permission(auth_user, "register", "cognitive_fabric_node")

    # Execute business logic
    return cognitive_fabric_node_service.register(workspace_id, cfn_data, auth_user["id"])
```

### Authorization Service API

**`check_permission(user, action, resource) -> bool`**
- Returns True if permitted, False otherwise
- Use for conditional logic based on permissions

**`require_permission(user, action, resource, detail=None) -> None`**
- Raises HTTPException 403 if permission denied
- Use at the start of API endpoints to enforce access control
- Optional custom error message via `detail` parameter

### Adding New Resources to RBAC

When adding a new resource type, create three files:

1. **Operation Policy** (`src/server/authz/operations/resource_name.rego`):
```rego
package authz.operations.resource_name

import rego.v1

admin := ["create_resource", "get_resource", "update_resource", "delete_resource"]
viewer := ["get_resource"]
guest := []
```

2. **Update Admin Role** (`src/server/authz/roles/admin.rego`):
```rego
import data.authz.operations.resource_name

allow if {
    input.user.role == "admin"
    input.resource == "resource_name"
    input.operation in resource_name.admin
}
```

3. **Update Viewer Role** (`src/server/authz/roles/viewer.rego`):
```rego
import data.authz.operations.resource_name

allow if {
    input.user.role == "viewer"
    input.resource == "resource_name"
    input.operation in resource_name.viewer
}
```

### Testing RBAC

```bash
# Run RBAC-specific tests
poetry run pytest tests/test_authz_rbac.py -v

# Test with different roles
# All tests automatically use the dev-user with role="admin"
# Individual tests create users with specific roles for testing
```

### Key Points

- ✅ RBAC is **ENABLED** and actively enforced on all endpoints
- ✅ Policies defined in Rego files (declarative, easy to audit)
- ✅ Centralized authorization via `authz_service`
- ✅ All endpoints migrated to use RBAC (CFN, MAS, Workspaces, IAM)
- ✅ Comprehensive test coverage (11 RBAC-specific tests)
- ⚠️ Workspace membership checks are SEPARATE from RBAC (both are enforced)

**RBAC checks:** "Does user role allow this operation?"
**Workspace membership checks:** "Is user a member of this workspace?"

Both must pass for workspace-scoped resources.

### Documentation

For complete RBAC implementation details, see:
- **docs/spec-driven/RBAC-IMPLEMENTATION.md** - Full implementation guide
- **src/server/authz/** - Rego policy files
