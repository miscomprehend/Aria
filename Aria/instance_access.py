def instance_owner_ids(
    hosted_mode: bool,
    instance_owner_id: str | None,
    token_user_id: str | None,
    master_owner_ids: set[str],
) -> set[str]:
    """Return controller IDs scoped to a main or hosted bot instance."""
    if hosted_mode:
        candidates = (instance_owner_id, token_user_id)
    else:
        candidates = (*master_owner_ids, instance_owner_id, token_user_id)

    return {str(user_id).strip() for user_id in candidates if str(user_id or "").strip()}
