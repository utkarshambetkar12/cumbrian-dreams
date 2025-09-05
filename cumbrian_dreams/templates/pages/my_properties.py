# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/my_properties.py
import frappe

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/my_properties"
        raise frappe.Redirect

    roles = set(frappe.get_roles(user))
    is_sm = "System Manager" in roles

    form = frappe.form_dict
    host_filter = form.get("host") if is_sm and form.get("host") else user

    props = frappe.get_all(
        "Property",
        filters={"host": host_filter} if host_filter else {},
        fields=["name","title","location","price_per_night","host","modified"],
        order_by="modified desc",
        limit_page_length=500
    )

    context.is_system_manager = is_sm
    context.host_filter = host_filter or ""
    context.props = props

    # For SM, optional host dropdown
    context.hosts = []
    if is_sm:
        context.hosts = frappe.get_all(
            "User",
            filters={"enabled":1, "name":["not in", ["Guest","Administrator"]]},
            fields=["name","full_name","email"],
            order_by="full_name asc",
            limit_page_length=1000
        )

    context.no_cache = 1
