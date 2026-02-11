package authz.operations.cognitive_fabric_node

import rego.v1

# Admin operations - full access to create, update, enable, disable, delete, heartbeat, list, get CFN nodes
admin := [
	"register_cognitive_fabric_node",
	"create_cognitive_fabric_node",
	"update_cognitive_fabric_node",
	"enable_cognitive_fabric_node",
	"disable_cognitive_fabric_node",
	"deregister_cognitive_fabric_node",
	"delete_cognitive_fabric_node",
	"heartbeat_cognitive_fabric_node",
	"get_cognitive_fabric_node",
	"list_cognitive_fabric_node",
]

# Viewer operations - read-only access (list and get)
viewer := [
	"get_cognitive_fabric_node",
	"list_cognitive_fabric_node",
]

# Guest operations - no access
guest := []
