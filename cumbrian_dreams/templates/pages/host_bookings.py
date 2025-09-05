# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/host_bookings.py
import frappe
from frappe.utils import getdate

def _redirect(url: str):
    frappe.local.flags.redirect_location = url
    raise frappe.Redirect

def get_context(context):
    user = frappe.session.user

    # If guest, redirect to login with return URL
    if user == "Guest":
        _redirect("/login?redirect-to=/host_bookings")

    roles = set(frappe.get_roles(user))
    is_system_manager = "System Manager" in roles
    is_host = "Host" in roles
    if not (is_host or is_system_manager):
        # Return proper 403 instead of 417
        frappe.throw("Host access required", frappe.PermissionError)

    form = frappe.form_dict
    property_filter = form.get("property") or None
    status = (form.get("status") or "Active").capitalize()
    if status not in ("Active", "Cancelled", "All"):
        status = "Active"

    from_date = form.get("from_date") or None
    to_date = form.get("to_date") or None
    try:
        limit = max(1, min(int(form.get("limit") or 50), 200))
    except Exception:
        limit = 50
    try:
        offset = max(0, int(form.get("offset") or 0))
    except Exception:
        offset = 0

    host_email = form.get("host") if (is_system_manager and form.get("host")) else user
    host_props = frappe.get_all("Property", filters={"host": host_email}, fields=["name", "title", "location"])
    host_prop_names = [p["name"] for p in host_props]

    context.host_props = host_props
    if not host_prop_names:
        context.items = []
        context.filters = {"property": "", "status": status, "from_date": from_date or "", "to_date": to_date or "", "limit": limit, "offset": offset}
        context.paging = {"has_more": False, "next_offset": None}
        context.no_cache = 1
        return

    filters = [["Booking", "property", "in", host_prop_names]]
    if property_filter:
        filters.append(["Booking", "property", "=", property_filter])
    if status != "All":
        filters.append(["Booking", "status", "=", status])
    if from_date:
        filters.append(["Booking", "booking_date", ">=", getdate(from_date)])
    if to_date:
        filters.append(["Booking", "booking_date", "<=", getdate(to_date)])

    rows = frappe.get_all(
        "Booking",
        fields=["name", "property", "user", "booking_date", "payment_completed", "status", "modified"],
        filters=filters,
        order_by="booking_date desc",
        limit_start=offset,
        limit_page_length=limit + 1,
    )
    has_more = len(rows) > limit
    items = rows[:limit]

    prop_map = {p["name"]: p for p in host_props}
    user_names = list({r["user"] for r in items})
    user_map = {}
    if user_names:
        users = frappe.get_all("User", fields=["name", "email", "full_name"], filters=[["User", "name", "in", user_names]])
        user_map = {u["name"]: u for u in users}
    for r in items:
        r["property_details"] = prop_map.get(r["property"])
        r["user_details"] = user_map.get(r["user"])

    context.items = items
    context.filters = {"property": property_filter or "", "status": status, "from_date": from_date or "", "to_date": to_date or "", "limit": limit, "offset": offset}
    context.paging = {"has_more": has_more, "next_offset": (offset + limit) if has_more else None}
    context.is_system_manager = is_system_manager
    context.no_cache = 1
