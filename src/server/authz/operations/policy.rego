package authz.operations.policy

import rego.v1

# Admin permissions - full access to create, read, update, delete, and list policies
admin := [
	"create_policy",
	"get_policy",
	"read_policy",
	"update_policy",
	"delete_policy",
	"list_policy",
]

# Viewer permissions - read-only access
viewer := [
	"get_policy",
	"read_policy",
	"list_policy",
]

# Guest permissions - no access
guest := []
