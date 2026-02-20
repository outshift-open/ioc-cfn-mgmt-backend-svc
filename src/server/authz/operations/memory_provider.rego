package authz.operations.memory_provider

import rego.v1

# Admin permissions - full access to create, read, update, delete, and list memory providers
admin := [
	"create_memory_provider",
	"read_memory_provider",
	"update_memory_provider",
	"delete_memory_provider",
	"list_memory_provider",
]

# Viewer permissions - read-only access
viewer := [
	"read_memory_provider",
	"list_memory_provider",
]

# Guest permissions - no access
guest := []
