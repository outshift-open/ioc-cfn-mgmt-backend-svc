package authz.operations.cognitive_engine

import rego.v1

# Admin permissions - full access to create, read, update, delete, and list cognitive engines
admin := [
	"create_cognitive_engine",
	"get_cognitive_engine",
	"read_cognitive_engine",
	"update_cognitive_engine",
	"delete_cognitive_engine",
	"list_cognitive_engine",
]

# Viewer permissions - read-only access
viewer := [
	"get_cognitive_engine",
	"read_cognitive_engine",
	"list_cognitive_engine",
]

# Guest permissions - no access
guest := []
