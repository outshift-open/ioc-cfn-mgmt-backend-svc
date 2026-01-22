package authz.operations.softwares

import rego.v1

# Admin operations - full access
admin := [
	"get_software",
	"create_software",
	"update_software",
	"delete_software",
]

# Viewer operations - read-only
viewer := [
	"get_software",
]

# Guest operations - no access
guest := []
