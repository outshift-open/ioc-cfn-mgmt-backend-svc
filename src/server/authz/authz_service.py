"""Authorization service for evaluating Rego policies."""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, status
from regopy import Input, Interpreter

# Get logger instance (logging is setup in main.py)
logger = logging.getLogger(__name__)


class AuthzService:
    def __init__(self) -> None:
        self.logger = logger
        self._authz_dir = Path(__file__).parent
        self._interpreter = Interpreter()
        self._interpreter_lock = threading.Lock()  # Thread-safety for regopy (Python-Go bridge)
        self._load_policies()

    def _load_policies(self) -> None:
        """Load all Rego policy files into the interpreter."""
        # Load main authz policy
        self._load_rego_file(self._authz_dir / "authz.rego")

        # Load role policies
        roles_dir = self._authz_dir / "roles"
        if roles_dir.exists():
            for rego_file in roles_dir.glob("*.rego"):
                if not rego_file.name.endswith("_test.rego"):
                    self._load_rego_file(rego_file)

        # Load operation policies
        operations_dir = self._authz_dir / "operations"
        if operations_dir.exists():
            for rego_file in operations_dir.glob("*.rego"):
                if not rego_file.name.endswith("_test.rego"):
                    self._load_rego_file(rego_file)

        self.logger.info("AuthzService initialized with Rego policy evaluation")

    def _load_rego_file(self, rego_file: Path) -> None:
        """Load a single Rego file into the interpreter."""
        try:
            rego_content = rego_file.read_text()
            self._interpreter.add_module(rego_file.name, rego_content)
            self.logger.debug("Loaded Rego policy: %s", rego_file.name)
        except Exception as e:
            self.logger.error("Error loading Rego file %s: %s", rego_file, e)
            raise

    def _evaluate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the input data against the loaded Rego policy.

        Args:
            input_data (Dict[str, Any]): The input data to evaluate.

        Returns:
            Dict[str, Any]: The result of the policy evaluation.
        """
        self.logger.debug("Evaluating authorization policy with input: %s", input_data)

        # Lock to prevent concurrent access to regopy interpreter (prevents segfaults)
        with self._interpreter_lock:
            self._interpreter.set_input(Input(input_data))
            result = self._interpreter.query("data.authz.allow")

        self.logger.debug("Authorization policy evaluation result: %s", result)

        # Parse the result from JSON string representation
        # When no rules match, regopy returns "undefined" which is not valid JSON
        result_str = str(result)
        if result_str == "undefined":
            return {"allow": False}

        result_json = json.loads(result_str)
        expressions = result_json.get("expressions", [])
        allow = expressions[0] if expressions else False
        return {"allow": allow}

    def check_permission(self, user: Dict[str, Any], action: str, resource: str) -> bool:
        """Check if a user has permission to perform an action on a resource.

        Args:
            user (Dict[str, Any]): The user information including role.
            action (str): The action to be performed (e.g., 'create', 'get', 'delete').
            resource (str): The resource on which the action is performed (singular, e.g., 'user', 'workspace').
        Returns:
            bool: True if the user has permission, False otherwise.
        """
        operation = f"{action}_{resource}"
        input_data = {"user": user, "operation": operation, "resource": resource}
        result = self._evaluate(input_data)
        return result.get("allow", False)

    def require_permission(self, user: Dict[str, Any], action: str, resource: str, detail: str | None = None) -> None:
        """Require permission to perform an action, raising HTTPException if denied.

        Args:
            user (Dict[str, Any]): The user information including role.
            action (str): The action to be performed (e.g., 'create', 'get', 'delete').
            resource (str): The resource on which the action is performed (singular, e.g., 'user', 'workspace').
            detail (str | None): Custom error message. If None, a default message is generated.

        Raises:
            HTTPException: 403 Forbidden if the user lacks permission.
        """
        if not self.check_permission(user=user, action=action, resource=resource):
            error_detail = detail or f"You don't have permission to {action} {resource}"
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_detail)
        return


# Create a singleton instance for the application
authz_service = AuthzService()
