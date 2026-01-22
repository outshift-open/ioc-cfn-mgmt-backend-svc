package authz.operations.api_keys

import rego.v1

# Admin operations - full access
admin := [
	"get_api_key",
	"create_api_key",
	"delete_api_key",
]

# Viewer operations - read-only
viewer := [
	"get_api_key",
]

# Guest operations - no access
guest := []
