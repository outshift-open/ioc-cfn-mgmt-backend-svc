package authz.operations.cognition_fabric_node

import rego.v1

# Admin operations - full access to create, update, enable, disable, delete, heartbeat, list, get CFN nodes
admin := [
	"register_cognition_fabric_node",
	"create_cognition_fabric_node",
	"update_cognition_fabric_node",
	"enable_cognition_fabric_node",
	"disable_cognition_fabric_node",
	"deregister_cognition_fabric_node",
	"delete_cognition_fabric_node",
	"heartbeat_cognition_fabric_node",
	"get_cognition_fabric_node",
	"list_cognition_fabric_node",
]

# Viewer operations - read-only access (list and get)
viewer := [
	"get_cognition_fabric_node",
	"list_cognition_fabric_node",
]

# Guest operations - no access
guest := []
