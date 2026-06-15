import logging

from odoo import fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RiskSubmissionMasterSync(models.Model):
    _inherit = "risk.module"

    vehicle_id = fields.Many2one(
        "risk.vehicle",
        string="Vehiculo registrado",
        readonly=True,
        copy=False,
        tracking=True,
    )
    driver_id = fields.Many2one(
        "risk.driver",
        string="Conductor registrado",
        readonly=True,
        copy=False,
        tracking=True,
    )
    owner_id = fields.Many2one(
        "risk.owner",
        string="Propietario / tenedor registrado",
        readonly=True,
        copy=False,
        tracking=True,
    )
    vehicle_owner_link_id = fields.Many2one(
        "risk.vehicle.owner",
        string="Relacion vehiculo-propietario",
        readonly=True,
        copy=False,
        tracking=True,
    )
    master_validation_summary = fields.Char(
        string="Resumen maestros",
        compute="_compute_master_validation_summary",
    )

    def _compute_master_validation_summary(self):
        for record in self:
            messages = []
            vehicle = record.vehicle_id or record._master_vehicle_for_plate()
            driver = record.driver_id or record._master_driver_for_document()
            if vehicle:
                if vehicle.status == "blocked":
                    messages.append("Vehiculo bloqueado")
                if vehicle.current_driver_id:
                    messages.append(
                        "Vehiculo asociado a %s" % vehicle.current_driver_id.display_name
                    )
            if driver and driver.current_vehicle_id:
                messages.append(
                    "Conductor asociado a %s" % driver.current_vehicle_id.display_name
                )
            if record.vehicle_owner_link_id:
                messages.append("Propietario/tenedor relacionado")
            record.master_validation_summary = "; ".join(messages) or "Sin conflictos en maestros"

    def _master_vehicle_for_plate(self):
        self.ensure_one()
        return self.env["risk.vehicle"].find_by_plate(self.vehicle_plate)

    def _master_driver_for_document(self):
        self.ensure_one()
        return self.env["risk.driver"].find_by_document(self.driver_document_number)

    def _master_vehicle_conflict_message(self):
        self.ensure_one()
        vehicle = self._master_vehicle_for_plate()
        if not vehicle:
            return False
        if vehicle.status == "blocked":
            return (
                "El vehiculo %s se encuentra bloqueado para nuevas habilitaciones. "
                "Por favor contacta al equipo de riesgo."
            ) % vehicle.plate
        driver = vehicle.assignment_conflict_for_driver(self.driver_document_number)
        if driver:
            return (
                "El vehiculo %s ya se encuentra habilitado con el conductor %s. "
                "Si necesitas actualizarlo, solicita revision al equipo de riesgo."
            ) % (vehicle.plate, driver.document_number)
        return False

    def _master_driver_conflict_message(self):
        self.ensure_one()
        driver = self._master_driver_for_document()
        if not driver:
            return False
        vehicle = driver.assignment_conflict_for_vehicle(self.vehicle_plate)
        if vehicle:
            return (
                "El conductor con cedula %s ya se encuentra habilitado para el "
                "vehiculo %s. Un conductor solo puede estar activo en un vehiculo."
            ) % (driver.document_number, vehicle.plate)
        return False

    def _check_master_assignment_conflicts(self):
        for record in self:
            message = record._master_vehicle_conflict_message() or record._master_driver_conflict_message()
            if message:
                raise ValidationError(message)

    def _sync_master_records(self, activate_assignment=False):
        for record in self:
            vehicle = record._sync_master_vehicle()
            driver = record._sync_master_driver()
            owner = record._sync_master_owner(
                record.owner_document_type,
                record.owner_document_number,
                record.owner_name,
                record.owner_phone,
                record.owner_email,
            )
            link = record._sync_master_vehicle_owner_link(vehicle, owner)
            record._sync_registered_owner_link(vehicle, owner)
            record._sync_additional_owner_links(vehicle)

            values = {}
            if vehicle and record.vehicle_id != vehicle:
                values["vehicle_id"] = vehicle.id
            if driver and record.driver_id != driver:
                values["driver_id"] = driver.id
            if owner and record.owner_id != owner:
                values["owner_id"] = owner.id
            if link and record.vehicle_owner_link_id != link:
                values["vehicle_owner_link_id"] = link.id
            if values:
                record.with_context(skip_risk_form_lock=True).write(values)

            if activate_assignment:
                record._activate_master_vehicle_driver(vehicle, driver)

            _logger.info(
                "Synced master records submission_id=%s vehicle_id=%s driver_id=%s owner_id=%s link_id=%s activate_assignment=%s",
                record.id,
                vehicle.id if vehicle else None,
                driver.id if driver else None,
                owner.id if owner else None,
                link.id if link else None,
                activate_assignment,
            )

    def _sync_master_vehicle(self):
        self.ensure_one()
        plate = self._master_clean(self.vehicle_plate, upper=True)
        if not plate:
            return self.env["risk.vehicle"]
        Vehicle = self.env["risk.vehicle"].sudo().with_context(active_test=False)
        vehicle = Vehicle.search([("plate", "=", plate)], limit=1)
        values = {
            "plate": plate,
            "semi_trailer_plate": self._master_clean(self.semi_trailer_plate, upper=True) or False,
            "active": True,
        }
        if vehicle:
            vehicle.write(self._changed_values(vehicle, values))
            return vehicle
        return Vehicle.create(values)

    def _sync_master_driver(self):
        self.ensure_one()
        document_number = self._master_clean(self.driver_document_number)
        if not document_number:
            return self.env["risk.driver"]
        Driver = self.env["risk.driver"].sudo().with_context(active_test=False)
        driver = Driver.search([("document_number", "=", document_number)], limit=1)
        values = {
            "name": self._master_clean(self.driver_name) or document_number,
            "document_number": document_number,
            "active": True,
        }
        self._add_if_present(values, "phone", self.driver_phone)
        self._add_if_present(values, "optional_phone", self.driver_optional_phone)
        self._add_if_present(values, "email", self.driver_email, lower=True)
        if driver:
            driver.write(self._changed_values(driver, values))
            return driver
        return Driver.create(values)

    def _sync_master_owner(self, document_type, document_number, name, phone, email=False):
        self.ensure_one()
        document_type = document_type or "cc"
        document_number = self._master_clean(document_number)
        if not document_number:
            return self.env["risk.owner"]
        Owner = self.env["risk.owner"].sudo().with_context(active_test=False)
        owner = Owner.search(
            [
                ("document_type", "=", document_type),
                ("document_number", "=", document_number),
            ],
            limit=1,
        )
        values = {
            "name": self._master_clean(name) or document_number,
            "document_type": document_type,
            "document_number": document_number,
            "active": True,
        }
        self._add_if_present(values, "phone", phone)
        self._add_if_present(values, "email", email, lower=True)
        if owner:
            owner.write(self._changed_values(owner, values))
            return owner
        return Owner.create(values)

    def _sync_master_vehicle_owner_link(self, vehicle, owner, role=False):
        self.ensure_one()
        if not vehicle or not owner:
            return self.env["risk.vehicle.owner"]
        role = role or ("owner" if self.same_owner_on_license != "no" else "holder")
        return self._get_or_create_vehicle_owner_link(vehicle, owner, role)

    def _sync_registered_owner_link(self, vehicle, main_owner):
        self.ensure_one()
        if self.same_owner_on_license != "no" or not vehicle:
            return self.env["risk.vehicle.owner"]
        registered_owner = self._sync_master_owner(
            self.registered_owner_document_type,
            self.registered_owner_document_number,
            self.registered_owner_name,
            self.registered_owner_phone,
        )
        if not registered_owner or registered_owner == main_owner:
            return self.env["risk.vehicle.owner"]
        return self._get_or_create_vehicle_owner_link(vehicle, registered_owner, "owner")

    def _sync_additional_owner_links(self, vehicle):
        """Sync every additional owner line to the master data, creating the
        risk.owner record and its vehicle-owner relation with the chosen role."""
        self.ensure_one()
        if not vehicle:
            return self.env["risk.vehicle.owner"]
        links = self.env["risk.vehicle.owner"]
        for line in self.submission_owner_ids:
            owner = self._sync_master_owner(
                line.document_type,
                line.document_number,
                line.name,
                line.phone,
                line.email,
            )
            if not owner:
                continue
            links |= self._get_or_create_vehicle_owner_link(
                vehicle, owner, line.role or "owner"
            )
        return links

    def _get_or_create_vehicle_owner_link(self, vehicle, owner, role):
        self.ensure_one()
        Link = self.env["risk.vehicle.owner"].sudo().with_context(active_test=False)
        link = Link.search(
            [
                ("vehicle_id", "=", vehicle.id),
                ("owner_id", "=", owner.id),
                ("role", "=", role),
            ],
            order="active desc, id desc",
            limit=1,
        )
        values = {
            "vehicle_id": vehicle.id,
            "owner_id": owner.id,
            "role": role,
            "active": True,
            "date_from": self.form_date or fields.Date.context_today(self),
            "date_to": False,
        }
        if link:
            link.write(self._changed_values(link, values))
            return link
        return Link.create(values)

    def _activate_master_vehicle_driver(self, vehicle, driver):
        self.ensure_one()
        if not vehicle or not driver:
            return
        vehicle.write(
            {
                "current_driver_id": driver.id,
                "status": "enabled",
                "active": True,
            }
        )
        driver.write(
            {
                "current_vehicle_id": vehicle.id,
                "active": True,
            }
        )

    def _changed_values(self, record, values):
        changed = {}
        for field_name, value in values.items():
            if field_name not in record._fields:
                continue
            current = record[field_name]
            if getattr(current, "id", current) != value:
                changed[field_name] = value
        return changed

    def _master_clean(self, value, upper=False, lower=False):
        value = (value or "").strip()
        if upper:
            return value.upper()
        if lower:
            return value.lower()
        return value

    def _add_if_present(self, values, field_name, value, upper=False, lower=False):
        value = self._master_clean(value, upper=upper, lower=lower)
        if value:
            values[field_name] = value
