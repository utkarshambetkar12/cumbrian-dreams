import frappe
from frappe.model.document import Document

class Property(Document):
    def validate(self):
        # Enforce unique Name (title)
        if self.title:
            exists = frappe.db.exists("Property", {"title": self.title, "name": ["!=", self.name]})
            if exists:
                frappe.throw(f"Property with the name '{self.title}' already exists.")
