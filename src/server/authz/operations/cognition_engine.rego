package authz.operations.cognition_engine

import rego.v1

# Admin permissions - full access to create, read, update, delete, and list cognition engines
admin := [
	"create_cognition_engine",
	"get_cognition_engine",
	"read_cognition_engine",
	"update_cognition_engine",
	"delete_cognition_engine",
	"list_cognition_engine",
]

# Viewer permissions - read-only access
viewer := [
	"get_cognition_engine",
	"read_cognition_engine",
	"list_cognition_engine",
]

# Guest permissions - no access
guest := []
