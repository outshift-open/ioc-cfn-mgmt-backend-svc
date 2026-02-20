package authz.roles.admin

import rego.v1
import data.authz.operations.workspaces
import data.authz.operations.users
import data.authz.operations.api_keys
import data.authz.operations.softwares
import data.authz.operations.iam
import data.authz.operations.cognitive_fabric_node
import data.authz.operations.cognitive_engine
import data.authz.operations.cognitive_agent
import data.authz.operations.memory_provider
import data.authz.operations.multi_agentic_system
import data.authz.operations.policy

# Admin role permissions - full access to all operations
allow if {
	input.user.role == "admin"
	input.resource == "workspace"
	input.operation in workspaces.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "user"
	input.operation in users.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "api_key"
	input.operation in api_keys.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "software"
	input.operation in softwares.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "iam"
	input.operation in iam.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "cognitive_fabric_node"
	input.operation in cognitive_fabric_node.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "cognitive_engine"
	input.operation in cognitive_engine.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "cognitive_agent"
	input.operation in cognitive_agent.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "memory_provider"
	input.operation in memory_provider.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "multi_agentic_system"
	input.operation in multi_agentic_system.admin
}

allow if {
	input.user.role == "admin"
	input.resource == "policy"
	input.operation in policy.admin
}
