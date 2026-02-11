package authz.operations.multi_agentic_system

import rego.v1

# Admin operations - full access to create, update, delete, list, get MAS
admin := [
	"create_multi_agentic_system",
	"update_multi_agentic_system",
	"delete_multi_agentic_system",
	"get_multi_agentic_system",
	"list_multi_agentic_system",
]

# Viewer operations - read-only access (list and get)
viewer := [
	"get_multi_agentic_system",
	"list_multi_agentic_system",
]

# Guest operations - no access
guest := []
