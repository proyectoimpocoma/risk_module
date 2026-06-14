"""Mixin de firma con OTP por correo.

Encapsula toda la logica relacionada con la verificacion del correo del
firmante (propietario o conductor) antes de aceptar la firma: generacion
de codigo, throttling, HMAC, ventana de expiracion, maximo de intentos.

Extraido de ``risk_submission.py`` en la refactorizacion 19.0.1.1.0.
Mantiene su propio logger ``risk_module.signatures`` para que se pueda
filtrar de forma independiente en configuracion.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from odoo import fields, models

_signature_logger = logging.getLogger("risk_module.signatures")

SIGNATURE_CODE_TTL_MINUTES = 15
SIGNATURE_CODE_RESEND_SECONDS = 60
SIGNATURE_CODE_MAX_ATTEMPTS = 5


class RiskSubmissionSignature(models.Model):
    _inherit = "risk.module"
    _description = "OTP de firma por correo"

    def _signature_party_config(self, party):
        """Return the signature configuration mapping for the requested party.

        Valid parties are 'owner' and 'driver'. A ValueError is raised for invalid parties.
        """
        configs = {
            "owner": {
                "label": "propietario",
                "email_field": "owner_email",
                "name_field": "owner_name",
                "template": "risk_module.email_template_owner_signature_code",
                "email": "owner_signature_email",
                "hash": "owner_signature_code_hash",
                "sent_at": "owner_signature_code_sent_at",
                "expires_at": "owner_signature_code_expires_at",
                "verified_at": "owner_signature_verified_at",
                "verified_ip": "owner_signature_verified_ip",
                "attempts": "owner_signature_code_attempts",
                "state": "owner_signature_verification_state",
            },
            "driver": {
                "label": "conductor",
                "email_field": "driver_email",
                "name_field": "driver_name",
                "template": "risk_module.email_template_driver_signature_code",
                "email": "driver_signature_email",
                "hash": "driver_signature_code_hash",
                "sent_at": "driver_signature_code_sent_at",
                "expires_at": "driver_signature_code_expires_at",
                "verified_at": "driver_signature_verified_at",
                "verified_ip": "driver_signature_verified_ip",
                "attempts": "driver_signature_code_attempts",
                "state": "driver_signature_verification_state",
            },
        }
        if party not in configs:
            raise ValueError("Invalid signature verification party: %s" % party)
        return configs[party]

    def _signature_code_hash(self, party, code):
        """Return a secure HMAC hash for a signature verification code.

        The hash is derived from the record identity, access token, party and code.
        """
        self.ensure_one()
        salt = "%s:%s:%s" % (self._name, self.id, self.access_token or "")
        payload = "%s:%s" % (party, code)
        return hmac.new(
            salt.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signature_email_verified_for(self, party, email):
        """Return True when the given email is verified for the signature party.

        The method checks the stored state, verification timestamp, and matching email.
        """
        self.ensure_one()
        config = self._signature_party_config(party)
        return bool(
            email
            and self[config["state"]] == "verified"
            and self[config["verified_at"]]
            and self[config["email"]] == email
        )

    def _send_signature_code(self, party):
        """Generate and send a verification code to the party's email address.

        The method enforces resend throttling and stores the hashed code and
        expiration details on the record.
        """
        self.ensure_one()
        config = self._signature_party_config(party)
        email = (self[config["email_field"]] or "").strip()

        if not email:
            _signature_logger.warning(
                "Signature code send blocked without email submission_id=%s party=%s",
                self.id,
                party,
            )
            return {
                "ok": False,
                "message": "Debes ingresar un correo para el %s antes de enviar el codigo."
                % config["label"],
            }

        now = fields.Datetime.now()
        sent_at = self[config["sent_at"]]
        if sent_at and (now - sent_at).total_seconds() < SIGNATURE_CODE_RESEND_SECONDS:
            _signature_logger.warning(
                "Signature code resend throttled submission_id=%s party=%s email=%s",
                self.id,
                party,
                email,
            )
            return {
                "ok": False,
                "message": "Espera un minuto antes de solicitar otro codigo.",
            }

        code = "%06d" % secrets.randbelow(1000000)
        expires_at = now + timedelta(minutes=SIGNATURE_CODE_TTL_MINUTES)

        self.write(
            {
                config["email"]: email,
                config["hash"]: self._signature_code_hash(party, code),
                config["sent_at"]: now,
                config["expires_at"]: expires_at,
                config["verified_at"]: False,
                config["verified_ip"]: False,
                config["attempts"]: 0,
                config["state"]: "sent",
            }
        )

        template = self.env.ref(config["template"], raise_if_not_found=False)
        if not template:
            _signature_logger.warning("Signature code template not found party=%s", party)
            return {
                "ok": False,
                "message": "No se encontro la plantilla de correo para enviar el codigo.",
            }

        self._queue_mail_after_commit(
            template=template,
            record_id=self.id,
            email_values={
                "email_from": "reporte@impocoma.com",
                "reply_to": "reporte@impocoma.com",
                "email_to": email,
                "recipient_ids": [(5, 0, 0)],
            },
            force_send=True,
            template_context={
                "signature_code": code,
                "signature_party_label": config["label"],
                "signature_person_name": self[config["name_field"]] or config["label"],
                "signature_code_ttl_minutes": SIGNATURE_CODE_TTL_MINUTES,
            },
            failure_values={
                config["hash"]: False,
                config["sent_at"]: False,
                config["expires_at"]: False,
                config["verified_at"]: False,
                config["verified_ip"]: False,
                config["attempts"]: 0,
                config["state"]: "not_sent",
            },
            success_message="Codigo de verificacion de firma enviado al %s: %s."
            % (config["label"], email),
            failure_message="No fue posible enviar el codigo de verificacion al %s: %s."
            % (config["label"], email),
        )

        _signature_logger.info(
            "Signature code email scheduled after commit submission_id=%s party=%s email=%s expires_at=%s",
            self.id,
            party,
            email,
            expires_at,
        )

        return {
            "ok": True,
            "message": "Enviamos un codigo al correo del %s." % config["label"],
        }

    def _verify_signature_code(self, party, code, ip_address=None):
        """Verify a submitted signature code and update verification state.

        The method handles invalid codes, expired codes, throttling, and blocked state.
        """
        self.ensure_one()
        config = self._signature_party_config(party)
        clean_code = (code or "").strip()
        now = fields.Datetime.now()

        if self[config["state"]] == "blocked":
            return {
                "ok": False,
                "message": "El codigo esta bloqueado por demasiados intentos. Solicita uno nuevo.",
            }
        if not self[config["hash"]]:
            return {
                "ok": False,
                "message": "Primero debes solicitar un codigo de verificacion.",
            }
        if not clean_code or len(clean_code) != 6 or not clean_code.isdigit():
            return {
                "ok": False,
                "message": "Ingresa un codigo de 6 digitos.",
            }
        if self[config["expires_at"]] and now > self[config["expires_at"]]:
            self.write({config["state"]: "expired"})
            return {
                "ok": False,
                "message": "El codigo vencio. Solicita uno nuevo.",
            }

        attempts = self[config["attempts"]] + 1
        if not hmac.compare_digest(
            self[config["hash"]],
            self._signature_code_hash(party, clean_code),
        ):
            state = "blocked" if attempts >= SIGNATURE_CODE_MAX_ATTEMPTS else "sent"
            self.write(
                {
                    config["attempts"]: attempts,
                    config["state"]: state,
                }
            )
            _signature_logger.warning(
                "Signature code verification failed submission_id=%s party=%s attempts=%s state=%s",
                self.id,
                party,
                attempts,
                state,
            )
            if state == "blocked":
                return {
                    "ok": False,
                    "message": "Codigo bloqueado por demasiados intentos. Solicita uno nuevo.",
                }
            return {
                "ok": False,
                "message": "Codigo incorrecto. Revisa el correo e intenta nuevamente.",
            }

        self.write(
            {
                config["verified_at"]: now,
                config["verified_ip"]: ip_address,
                config["attempts"]: attempts,
                config["state"]: "verified",
            }
        )
        self.message_post(
            body="Correo de firma verificado para el %s: %s."
            % (config["label"], self[config["email"]])
        )
        _signature_logger.info(
            "Signature code verified submission_id=%s party=%s email=%s ip=%s",
            self.id,
            party,
            self[config["email"]],
            ip_address,
        )
        return {
            "ok": True,
            "message": "Correo del %s verificado correctamente." % config["label"],
        }

    def send_owner_signature_code(self):
        """Send a verification code to the owner's email address."""
        return self._send_signature_code("owner")

    def verify_owner_signature_code(self, code, ip_address=None):
        """Verify the owner's submitted signature code."""
        return self._verify_signature_code("owner", code, ip_address=ip_address)

    def send_driver_signature_code(self):
        """Send a verification code to the driver's email address."""
        return self._send_signature_code("driver")

    def verify_driver_signature_code(self, code, ip_address=None):
        """Verify the driver's submitted signature code."""
        return self._verify_signature_code("driver", code, ip_address=ip_address)
