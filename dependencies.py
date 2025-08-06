#!/usr/bin/env python3

import valkey
from valkey.asyncio import Valkey as AsyncValkey
from ollama import AsyncClient
from config import settings
from utils.db.user_db import UserGroup, User
from fastapi import Depends
from routers.auth import get_current_active_user

# Initialize clients once and reuse them
ollama_client = AsyncClient(host=settings.OLLAMA_HOST)
valkey_client = AsyncValkey(
    host=settings.VALKEY_HOST, port=settings.VALKEY_PORT, db=0, decode_responses=True
)


# Dependency provider functions
def get_valkey_client():
    return valkey_client


def get_ollama_client():
    return AsyncClient(host=settings.OLLAMA_HOST)    

llm_client=get_ollama_client()
valkey_client=get_valkey_client()
def require_user_group(required_groups: list[UserGroup]):
    """
    A dependency factory that creates a dependency to check for specific user groups.
    """

    async def get_current_user_with_group_check(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.user_group not in required_groups:
            logger.warning(
                f"User {current_user.email} with group '{current_user.user_group.value}'"
                f" tried to access a resource restricted to {required_groups}."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return get_current_user_with_group_check


# Create specific dependencies for convenience
require_managerial_user = require_user_group([UserGroup.MANAGERIAL, UserGroup.ADMIN])
require_staff_user = require_user_group(
    [UserGroup.STAFF, UserGroup.MANAGERIAL, UserGroup.ADMIN]
)
require_admin_only = require_user_group([UserGroup.ADMIN])
