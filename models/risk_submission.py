import re
import uuid

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RiskSubmission(models.Model):
    _name = "risk.module"
    _description = "Solicitud de habilitacion de terceros"
    _rec_name = "vehicle_plate"
    _order = "create_date desc"

    # Regex placa colombiana: 3 letras + 2 dígitos (moto) o 3 dígitos (vehiculo/carga)
    _PLATE_REGEX = re.compile(r'^[A-Z]{3}[0-9]{2,3}$')
    # Regex email basico RFC 5322 simplificado
    _EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

    name = fields.Char(string="Referencia")
    state = fields.Selection([
        ("draft", "Borrador"),
        ("submitted", "Enviado"),
    ], string="Estado", default="draft", required=True)
    access_token = fields.Char(string="Token publico", default=lambda self: uuid.uuid4().hex, copy=False)
    form_date = fields.Date(string="Fecha", default=fields.Date.context_today)
    vehicle_plate = fields.Char(string="Placa", required=True)
    semi_trailer_plate = fields.Char(string="Semi/Remolque")
    satellite_company = fields.Char(string="Empresa satelital")
    satellite_user = fields.Char(string="Usuario satelital")
    satellite_password = fields.Char(string="Clave satelital")
    owner_name = fields.Char(string="Nombres y apellidos / Empresa")
    owner_document_type = fields.Selection([
        ("cc", "CC"),
        ("nit", "Nit"),
    ], string="Tipo de documento")
    owner_document_number = fields.Char(string="Numero de documento")
    owner_address = fields.Char(string="Direccion")
    owner_neighborhood = fields.Char(string="Barrio")
    owner_city = fields.Char(string="Ciudad")
    owner_phone = fields.Char(string="Celular notificaciones")
    owner_email = fields.Char(string="Correo facturacion y notificaciones")
    advance_payment_to = fields.Selection([
        ("driver", "Conductor"),
        ("owner", "Propietario"),
    ], string="Entrega y pago de anticipos a")
    same_owner_on_license = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Corresponde al propietario en licencia")
    registered_owner_document_type = fields.Selection([
        ("cc", "CC"),
        ("nit", "Nit"),
    ], string="Tipo documento propietario")
    registered_owner_document_number = fields.Char(string="Numero documento propietario")
    registered_owner_name = fields.Char(string="Nombres y apellidos propietario")
    registered_owner_phone = fields.Char(string="Celular propietario")
    driver_name = fields.Char(string="Nombres y apellidos conductor")
    driver_document_number = fields.Char(string="Numero de cedula conductor")
    driver_address = fields.Char(string="Direccion conductor")
    driver_neighborhood = fields.Char(string="Barrio conductor")
    driver_city = fields.Char(string="Ciudad conductor")
    driver_phone = fields.Char(string="Celular conductor")
    driver_optional_phone = fields.Char(string="Telefono opcional conductor")
    driver_email = fields.Char(string="Correo autorizacion conductor")
    driver_is_fit = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Apto fisica, mental y psicotecnicamente")
    driver_is_trained = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Capacitado y entrenado")
    family_reference_name = fields.Char(string="Referencia familiar")
    family_reference_relationship = fields.Char(string="Parentesco referencia familiar")
    family_reference_phone = fields.Char(string="Celular referencia familiar")
    cargo_reference_name = fields.Char(string="Referencia transporte de carga")
    cargo_reference_phone = fields.Char(string="Celular referencia transporte de carga")
    banking_info_accepted = fields.Boolean(string="Acepto informacion bancaria")
    compensation_accepted = fields.Boolean(string="Acepto compensacion general")
    personal_data_accepted = fields.Boolean(string="Acepto tratamiento de datos personales")
    terms_accepted_at = fields.Datetime(string="Fecha aceptacion terminos")
    owner_has_valid_study = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Propietario con estudio vigente")
    owner_signature = fields.Binary(string="Firma propietario")
    owner_signature_document = fields.Char(string="Cedula firma propietario")
    owner_signed_at = fields.Datetime(string="Fecha firma propietario")
    owner_signature_ip = fields.Char(string="IP firma propietario")
    owner_signature_user_agent = fields.Text(string="Navegador firma propietario")
    driver_has_valid_study = fields.Selection([
        ("yes", "Si"),
        ("no", "No"),
    ], string="Conductor con estudio vigente")
    driver_signature = fields.Binary(string="Firma conductor")
    driver_signature_document = fields.Char(string="Cedula firma conductor")
    driver_signed_at = fields.Datetime(string="Fecha firma conductor")
    driver_signature_ip = fields.Char(string="IP firma conductor")
    driver_signature_user_agent = fields.Text(string="Navegador firma conductor")
    message = fields.Text(string="Observaciones")

    def action_open_printable(self):
        """Abre la hoja de vida imprimible desde la vista interna."""
        self.ensure_one()
        if not self.access_token:
            self.access_token = uuid.uuid4().hex
        return {
            'type': 'ir.actions.act_url',
            'name': 'Hoja de Vida Imprimible',
            'url': f'/registro-conductor/imprimir/{self.id}?token={self.access_token}',
            'target': 'new',
        }

    def _format_co_phone(self, phone):
        """Formatea un numero de telefono segun el estandar colombiano.

        Formatos soportados:
          - Movil  (10 dig, inicia en 3): '3001234567'  -> '300 123 4567'
          - Fijo   ( 7 dig)             : '2345678'     -> '234 5678'
          - Fijo + indicativo ciudad
            (10 dig, inicia en 6)       : '6012345678'  -> '(601) 234 5678'
          - Cualquier otro valor        : se retorna sin cambios
        """
        if not phone:
            return ''
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10 and digits.startswith('3'):
            # Celular colombiano: 300 123 4567
            return f'{digits[0:3]} {digits[3:6]} {digits[6:10]}'
        if len(digits) == 10 and digits.startswith('6'):
            # Fijo con indicativo de ciudad: (601) 234 5678
            return f'({digits[0:3]}) {digits[3:6]} {digits[6:10]}'
        if len(digits) == 7:
            # Fijo local sin indicativo: 234 5678
            return f'{digits[0:3]} {digits[3:7]}'
        # Si no coincide con ningun patron, retornar el valor original
        return phone

    @staticmethod
    def _phone_digits(phone):
        return re.sub(r'\D', '', phone or '')

    @classmethod
    def _is_valid_mobile_phone(cls, phone):
        if not phone:
            return True
        digits = cls._phone_digits(phone)
        return len(digits) == 10 and digits.startswith('3')

    @classmethod
    def _is_valid_phone(cls, phone):
        if not phone:
            return True
        digits = cls._phone_digits(phone)
        return len(digits) == 7 or (len(digits) == 10 and digits[0] in ('3', '6'))

    # -------------------------------------------------------------------------
    # Propietario: normalizacion y validacion
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_city(city):
        """Retorna la ciudad en formato Title Case (primera letra de cada palabra en mayuscula)."""
        return city.strip().title() if city and city.strip() else False

    @api.constrains('owner_email')
    def _check_owner_email(self):
        """Valida que el correo del propietario tenga un formato valido."""
        for record in self:
            if record.owner_email and not self._EMAIL_REGEX.match(record.owner_email.strip()):
                raise ValidationError(
                    f'El correo "{record.owner_email}" no tiene un formato valido.\n'
                    'Ejemplo: propietario@empresa.com'
                )

    @api.constrains('driver_email')
    def _check_driver_email(self):
        """Valida que el correo del conductor tenga un formato valido."""
        for record in self:
            if record.driver_email and not self._EMAIL_REGEX.match(record.driver_email.strip()):
                raise ValidationError(
                    f'El correo "{record.driver_email}" no tiene un formato valido.\n'
                    'Ejemplo: conductor@empresa.com'
                )

    @api.constrains('owner_document_number', 'owner_document_type')
    def _check_owner_document_number(self):
        """Valida el numero de documento del propietario segun el tipo.

        Reglas:
          - CC : solo digitos, entre 6 y 10 caracteres
          - NIT: 9 digitos, opcionalmente seguido de guion y 1 digito verificador (123456789-0)
        """
        for record in self:
            num = record.owner_document_number
            if not num:
                continue
            num = num.strip()
            if record.owner_document_type == 'cc':
                if not re.fullmatch(r'[0-9]{6,10}', num):
                    raise ValidationError(
                        f'La cedula "{num}" debe contener entre 6 y 10 digitos numericos.'
                    )
            elif record.owner_document_type == 'nit':
                if not re.fullmatch(r'[0-9]{9}(-[0-9])?', num):
                    raise ValidationError(
                        f'El NIT "{num}" debe tener el formato: 123456789 o 123456789-0'
                    )

    @api.constrains('driver_document_number')
    def _check_driver_document_number(self):
        """Valida la cedula del conductor."""
        for record in self:
            if record.driver_document_number and not re.fullmatch(r'[0-9]{6,10}', record.driver_document_number.strip()):
                raise ValidationError(
                    f'La cedula del conductor "{record.driver_document_number}" debe contener entre 6 y 10 digitos numericos.'
                )

    @api.constrains(
        'owner_phone',
        'registered_owner_phone',
        'driver_phone',
        'family_reference_phone',
        'cargo_reference_phone',
    )
    def _check_mobile_phones(self):
        """Valida celulares colombianos."""
        labels = {
            'owner_phone': 'celular del propietario',
            'registered_owner_phone': 'celular del propietario registrado',
            'driver_phone': 'celular del conductor',
            'family_reference_phone': 'celular de referencia familiar',
            'cargo_reference_phone': 'celular de referencia de carga',
        }
        for record in self:
            for field_name, label in labels.items():
                value = getattr(record, field_name)
                if value and not self._is_valid_mobile_phone(value):
                    raise ValidationError(
                        f'El {label} debe ser un celular colombiano de 10 digitos que inicia por 3.'
                    )

    @api.constrains('driver_optional_phone')
    def _check_optional_phone(self):
        """Valida telefono opcional fijo o movil."""
        for record in self:
            if record.driver_optional_phone and not self._is_valid_phone(record.driver_optional_phone):
                raise ValidationError(
                    'El telefono opcional debe tener 7 digitos o 10 digitos iniciando por 3 o 6.'
                )

    @api.onchange('owner_city')
    def _onchange_owner_city(self):
        """Normaliza la ciudad del propietario a Title Case en tiempo real."""
        if self.owner_city:
            self.owner_city = self._normalize_city(self.owner_city)

    # -------------------------------------------------------------------------
    # Placas: normalizacion y validacion formato colombiano
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_plate(plate):
        """Retorna la placa en mayusculas sin espacios, o False si esta vacia."""
        return plate.strip().upper() if plate and plate.strip() else False

    @api.constrains('vehicle_plate', 'semi_trailer_plate')
    def _check_plate_format(self):
        """Valida que las placas tengan el formato colombiano valido.

        Formatos aceptados:
          - Vehiculo / carga: ABC123  (3 letras + 3 digitos)
          - Motocicleta     : ABC12   (3 letras + 2 digitos)
        """
        for record in self:
            for field_name, label in [
                ('vehicle_plate', 'Placa del vehiculo'),
                ('semi_trailer_plate', 'Placa del semi/remolque'),
            ]:
                plate = getattr(record, field_name)
                if not plate:
                    continue  # semi_trailer_plate es opcional
                normalized = self._normalize_plate(plate)
                if not self._PLATE_REGEX.match(normalized):
                    raise ValidationError(
                        f'{label} "{normalized}" no tiene el formato colombiano valido.\n'
                        'Formatos aceptados:\n'
                        '  • Vehiculo / carga: ABC123 (3 letras + 3 digitos)\n'
                        '  • Motocicleta     : ABC12  (3 letras + 2 digitos)'
                    )

    @api.onchange('vehicle_plate')
    def _onchange_vehicle_plate(self):
        """Normaliza la placa a mayusculas y advierte si el formato es invalido."""
        if not self.vehicle_plate:
            return
        self.vehicle_plate = self._normalize_plate(self.vehicle_plate)
        if not self._PLATE_REGEX.match(self.vehicle_plate):
            return {
                'warning': {
                    'title': 'Formato de placa invalido',
                    'message': (
                        f'La placa "{self.vehicle_plate}" no tiene el formato colombiano valido.\n\n'
                        'Formatos aceptados:\n'
                        '  • Vehiculo / carga: ABC123 (3 letras + 3 digitos)\n'
                        '  • Motocicleta     : ABC12  (3 letras + 2 digitos)'
                    ),
                }
            }

    @api.onchange('semi_trailer_plate')
    def _onchange_semi_trailer_plate(self):
        """Normaliza la placa del semi a mayusculas y advierte si el formato es invalido."""
        if not self.semi_trailer_plate:
            return
        self.semi_trailer_plate = self._normalize_plate(self.semi_trailer_plate)
        if not self._PLATE_REGEX.match(self.semi_trailer_plate):
            return {
                'warning': {
                    'title': 'Formato de semi/remolque invalido',
                    'message': (
                        f'La placa "{self.semi_trailer_plate}" no tiene el formato colombiano valido.\n\n'
                        'Formatos aceptados:\n'
                        '  • Remolque / carga: ABC123 (3 letras + 3 digitos)\n'
                        '  • Motocicleta     : ABC12  (3 letras + 2 digitos)'
                    ),
                }
            }

    @api.model_create_multi
    def create(self, vals_list):
        """Normaliza placas y ciudad del propietario antes de crear (cubre el formulario web)."""
        for vals in vals_list:
            if vals.get('vehicle_plate'):
                vals['vehicle_plate'] = self._normalize_plate(vals['vehicle_plate'])
            if vals.get('semi_trailer_plate'):
                vals['semi_trailer_plate'] = self._normalize_plate(vals['semi_trailer_plate'])
            if vals.get('owner_city'):
                vals['owner_city'] = self._normalize_city(vals['owner_city'])
        return super().create(vals_list)

    def write(self, vals):
        """Normaliza placas y ciudad del propietario antes de escribir (cubre el formulario web)."""
        if vals.get('vehicle_plate'):
            vals['vehicle_plate'] = self._normalize_plate(vals['vehicle_plate'])
        if vals.get('semi_trailer_plate'):
            vals['semi_trailer_plate'] = self._normalize_plate(vals['semi_trailer_plate'])
        if vals.get('owner_city'):
            vals['owner_city'] = self._normalize_city(vals['owner_city'])
        return super().write(vals)
