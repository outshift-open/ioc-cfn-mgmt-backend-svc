# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# SPDX-License-Identifier: Apache-2.0

from enum import Enum

from server.mock_services import verify_db, verify_foo


class HealthState(Enum):
    UP = 0
    UNKNOWN = 1
    DEGRADED = 2
    DOWN = 3


class HealthCheckType(Enum):
    SELF = 0
    UNKNOWN = 1
    DEPENDENCY_OPTIONAL = 2
    DEPENDENCY_CRITICAL = 3


def check_db():
    """Verify successful queries on dependent database"""
    is_ok = verify_db()
    return is_ok


def check_foo():
    """Verify dependency service Foo is reachable"""
    is_ok = verify_foo()
    return is_ok


def check_self():
    """Define service-specific logic for calculating this service's
    health state.
    """
    # check db (mocked)
    db_ok = check_db()
    # check foo (mocked)
    foo_ok = check_foo()

    if db_ok and foo_ok:
        service_state = HealthState.UP
    elif db_ok and not foo_ok:
        # foo is an optional dependency
        service_state = HealthState.DEGRADED
    elif not db_ok:
        # db is a critical service
        service_state = HealthState.DOWN
    else:
        service_state = HealthState.UNKNOWN

    return service_state
