package authz.roles.viewer

import rego.v1
import data.authz.operations.workspaces
import data.authz.operations.users
import data.authz.operations.api_keys
import data.authz.operations.softwares

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
