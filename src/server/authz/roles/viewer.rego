package authz.roles.viewer

import rego.v1
import data.authz.operations.workspaces
import data.authz.operations.users
import data.authz.operations.api_keys
import data.authz.operations.softwares
import data.authz.operations.cognitive_fabric_node
import data.authz.operations.cognitive_engine
import data.authz.operations.cognitive_agent
import data.authz.operations.memory_provider
import data.authz.operations.multi_agentic_system
import data.authz.operations.policy

# Viewer role permissions - read-only operations
allow if {
	input.user.role == "viewer"
	input.resource == "workspace"
	input.operation in workspaces.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "user"
	input.operation in users.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "api_key"
	input.operation in api_keys.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "software"
	input.operation in softwares.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "cognitive_fabric_node"
	input.operation in cognitive_fabric_node.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "cognitive_engine"
	input.operation in cognitive_engine.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "cognitive_agent"
	input.operation in cognitive_agent.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "memory_provider"
	input.operation in memory_provider.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "multi_agentic_system"
	input.operation in multi_agentic_system.viewer
}

allow if {
	input.user.role == "viewer"
	input.resource == "policy"
	input.operation in policy.viewer
}
