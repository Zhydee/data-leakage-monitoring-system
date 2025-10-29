DATA_TYPE_REGEX_MAP = {
    "email": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    "phone": r"^\+?[\d\s\-]{7,15}$",
    "username": r"^[a-zA-Z0-9_-]{3,16}$",
    "credit_card": r"^\d{13,19}$",
    "ic": r"^\d{6}-?\d{2}-?\d{4}$",
    "github_repo": r"^https?://github\.com/[\w.-]+/[\w.-]+/?$",
    "full_name": r"^[A-Za-z\s.'@]+$",
    "password": r".{6,}"
}
