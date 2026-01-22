package authz.operations.workspaces

import rego.v1

# Admin operations - full access
admin := [
	"get_workspace",
	"create_workspace",
	"update_workspace",
	"delete_workspace",
]

# Viewer operations - read-only
viewer := [
	"get_workspace",
]

# Guest operations - no access
guest := []
