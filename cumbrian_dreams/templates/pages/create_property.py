# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/create_property.py
import frappe

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        # redirect to login and come back
        frappe.local.flags.redirect_location = "/login?redirect-to=/create_property"
        raise frappe.Redirect

    roles = set(frappe.get_roles(user))
    if not (("Host" in roles) or ("System Manager" in roles)):
        # 403
        frappe.throw("Host or System Manager role required.", frappe.PermissionError)

    # For System Manager we’ll show a host selector; Host users won’t see it.
    context.is_system_manager = "System Manager" in roles
    context.users = []
    if context.is_system_manager:
        context.users = frappe.get_all(
            "User",
            filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
            fields=["name", "email", "full_name"],
            order_by="full_name asc",
            limit_page_length=1000,
        )

    context.no_cache = 1
