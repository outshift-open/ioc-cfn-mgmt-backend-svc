"""Policy service - Business logic for Policy operations"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from server.database.relational_db.db import RelationalDB
from server.database.relational_db.models.policies import Policy as PolicyModel
from server.schemas.policies import (
    PolicyCreate,
    PolicyDetail,
    PolicyList,
    PolicyListItem,
    PolicyUpdate,
)
from server.utils import generate_uuid


class PolicyService:
    """Service layer for Policy business logic"""

    def create(self, workspace_id: str, policy_data: PolicyCreate, user_id: str) -> PolicyDetail:
        """
        Create a new Policy

        Args:
            workspace_id: Workspace identifier
            policy_data: Policy creation data
            user_id: ID of the user creating the policy

        Returns:
            PolicyDetail with the created policy

        Raises:
            HTTPException: If policy with same ID already exists or creation fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Check if policy with same ID already exists (globally unique)
                existing_policy = (
                    session.query(PolicyModel)
                    .filter(
                        PolicyModel.policy_id == policy_data.policy_id,
                        PolicyModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if existing_policy:
                    if existing_policy.workspace_id == workspace_id:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(f"Policy with ID '{policy_data.policy_id}' " f"already exists in this workspace"),
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                f"Policy with ID '{policy_data.policy_id}' "
                                f"already exists in another workspace (globally unique constraint)"
                            ),
                        )

                # Create new policy
                new_policy = PolicyModel(
                    id=generate_uuid(),
                    policy_id=policy_data.policy_id,
                    workspace_id=workspace_id,
                    policy_name=policy_data.policy_name,
                    config=policy_data.config,
                    enabled=True,
                    created_by=user_id,
                )

                session.add(new_policy)
                session.commit()
                session.refresh(new_policy)

                return PolicyDetail(
                    policy_id=new_policy.policy_id,
                    workspace_id=new_policy.workspace_id,
                    policy_name=new_policy.policy_name,
                    config=new_policy.config,
                    enabled=new_policy.enabled,
                    created_at=new_policy.created_at,
                    updated_at=new_policy.updated_at,
                    created_by=new_policy.created_by,
                    updated_by=new_policy.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create policy: {str(e)}",
            )

    def get(self, workspace_id: str, policy_id: str) -> PolicyDetail:
        """
        Get a specific Policy by ID

        Args:
            workspace_id: Workspace identifier
            policy_id: ID of the policy

        Returns:
            PolicyDetail with the policy details

        Raises:
            HTTPException: If policy not found
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                policy = (
                    session.query(PolicyModel)
                    .filter(
                        PolicyModel.workspace_id == workspace_id,
                        PolicyModel.policy_id == policy_id,
                        PolicyModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not policy:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Policy with ID '{policy_id}' not found in this workspace",
                    )

                return PolicyDetail(
                    policy_id=policy.policy_id,
                    workspace_id=policy.workspace_id,
                    policy_name=policy.policy_name,
                    config=policy.config,
                    enabled=policy.enabled,
                    created_at=policy.created_at,
                    updated_at=policy.updated_at,
                    created_by=policy.created_by,
                    updated_by=policy.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get policy: {str(e)}",
            )

    def list(self, workspace_id: str) -> PolicyList:
        """
        List all Policies in workspace

        Args:
            workspace_id: Workspace identifier

        Returns:
            PolicyList with policies and total count
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                # Query all enabled policies in workspace
                policies = (
                    session.query(PolicyModel)
                    .filter(
                        PolicyModel.workspace_id == workspace_id,
                        PolicyModel.deleted_at.is_(None),
                        PolicyModel.enabled.is_(True),
                    )
                    .all()
                )

                policy_list = [
                    PolicyListItem(
                        policy_id=policy.policy_id,
                        workspace_id=policy.workspace_id,
                        policy_name=policy.policy_name,
                        config=policy.config,
                        enabled=policy.enabled,
                        created_at=policy.created_at.isoformat() if policy.created_at else None,
                    )
                    for policy in policies
                ]

                return PolicyList(policies=policy_list, total=len(policy_list))

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list policies: {str(e)}",
            )

    def update(self, workspace_id: str, policy_id: str, update_data: PolicyUpdate, user_id: str) -> PolicyDetail:
        """
        Update a Policy

        Args:
            workspace_id: Workspace identifier
            policy_id: ID of the policy to update
            update_data: Policy update data
            user_id: ID of the user updating the policy

        Returns:
            PolicyDetail with the updated policy

        Raises:
            HTTPException: If policy not found or update fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                policy = (
                    session.query(PolicyModel)
                    .filter(
                        PolicyModel.workspace_id == workspace_id,
                        PolicyModel.policy_id == policy_id,
                        PolicyModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not policy:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Policy with ID '{policy_id}' not found in this workspace",
                    )

                # Update fields if provided
                if update_data.policy_name is not None:
                    policy.policy_name = update_data.policy_name
                if update_data.config is not None:
                    policy.config = update_data.config
                if update_data.enabled is not None:
                    policy.enabled = update_data.enabled

                policy.updated_by = user_id
                policy.updated_at = datetime.now(timezone.utc)

                session.commit()
                session.refresh(policy)

                return PolicyDetail(
                    policy_id=policy.policy_id,
                    workspace_id=policy.workspace_id,
                    policy_name=policy.policy_name,
                    config=policy.config,
                    enabled=policy.enabled,
                    created_at=policy.created_at,
                    updated_at=policy.updated_at,
                    created_by=policy.created_by,
                    updated_by=policy.updated_by,
                )

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update policy: {str(e)}",
            )

    def delete(self, workspace_id: str, policy_id: str, user_id: str) -> dict:
        """
        Soft delete a Policy

        Args:
            workspace_id: Workspace identifier
            policy_id: ID of the policy to delete
            user_id: ID of the user deleting the policy

        Returns:
            Dict with success message

        Raises:
            HTTPException: If policy not found or deletion fails
        """
        try:
            db = RelationalDB()
            session = db.get_session()

            try:
                policy = (
                    session.query(PolicyModel)
                    .filter(
                        PolicyModel.workspace_id == workspace_id,
                        PolicyModel.policy_id == policy_id,
                        PolicyModel.deleted_at.is_(None),
                    )
                    .first()
                )

                if not policy:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Policy with ID '{policy_id}' not found in this workspace",
                    )

                # Soft delete by setting deleted_at timestamp
                policy.deleted_at = datetime.now(timezone.utc)
                policy.updated_by = user_id
                policy.updated_at = datetime.now(timezone.utc)

                session.commit()

                return {
                    "message": f"Policy '{policy_id}' deleted successfully",
                    "policy_id": policy_id,
                }

            finally:
                session.close()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete policy: {str(e)}",
            )


# Singleton instance
policy_service = PolicyService()
