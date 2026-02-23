#!/bin/bash
# Interactive REST API script for ioc-cfn-mgmt-backend-svc
# Provides menu-driven interface to create, list, and delete sample resources

set -e

# Configuration
BASE_URL="${BASE_URL:-http://localhost:9000}"
API_PREFIX="/api"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} ${1}"
}

print_error() {
    echo -e "${RED}✗${NC} ${1}"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} ${1}"
}

print_header() {
    echo -e "${CYAN}${1}${NC}"
}

# Function to make API calls
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -X GET "${BASE_URL}${API_PREFIX}${endpoint}" \
            -H "Content-Type: application/json")
    elif [ "$method" = "DELETE" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${API_PREFIX}${endpoint}" \
            -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${API_PREFIX}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        print_success "Success (HTTP $http_code)"
        if command -v jq &> /dev/null; then
            echo "$body" | jq '.'
        else
            echo "$body"
        fi
        return 0
    elif [ "$http_code" = "409" ]; then
        print_info "Resource already exists (HTTP $http_code)"
        if command -v jq &> /dev/null; then
            echo "$body" | jq '.'
        else
            echo "$body"
        fi
        return 0
    else
        print_error "Failed (HTTP $http_code)"
        if command -v jq &> /dev/null; then
            echo "$body" | jq '.'
        else
            echo "$body"
        fi
        return 1
    fi
}

# Silent API call for programmatic use (returns only JSON body)
api_call_silent() {
    local method=$1
    local endpoint=$2
    local data=$3

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -X GET "${BASE_URL}${API_PREFIX}${endpoint}" \
            -H "Content-Type: application/json")
    elif [ "$method" = "DELETE" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${API_PREFIX}${endpoint}" \
            -H "Content-Type: application/json")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "${BASE_URL}${API_PREFIX}${endpoint}" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    # Return body to stdout for capture, print status to stderr
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        echo "$body"
        return 0
    elif [ "$http_code" = "409" ]; then
        echo "$body"
        return 0
    else
        echo "$body"
        return 1
    fi
}

# Function to pause and wait for user
pause() {
    echo ""
    read -p "Press Enter to continue..."
}

# CFN Functions
cfn_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "  Cognitive Fabric Node (CFN) Management"
        print_header "=========================================="
        echo ""
        echo "1. Create CFN"
        echo "2. List CFNs"
        echo "3. Get CFN Details"
        echo "4. Send Heartbeat"
        echo "5. Disable CFN"
        echo "6. Delete CFN"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_cfn ;;
            2) list_cfns ;;
            3) get_cfn ;;
            4) heartbeat_cfn ;;
            5) disable_cfn ;;
            6) delete_cfn ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_cfn() {
    clear
    print_header "Create Cognitive Fabric Node"
    echo ""
    print_info "Using static values:"
    echo "  CFN Name: Sample CFN Node"
    echo "  Log Level: info"
    echo "  Memory: 4GB"
    echo ""
    print_info "Creating CFN..."
    api_call POST "/cognitive-fabric-nodes" '{
  "cfn_name": "Sample CFN Node",
  "cfn_config": {
    "log_level": "info",
    "memory": "4GB"
  }
}'
    pause
}

list_cfns() {
    clear
    print_header "List All CFN Nodes"
    echo ""
    api_call GET "/cognitive-fabric-nodes" ""
    pause
}

# Helper function to get CFN ID by name
get_cfn_id_by_name() {
    local cfn_name=$1
    local response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/cognitive-fabric-nodes" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        echo "$response" | jq -r ".nodes[] | select(.cfn_name == \"${cfn_name}\") | .cfn_id" 2>/dev/null | head -1
    else
        # Fallback without jq - this is a simplified approach
        echo "$response" | grep -o '"cfn_id":"[^"]*"' | head -1 | cut -d'"' -f4
    fi
}

# Helper function to check if CFN exists by name
cfn_exists_by_name() {
    local cfn_name=$1
    local cfn_id=$(get_cfn_id_by_name "$cfn_name")

    if [ -n "$cfn_id" ] && [ "$cfn_id" != "null" ]; then
        echo "$cfn_id"
        return 0
    else
        return 1
    fi
}

# Helper function to get Memory Provider ID by name
get_memory_provider_id_by_name() {
    local mp_name=$1
    local response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/memory-providers" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        echo "$response" | jq -r ".providers[] | select(.memory_provider_name == \"${mp_name}\") | .memory_provider_id" 2>/dev/null | head -1
    else
        # Fallback without jq
        echo "$response" | grep -o '"memory_provider_id":"[^"]*"' | head -1 | cut -d'"' -f4
    fi
}

get_cfn() {
    clear
    print_header "Get CFN Details"
    echo ""
    print_info "Looking for CFN with name: Sample CFN Node"

    cfn_id=$(get_cfn_id_by_name "Sample CFN Node")

    if [ -z "$cfn_id" ] || [ "$cfn_id" = "null" ]; then
        print_error "CFN 'Sample CFN Node' not found"
        pause
        return
    fi

    print_info "Using CFN ID: $cfn_id"
    echo ""
    api_call GET "/cognitive-fabric-nodes/${cfn_id}" ""
    pause
}

heartbeat_cfn() {
    clear
    print_header "Send CFN Heartbeat"
    echo ""
    print_info "Looking for CFN with name: Sample CFN Node"

    cfn_id=$(get_cfn_id_by_name "Sample CFN Node")

    if [ -z "$cfn_id" ] || [ "$cfn_id" = "null" ]; then
        print_error "CFN 'Sample CFN Node' not found"
        pause
        return
    fi

    print_info "Using CFN ID: $cfn_id"
    echo ""
    api_call PUT "/cognitive-fabric-nodes/${cfn_id}/heartbeat" ""
    pause
}

disable_cfn() {
    clear
    print_header "Disable CFN"
    echo ""
    print_info "Looking for CFN with name: Sample CFN Node"

    cfn_id=$(get_cfn_id_by_name "Sample CFN Node")

    if [ -z "$cfn_id" ] || [ "$cfn_id" = "null" ]; then
        print_error "CFN 'Sample CFN Node' not found"
        pause
        return
    fi

    print_info "Using CFN ID: $cfn_id"
    echo ""
    api_call PATCH "/cognitive-fabric-nodes/${cfn_id}/disable" ""
    pause
}

delete_cfn() {
    clear
    print_header "Delete CFN"
    echo ""
    print_info "Looking for CFN with name: Sample CFN Node"

    cfn_id=$(get_cfn_id_by_name "Sample CFN Node")

    if [ -z "$cfn_id" ] || [ "$cfn_id" = "null" ]; then
        print_error "CFN 'Sample CFN Node' not found"
        pause
        return
    fi

    print_info "Using CFN ID: $cfn_id"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/cognitive-fabric-nodes/${cfn_id}" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Workspace Functions
workspace_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "        Workspace Management"
        print_header "=========================================="
        echo ""
        echo "1. Create Workspace"
        echo "2. List Workspaces"
        echo "3. Get Workspace Details"
        echo "4. Delete Workspace"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_workspace ;;
            2) list_workspaces ;;
            3) get_workspace ;;
            4) delete_workspace ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_workspace() {
    clear
    print_header "Create Workspace"
    echo ""

    # Check if CFN exists by name
    print_info "Checking if CFN 'Sample CFN Node' exists..."
    cfn_id=$(cfn_exists_by_name "Sample CFN Node")
    cfn_exists=$?

    if [ $cfn_exists -ne 0 ]; then
        print_error "CFN 'Sample CFN Node' not found!"
        echo ""
        read -p "Would you like to create it now? (yes/no): " create_cfn_answer

        if [ "$create_cfn_answer" = "yes" ]; then
            echo ""
            print_info "Creating CFN 'Sample CFN Node'..."

            # Temporarily disable exit-on-error for this call
            set +e
            cfn_response=$(api_call_silent POST "/cognitive-fabric-nodes" '{
  "cfn_name": "Sample CFN Node",
  "cfn_config": {
    "log_level": "info",
    "memory": "4GB"
  }
}')
            cfn_exit_code=$?
            set -e

            if [ $cfn_exit_code -ne 0 ]; then
                print_error "Failed to create CFN"
                pause
                return
            fi

            print_success "CFN created"
            if command -v jq &> /dev/null; then
                echo "$cfn_response" | jq '.'
                cfn_id=$(echo "$cfn_response" | jq -r '.cfn_id // empty' 2>/dev/null)
            else
                echo "$cfn_response"
                cfn_id=$(echo "$cfn_response" | grep -o '"cfn_id":"[^"]*"' | head -1 | cut -d'"' -f4)
            fi

            if [ -z "$cfn_id" ] || [ "$cfn_id" = "null" ]; then
                print_error "Failed to extract CFN ID from response"
                pause
                return
            fi
            echo ""
        else
            print_info "Cancelled - create a CFN first"
            pause
            return
        fi
    else
        print_success "CFN 'Sample CFN Node' found (ID: $cfn_id)"
    fi

    echo ""
    print_info "Using static values:"
    echo "  Workspace Name: Sample Workspace"
    echo "  Description: A sample workspace for testing"
    echo "  CFN ID: $cfn_id"
    echo ""
    print_info "Creating workspace..."
    api_call POST "/workspaces/create" "{
  \"name\": \"Sample Workspace\",
  \"description\": \"A sample workspace for testing\",
  \"cfn_id\": \"${cfn_id}\"
}"
    pause
}

list_workspaces() {
    clear
    print_header "List All Workspaces"
    echo ""
    api_call GET "/workspaces" ""
    pause
}

get_workspace() {
    clear
    print_header "Get Workspace Details"
    echo ""
    print_info "Fetching first available workspace..."
    echo ""

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    echo ""
    api_call GET "/workspaces/${ws_id}" ""
    pause
}

delete_workspace() {
    clear
    print_header "Delete Workspace"
    echo ""
    print_info "Fetching first available workspace..."
    echo ""

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/workspaces/${ws_id}" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Memory Provider Functions
memory_provider_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "     Memory Provider Management"
        print_header "=========================================="
        echo ""
        echo "1. Create Memory Provider"
        echo "2. List Memory Providers"
        echo "3. Get Memory Provider Details"
        echo "4. Delete Memory Provider"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_memory_provider ;;
            2) list_memory_providers ;;
            3) get_memory_provider ;;
            4) delete_memory_provider ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_memory_provider() {
    clear
    print_header "Create Memory Provider"
    echo ""
    print_info "Using static values:"
    echo "  Memory Provider Name: Sample Memory Provider"
    echo "  Provider Type: vector_store"
    echo "  Provider: ioc-memory-provider"
    echo "  Host: localhost"
    echo "  Port: 9003"
    echo ""
    print_info "Creating memory provider..."
    api_call POST "/memory-providers" '{
  "memory_provider_name": "Sample Memory Provider",
  "provider_type": "vector_store",
  "provider": "ioc-memory-provider",
  "config": {
    "host": "localhost",
    "port": 9003
  }
}'
    pause
}

list_memory_providers() {
    clear
    print_header "List All Memory Providers"
    echo ""
    api_call GET "/memory-providers" ""
    pause
}

get_memory_provider() {
    clear
    print_header "Get Memory Provider Details"
    echo ""
    print_info "Looking for Memory Provider with name: Sample Memory Provider"

    mp_id=$(get_memory_provider_id_by_name "Sample Memory Provider")

    if [ -z "$mp_id" ] || [ "$mp_id" = "null" ]; then
        print_error "Memory Provider 'Sample Memory Provider' not found"
        pause
        return
    fi

    print_info "Using Memory Provider ID: $mp_id"
    echo ""
    api_call GET "/memory-providers/${mp_id}" ""
    pause
}

delete_memory_provider() {
    clear
    print_header "Delete Memory Provider"
    echo ""
    print_info "Looking for Memory Provider with name: Sample Memory Provider"

    mp_id=$(get_memory_provider_id_by_name "Sample Memory Provider")

    if [ -z "$mp_id" ] || [ "$mp_id" = "null" ]; then
        print_error "Memory Provider 'Sample Memory Provider' not found"
        pause
        return
    fi

    print_info "Using Memory Provider ID: $mp_id"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/memory-providers/${mp_id}" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Cognitive Agent Functions
cognitive_agent_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "     Cognitive Agent Management"
        print_header "=========================================="
        echo ""
        echo "1. Create Cognitive Agent"
        echo "2. List Cognitive Agents"
        echo "3. Get Cognitive Agent Details"
        echo "4. Update Cognitive Agent"
        echo "5. Delete Cognitive Agent"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_cognitive_agent ;;
            2) list_cognitive_agents ;;
            3) get_cognitive_agent ;;
            4) update_cognitive_agent ;;
            5) delete_cognitive_agent ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_cognitive_agent() {
    clear
    print_header "Create Cognitive Agent"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found. Create a workspace first."
        pause
        return
    fi

    echo ""
    print_info "Using static values:"
    echo "  Workspace ID: $ws_id"
    echo "  Agent ID: sample-agent-001"
    echo "  Agent Name: Sample Cognitive Agent"
    echo "  Description: A sample cognitive agent for testing"
    echo ""
    print_info "Creating cognitive agent..."
    api_call POST "/workspaces/${ws_id}/cognitive-agents" '{
  "cognitive_agent_id": "sample-agent-001",
  "cognitive_agent_name": "Sample Cognitive Agent",
  "description": "A sample cognitive agent for testing",
  "config": {
    "capabilities": ["reasoning", "planning"],
    "priority": "high"
  }
}'
    pause
}

list_cognitive_agents() {
    clear
    print_header "List Cognitive Agents"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    echo ""
    api_call GET "/workspaces/${ws_id}/cognitive-agents" ""
    pause
}

get_cognitive_agent() {
    clear
    print_header "Get Cognitive Agent Details"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Agent ID: sample-agent-001"
    echo ""
    api_call GET "/workspaces/${ws_id}/cognitive-agents/sample-agent-001" ""
    pause
}

update_cognitive_agent() {
    clear
    print_header "Update Cognitive Agent"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Agent ID: sample-agent-001"
    echo ""
    print_info "Updating cognitive agent name..."
    api_call PATCH "/workspaces/${ws_id}/cognitive-agents/sample-agent-001" '{
  "cognitive_agent_name": "Updated Sample Agent",
  "description": "Updated description"
}'
    pause
}

delete_cognitive_agent() {
    clear
    print_header "Delete Cognitive Agent"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Agent ID: sample-agent-001"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/workspaces/${ws_id}/cognitive-agents/sample-agent-001" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Cognitive Engine Functions
cognitive_engine_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "     Cognitive Engine Management"
        print_header "=========================================="
        echo ""
        echo "1. Create Cognitive Engine"
        echo "2. List Cognitive Engines"
        echo "3. Get Cognitive Engine Details"
        echo "4. Delete Cognitive Engine"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_cognitive_engine ;;
            2) list_cognitive_engines ;;
            3) get_cognitive_engine ;;
            4) delete_cognitive_engine ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_cognitive_engine() {
    clear
    print_header "Create Cognitive Engine"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found. Create a workspace first."
        pause
        return
    fi

    echo ""
    print_info "Using static values:"
    echo "  Workspace ID: $ws_id"
    echo "  Engine ID: sample-engine-001"
    echo "  Engine Name: Sample Cognitive Engine"
    echo "  Model: claude-opus-4-6"
    echo "  Temperature: 0.7"
    echo "  Max Tokens: 4096"
    echo ""
    print_info "Creating cognitive engine..."
    api_call POST "/workspaces/${ws_id}/cognitive-engines" '{
  "cognitive_engine_id": "sample-engine-001",
  "cognitive_engine_name": "Sample Cognitive Engine",
  "config": {
    "model": "claude-opus-4-6",
    "temperature": 0.7,
    "max_tokens": 4096
  }
}'
    pause
}

list_cognitive_engines() {
    clear
    print_header "List Cognitive Engines"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    echo ""
    api_call GET "/workspaces/${ws_id}/cognitive-engines" ""
    pause
}

get_cognitive_engine() {
    clear
    print_header "Get Cognitive Engine Details"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Engine ID: sample-engine-001"
    echo ""
    api_call GET "/workspaces/${ws_id}/cognitive-engines/sample-engine-001" ""
    pause
}

delete_cognitive_engine() {
    clear
    print_header "Delete Cognitive Engine"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Engine ID: sample-engine-001"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/workspaces/${ws_id}/cognitive-engines/sample-engine-001" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Policy Functions
policy_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "         Policy Management"
        print_header "=========================================="
        echo ""
        echo "1. Create Policy"
        echo "2. List Policies"
        echo "3. Get Policy Details"
        echo "4. Update Policy"
        echo "5. Delete Policy"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_policy ;;
            2) list_policies ;;
            3) get_policy ;;
            4) update_policy ;;
            5) delete_policy ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_policy() {
    clear
    print_header "Create Policy"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found. Create a workspace first."
        pause
        return
    fi

    echo ""
    print_info "Using static values:"
    echo "  Workspace ID: $ws_id"
    echo "  Policy ID: sample-policy-001"
    echo "  Policy Name: Sample Policy"
    echo ""
    print_info "Creating policy..."
    api_call POST "/workspaces/${ws_id}/policies" '{
  "policy_id": "sample-policy-001",
  "policy_name": "Sample Policy",
  "config": {
    "rules": ["rule1", "rule2"],
    "enforcement_level": "strict"
  }
}'
    pause
}

list_policies() {
    clear
    print_header "List Policies"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    echo ""
    api_call GET "/workspaces/${ws_id}/policies" ""
    pause
}

get_policy() {
    clear
    print_header "Get Policy Details"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Policy ID: sample-policy-001"
    echo ""
    api_call GET "/workspaces/${ws_id}/policies/sample-policy-001" ""
    pause
}

update_policy() {
    clear
    print_header "Update Policy"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Policy ID: sample-policy-001"
    echo ""
    print_info "Updating policy..."
    api_call PATCH "/workspaces/${ws_id}/policies/sample-policy-001" '{
  "policy_name": "Updated Sample Policy",
  "config": {
    "rules": ["rule1", "rule2", "rule3"],
    "enforcement_level": "moderate"
  }
}'
    pause
}

delete_policy() {
    clear
    print_header "Delete Policy"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Using Policy ID: sample-policy-001"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/workspaces/${ws_id}/policies/sample-policy-001" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Multi-Agentic System Functions
mas_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "  Multi-Agentic System (MAS) Management"
        print_header "=========================================="
        echo ""
        echo "1. Create MAS"
        echo "2. List MAS"
        echo "3. Get MAS Details"
        echo "4. Delete MAS"
        echo "0. Back to Main Menu"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) create_mas ;;
            2) list_mas ;;
            3) get_mas ;;
            4) delete_mas ;;
            0) return ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

create_mas() {
    clear
    print_header "Create Multi-Agentic System"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found. Create a workspace first."
        pause
        return
    fi

    echo ""
    print_info "Using static values:"
    echo "  Workspace ID: $ws_id"
    echo "  MAS Name: Sample MAS"
    echo "  Description: A sample multi-agentic system"
    echo "  Agents: coordinator (claude-sonnet-4-5), executor (claude-haiku-4-5)"
    echo "  Collaboration Mode: hierarchical"
    echo ""
    print_info "Creating MAS..."
    api_call POST "/workspaces/${ws_id}/multi-agentic-systems" '{
  "name": "Sample MAS",
  "description": "A sample multi-agentic system",
  "agents": {
    "coordinator": {
      "type": "coordinator",
      "model": "claude-sonnet-4-5",
      "config": {
        "temperature": 0.5,
        "max_tokens": 2048
      }
    },
    "executor": {
      "type": "executor",
      "model": "claude-haiku-4-5",
      "config": {
        "temperature": 0.2,
        "max_tokens": 1024
      }
    }
  },
  "config": {
    "collaboration_mode": "hierarchical"
  }
}'
    pause
}

list_mas() {
    clear
    print_header "List Multi-Agentic Systems"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    echo ""
    api_call GET "/workspaces/${ws_id}/multi-agentic-systems" ""
    pause
}

get_mas() {
    clear
    print_header "Get MAS Details"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    ws_response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$ws_response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$ws_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Fetching first available MAS..."

    # Get list and extract first MAS ID
    mas_response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces/${ws_id}/multi-agentic-systems" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        mas_id=$(echo "$mas_response" | jq -r '.systems[0].id // empty' 2>/dev/null)
    else
        mas_id=$(echo "$mas_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$mas_id" ]; then
        print_error "No MAS found in workspace"
        pause
        return
    fi

    print_info "Using MAS ID: $mas_id"
    echo ""
    api_call GET "/workspaces/${ws_id}/multi-agentic-systems/${mas_id}" ""
    pause
}

delete_mas() {
    clear
    print_header "Delete Multi-Agentic System"
    echo ""
    print_info "Fetching first available workspace..."

    # Get list and extract first workspace ID
    ws_response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        ws_id=$(echo "$ws_response" | jq -r '.workspaces[0].id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$ws_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$ws_id" ]; then
        print_error "No workspaces found"
        pause
        return
    fi

    print_info "Using Workspace ID: $ws_id"
    print_info "Fetching first available MAS..."

    # Get list and extract first MAS ID
    mas_response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces/${ws_id}/multi-agentic-systems" -H "Content-Type: application/json")

    if command -v jq &> /dev/null; then
        mas_id=$(echo "$mas_response" | jq -r '.systems[0].id // empty' 2>/dev/null)
    else
        mas_id=$(echo "$mas_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    if [ -z "$mas_id" ]; then
        print_error "No MAS found in workspace"
        pause
        return
    fi

    print_info "Using MAS ID: $mas_id"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        echo ""
        api_call DELETE "/workspaces/${ws_id}/multi-agentic-systems/${mas_id}" ""
    else
        print_info "Cancelled"
    fi
    pause
}

# Quick Sample Data
quick_sample() {
    clear
    print_header "=========================================="
    print_header "       Quick Sample Data Setup"
    print_header "=========================================="
    echo ""
    print_info "This will create a complete sample setup:"
    echo "  - 1 CFN Node"
    echo "  - 1 Workspace"
    echo "  - 1 Memory Provider"
    echo "  - 1 Cognitive Engine"
    echo "  - 1 Cognitive Agent"
    echo "  - 1 Policy"
    echo "  - 1 Multi-Agentic System"
    echo ""
    read -p "Continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        print_info "Cancelled"
        pause
        return
    fi

    echo ""
    print_info "Creating CFN..."

    # Check if CFN already exists by name
    cfn_id=$(cfn_exists_by_name "Sample CFN Node")
    cfn_exists=$?

    if [ $cfn_exists -eq 0 ]; then
        print_success "CFN already exists (ID: $cfn_id)"
    else
        # Temporarily disable exit-on-error for this call
        set +e
        cfn_response=$(api_call_silent POST "/cognitive-fabric-nodes" '{
  "cfn_name": "Sample CFN Node",
  "cfn_config": {
    "log_level": "info",
    "memory": "4GB"
  }
}')
        cfn_exit_code=$?
        set -e

        if [ $cfn_exit_code -ne 0 ]; then
            print_error "Failed to create CFN"
            echo "$cfn_response"
            pause
            return
        fi

        print_success "CFN created"
        if command -v jq &> /dev/null; then
            echo "$cfn_response" | jq '.'
            cfn_id=$(echo "$cfn_response" | jq -r '.cfn_id // empty' 2>/dev/null)
        else
            echo "$cfn_response"
            cfn_id=$(echo "$cfn_response" | grep -o '"cfn_id":"[^"]*"' | head -1 | cut -d'"' -f4)
        fi

        if [ -z "$cfn_id" ] || [ "$cfn_id" = "null" ]; then
            print_error "Failed to extract CFN ID from response"
            pause
            return
        fi
    fi

    print_info "Using CFN ID: $cfn_id"

    echo ""
    print_info "Creating Workspace..."

    # Temporarily disable exit-on-error for this call
    set +e
    ws_response=$(api_call_silent POST "/workspaces/create" "{
  \"name\": \"Sample Workspace\",
  \"description\": \"A sample workspace\",
  \"cfn_id\": \"${cfn_id}\"
}")
    ws_exit_code=$?
    set -e

    if [ $ws_exit_code -ne 0 ]; then
        print_error "Failed to create workspace"
        echo "$ws_response"
        pause
        return
    fi

    # Display the response
    print_success "Workspace created"
    if command -v jq &> /dev/null; then
        echo "$ws_response" | jq '.'
    else
        echo "$ws_response"
    fi

    # Extract workspace_id using grep/sed if jq not available
    if command -v jq &> /dev/null; then
        ws_id=$(echo "$ws_response" | jq -r '.id // empty' 2>/dev/null)
    else
        ws_id=$(echo "$ws_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    fi

    # If workspace already exists (no ID in response), fetch it by listing
    if [ -z "$ws_id" ]; then
        print_info "Workspace already exists, fetching existing workspace..."
        ws_list_response=$(curl -s -X GET "${BASE_URL}${API_PREFIX}/workspaces" -H "Content-Type: application/json")

        if command -v jq &> /dev/null; then
            ws_id=$(echo "$ws_list_response" | jq -r '.workspaces[] | select(.name == "Sample Workspace") | .id' 2>/dev/null | head -1)
        else
            # Fallback: get first workspace ID
            ws_id=$(echo "$ws_list_response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        fi
    fi

    if [ -z "$ws_id" ] || [ "$ws_id" = "null" ]; then
        print_error "Failed to extract workspace ID. Response was:"
        echo "$ws_response"
        pause
        return
    fi

    print_success "Using Workspace ID: $ws_id"

    echo ""
    print_info "Sending heartbeat..."
    api_call PUT "/cognitive-fabric-nodes/${cfn_id}/heartbeat" "" || {
        print_error "Failed to send heartbeat, but continuing..."
    }

    echo ""
    print_info "Creating Memory Provider..."
    api_call POST "/memory-providers" '{
  "memory_provider_name": "Sample Memory Provider",
  "provider_type": "vector_store",
  "provider": "ioc-memory-provider",
  "config": {
    "host": "localhost",
    "port": 9003
  }
}' || {
        print_error "Failed to create memory provider, but continuing..."
    }

    echo ""
    print_info "Creating Cognitive Engine..."
    api_call POST "/workspaces/${ws_id}/cognitive-engines" '{
  "cognitive_engine_id": "sample-engine-001",
  "cognitive_engine_name": "Sample Engine",
  "config": {
    "model": "claude-opus-4-6",
    "temperature": 0.7
  }
}' || {
        print_error "Failed to create cognitive engine, but continuing..."
    }

    echo ""
    print_info "Creating Cognitive Agent..."
    api_call POST "/workspaces/${ws_id}/cognitive-agents" '{
  "cognitive_agent_id": "sample-agent-001",
  "cognitive_agent_name": "Sample Agent",
  "description": "A sample cognitive agent",
  "config": {
    "capabilities": ["reasoning", "planning"]
  }
}' || {
        print_error "Failed to create cognitive agent, but continuing..."
    }

    echo ""
    print_info "Creating Policy..."
    api_call POST "/workspaces/${ws_id}/policies" '{
  "policy_id": "sample-policy-001",
  "policy_name": "Sample Policy",
  "config": {
    "rules": ["rule1", "rule2"],
    "enforcement_level": "strict"
  }
}' || {
        print_error "Failed to create policy, but continuing..."
    }

    echo ""
    print_info "Creating Multi-Agentic System..."
    api_call POST "/workspaces/${ws_id}/multi-agentic-systems" '{
  "name": "Sample MAS",
  "description": "A sample multi-agentic system",
  "agents": {
    "coordinator": {
      "type": "coordinator",
      "model": "claude-sonnet-4-5",
      "config": {"temperature": 0.5}
    }
  },
  "config": {}
}' || {
        print_error "Failed to create MAS, but continuing..."
    }

    echo ""
    print_success "Quick sample data setup completed!"
    print_info "Workspace ID: ${ws_id}"
    pause
}

# Main Menu
main_menu() {
    while true; do
        clear
        print_header "=========================================="
        print_header "  IOC CFN Management - Interactive Menu"
        print_header "=========================================="
        echo ""
        print_info "Base URL: $BASE_URL"
        echo ""
        echo "1. Cognitive Fabric Node (CFN)"
        echo "2. Memory Providers"
        echo "3. Workspaces"
        echo "4. Multi-Agentic Systems (MAS)"
        echo "5. Cognitive Agents"
        echo "6. Cognitive Engines"
        echo "7. Policies"
        echo ""
        echo "9. Quick Sample Data Setup"
        echo "0. Exit"
        echo ""
        read -p "Select option: " choice

        case $choice in
            1) cfn_menu ;;
            2) memory_provider_menu ;;
            3) workspace_menu ;;
            4) mas_menu ;;
            5) cognitive_agent_menu ;;
            6) cognitive_engine_menu ;;
            7) policy_menu ;;
            9) quick_sample ;;
            0)
                clear
                print_success "Goodbye!"
                exit 0
                ;;
            *) print_error "Invalid option" ; pause ;;
        esac
    done
}

# Start the application
main_menu
