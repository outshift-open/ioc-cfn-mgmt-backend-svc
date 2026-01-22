package authz.roles.admin

import rego.v1
import data.authz.operations.workspaces
import data.authz.operations.users
import data.authz.operations.api_keys
import data.authz.operations.softwares
import data.authz.operations.iam

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
