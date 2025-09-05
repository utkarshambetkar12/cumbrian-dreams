# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/book_on_behalf.py
import frappe
from frappe.utils import getdate
from datetime import date

ALLOWED_ROLES = {"System Manager", "Support", "Host"}

def get_context(context):
    user = frappe.session.user
    if user == "Guest":
        # redirect to login with return URL
        frappe.local.flags.redirect_location = "/login?redirect-to=/book_on_behalf"
        raise frappe.Redirect

    roles = set(frappe.get_roles(user))
    if not (roles & ALLOWED_ROLES):
        # 403
        frappe.throw("You do not have access to this page.", frappe.PermissionError)

    # Host can only see their properties; SM/Support see all
    if "Host" in roles and "System Manager" not in roles and "Support" not in roles:
        props = frappe.get_all(
            "Property",
            filters={"host": user},
            fields=["name", "title", "location", "price_per_night"],
            order_by="modified desc",
            limit_page_length=500,
        )
    else:
        props = frappe.get_all(
            "Property",
            fields=["name", "title", "location", "price_per_night", "host"],
            order_by="modified desc",
            limit_page_length=1000,
        )

    # Users to book on behalf of:
    # Prioritize website users/customers; fall back to all enabled users (excluding Guest/Administrator).
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
        fields=["name", "email", "full_name", "user_type"],
        order_by="full_name asc",
        limit_page_length=1000,
    )

    # pre-fill “today” as min date
    context.today = str(date.today())
    context.props = props
    context.users = users
    context.is_host = "Host" in roles
    context.no_cache = 1
