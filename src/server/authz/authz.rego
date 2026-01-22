package authz

import rego.v1
import data.authz.roles.admin
import data.authz.roles.viewer
import data.authz.roles.guest

# Default deny
default allow := false

# Delegate to role-specific policies
allow if {
	admin.allow
}

allow if {
	viewer.allow
}

allow if {
	guest.allow
}
