import uuid

from odoo import fields, models


class RiskSubmission(models.Model):
    _name = "risk.module"
    _description = "Solicitud de habilitacion de terceros"
    _rec_name = "vehicle_plate"
    _order = "create_date desc"

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
