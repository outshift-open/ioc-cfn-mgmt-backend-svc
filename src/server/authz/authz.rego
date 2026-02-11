package authz

import rego.v1
import data.authz.roles.admin
import data.authz.roles.viewer
import data.authz.roles.guest
import data.authz.roles.super_admin

# Default deny
default allow := false

# Delegate to role-specific policies
# Super admin checked first (has unrestricted access)
allow if {
	super_admin.allow
}

allow if {
	admin.allow
}

allow if {
	viewer.allow
}

allow if {
	guest.allow
}
