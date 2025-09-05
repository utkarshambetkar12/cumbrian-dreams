# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/edit_property.py
import frappe

def _redirect(url: str):
    frappe.local.flags.redirect_location = url
    raise frappe.Redirect

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        _redirect("/login?redirect-to=/my_properties")

    roles = set(frappe.get_roles(user))
    is_sm = "System Manager" in roles
    is_host_role = "Host" in roles

    name = frappe.form_dict.get("name")
    if not name:
        _redirect("/my_properties")

    try:
        doc = frappe.get_doc("Property", name)
    except frappe.DoesNotExistError:
        frappe.throw("Property not found", frappe.DoesNotExistError)

    # Permission: Hosts can only edit their own properties; SM can edit any
    if not is_sm and is_host_role and doc.host != user:
        frappe.throw("You can only edit properties you host.", frappe.PermissionError)

    context.item = {
        "name": doc.name,
        "title": doc.title,
        "price_per_night": doc.price_per_night,
        "location": doc.location,
        "features": doc.features,
        "rules": doc.rules,
        "host": doc.host,
    }

    context.is_system_manager = is_sm
    context.users = []
    if is_sm:
        context.users = frappe.get_all(
            "User",
            filters={"enabled":1, "name":["not in", ["Guest","Administrator"]]},
            fields=["name","full_name","email"],
            order_by="full_name asc",
            limit_page_length=1000
        )

    context.no_cache = 1
