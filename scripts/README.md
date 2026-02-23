# Scripts

This directory contains utility scripts for the IoC CFN Management Backend Service.

## Available Scripts

### `sample.sh`

Interactive menu-driven script for managing and testing API endpoints using predefined sample data.

**Features:**
- Menu-based navigation for all resource types (CFN, Workspaces, Memory Providers, Cognitive Engines, MAS)
- All operations use static/predefined values - no manual data entry required
- Quick Sample Data Setup option to create a complete test environment
- Automatic resource selection for get/delete operations
- Color-coded output and error handling

**What it manages:**
1. Cognitive Fabric Nodes (CFN) - create, list, get, heartbeat, disable, delete
2. Workspaces - create, list, get, delete
3. Memory Providers - create, list, get, delete
4. Cognitive Engines - create, list, get, delete
5. Multi-Agentic Systems (MAS) - create, list, get, delete

**Prerequisites:**
- Backend service running (default: `http://localhost:9000`)
- `curl` installed
- `jq` installed (optional, for better JSON formatting)

**Usage:**

```bash
# Using default URL (http://localhost:9000)
./scripts/sample.sh

# Using custom base URL
BASE_URL=http://localhost:8080 ./scripts/sample.sh
```

**Installing jq (if not installed):**

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# CentOS/RHEL
sudo yum install jq
```

**Static Values Used:**
- CFN ID: `sample-cfn-001`
- CFN Name: `Sample CFN Node`
- Workspace Name: `Sample Workspace`
- Memory Provider ID: `sample-mp-001`
- Cognitive Engine ID: `sample-engine-001`
- MAS Name: `Sample MAS`

**Example Menu:**

```
==========================================
  IoC CFN Management - Interactive Menu
==========================================

ℹ Base URL: http://localhost:9000

1. Cognitive Fabric Node (CFN)
2. Workspaces
3. Memory Providers
4. Cognitive Engines
5. Multi-Agentic Systems (MAS)

9. Quick Sample Data Setup
0. Exit

Select option:
```

**Example Create Operation:**

```
Create Cognitive Fabric Node

ℹ Using static values:
  CFN ID: sample-cfn-001
  CFN Name: Sample CFN Node
  Log Level: info
  Memory: 4GB

ℹ Creating CFN...
✓ Success (HTTP 201)
{
  "cfn_id": "sample-cfn-001",
  "workspace_ids": [],
  "cfn_name": "Sample CFN Node",
  ...
}
```

### `lint.sh`

Runs code formatting and linting checks.

**Usage:**

```bash
# Run and fix formatting issues
./scripts/lint.sh

# Check only (don't fix)
./scripts/lint.sh --check
```

### `unit-test.sh`

Runs the unit test suite.

**Usage:**

```bash
./scripts/unit-test.sh
```

## Notes

- The `sample.sh` script uses the REST API endpoints, so the backend service must be running
- Authentication is currently disabled in the backend, so no API keys or tokens are required
- All operations use predefined static values - no manual data entry required
- For resources with UUID-based IDs (Workspaces, Engines, MAS), the script automatically selects the first available resource
- Sample data uses predictable IDs (`sample-cfn-001`, `sample-mp-001`, etc.) for easy reference and cleanup
- All API calls include error handling and will display detailed error messages if something fails
- User input is only required for menu selections and delete confirmations
