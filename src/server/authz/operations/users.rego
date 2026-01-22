package authz.operations.users

import rego.v1

# Admin operations - full access
admin := [
	"get_user",
	"create_user",
	"update_user",
	"delete_user",
]

# Viewer operations - read-only
viewer := [
	"get_user",
]

# Guest operations - no access
guest := []
