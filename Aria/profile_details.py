"""Formatting helpers for public Discord profile details."""


def format_public_profile_details(profile_data: dict) -> list[str]:
    user_profile = profile_data.get("user_profile") if isinstance(profile_data, dict) else None
    if not isinstance(user_profile, dict):
        return []

    details = []
    bio = " ".join(str(user_profile.get("bio") or "").split())
    pronouns = " ".join(str(user_profile.get("pronouns") or "").split())
    if bio:
        details.append(f"Bio: {bio[:190]}")
    if pronouns:
        details.append(f"Pronouns: {pronouns[:40]}")

    accent_color = user_profile.get("accent_color")
    if isinstance(accent_color, int) and not isinstance(accent_color, bool) and 0 <= accent_color <= 0xFFFFFF:
        details.append(f"Accent: #{accent_color:06X}")
    return details