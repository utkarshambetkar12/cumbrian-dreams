import frappe
from frappe.model.document import Document

class Booking(Document):
    def validate(self):
        if not self.status:
            self.status = "Active"

        if self.property and self.booking_date:
            dup = frappe.db.exists(
                "Booking",
                {
                    "property": self.property,
                    "booking_date": self.booking_date,
                    "status": "Active",
                    "name": ["!=", self.name],
                },
            )
            if dup:
                frappe.throw("This property is already booked for that date.")
