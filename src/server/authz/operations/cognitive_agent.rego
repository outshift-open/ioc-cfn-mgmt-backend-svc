package authz.operations.cognitive_agent

import rego.v1

# Admin permissions - full access to create, read, update, delete, and list cognitive agents
admin := [
	"create_cognitive_agent",
	"get_cognitive_agent",
	"read_cognitive_agent",
	"update_cognitive_agent",
	"delete_cognitive_agent",
	"list_cognitive_agent",
]

# Viewer permissions - read-only access
viewer := [
	"get_cognitive_agent",
	"read_cognitive_agent",
	"list_cognitive_agent",
]

# Guest permissions - no access
guest := []
