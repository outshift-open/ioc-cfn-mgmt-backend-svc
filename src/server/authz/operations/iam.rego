package authz.operations.iam

import rego.v1

# Admin operations - full access
admin := ["get_roles_iam"]

# Viewer operations - no access
viewer := []

# Guest operations - no access
guest := []
