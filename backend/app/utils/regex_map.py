DATA_TYPE_REGEX_MAP = {
    "email": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    "phone": r"^\+?[\d\s\-]{7,15}$",
    "username": r"^[a-zA-Z0-9_-]{3,16}$",
    "domain": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "ip": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$",
    "credit_card": r"^\d{13,19}$",
    "ic": r"^\d{6}-\d{2}-\d{4}$",
    "api_key": r"^[A-Za-z0-9+/=]{20,}$",
    "github_url": r"^https:\/\/github\.com\/[\w.-]+\/[\w.-]+$",
    "password": r".{6,}"
}
