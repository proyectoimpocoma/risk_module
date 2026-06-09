import re

from odoo import api, models


class RiskSubmissionFormatting(models.Model):
    _inherit = "risk.module"

    def _format_co_phone(self, phone):
        """Formatea un numero de telefono segun el estandar colombiano."""
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10 and digits.startswith("3"):
            return f"{digits[0:3]} {digits[3:6]} {digits[6:10]}"
        if len(digits) == 10 and digits.startswith("6"):
            return f"({digits[0:3]}) {digits[3:6]} {digits[6:10]}"
        if len(digits) == 7:
            return f"{digits[0:3]} {digits[3:7]}"
        return phone

    @staticmethod
    def _phone_digits(phone):
        return re.sub(r"\D", "", phone or "")

    @classmethod
    def _is_valid_mobile_phone(cls, phone):
        if not phone:
            return True
        digits = cls._phone_digits(phone)
        return len(digits) == 10 and digits.startswith("3")

    @classmethod
    def _is_valid_phone(cls, phone):
        if not phone:
            return True
        digits = cls._phone_digits(phone)
        return len(digits) == 7 or (len(digits) == 10 and digits[0] in ("3", "6"))

    @staticmethod
    def _normalize_city(city):
        """Retorna la ciudad en formato Title Case."""
        return city.strip().title() if city and city.strip() else False

    @api.onchange("owner_city")
    def _onchange_owner_city(self):
        """Normaliza la ciudad del propietario a Title Case en tiempo real."""
        if self.owner_city:
            self.owner_city = self._normalize_city(self.owner_city)

    @staticmethod
    def _normalize_plate(plate):
        """Retorna la placa en mayusculas sin espacios, o False si esta vacia."""
        return plate.strip().upper() if plate and plate.strip() else False
