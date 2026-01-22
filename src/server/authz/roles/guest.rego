package authz.roles.guest

import rego.v1

# Guest role permissions - no permissions allowed
# Guests cannot perform any operations in the system
default allow := false
