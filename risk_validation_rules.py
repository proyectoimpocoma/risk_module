import re


PLATE_REGEX = re.compile(r"^[A-Z]{3}[0-9]{2,3}$")
SEMI_TRAILER_PLATE_REGEX = re.compile(r"^[A-Z][0-9]{5}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
CC_REGEX = re.compile(r"^[0-9]{6,10}$")
NIT_REGEX = re.compile(r"^[0-9]{9}(-[0-9])?$")


def phone_digits(phone):
    return re.sub(r"\D", "", phone or "")


def is_valid_mobile_phone(phone):
    if not phone:
        return True
    digits = phone_digits(phone)
    return len(digits) == 10 and digits.startswith("3")


def is_valid_phone(phone):
    if not phone:
        return True
    digits = phone_digits(phone)
    return len(digits) == 7 or (len(digits) == 10 and digits[0] in ("3", "6"))
