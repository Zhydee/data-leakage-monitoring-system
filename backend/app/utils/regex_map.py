DATA_TYPE_REGEX_MAP = {
    "email": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    "phone": r"^(01)[0-9]{8,9}$",
    "username": r"^[a-zA-Z0-9_.-]{3,30}$",
    "ic": r"^\d{6}-\d{2}-\d{4}$",
    "credit_card": r"^\d{16}$",
    "api_key": r"^[a-zA-Z0-9]{20,40}$"
}
