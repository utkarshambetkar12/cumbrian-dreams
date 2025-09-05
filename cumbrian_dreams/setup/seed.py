import frappe
from frappe.utils import flt

def ensure_role(role_name, desk_access=0):
    if not frappe.db.exists("Role", {"role_name": role_name}):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            "desk_access": desk_access
        }).insert(ignore_permissions=True)

def ensure_user(email, first_name, roles, password="Test@123", user_type="Website User"):
    if frappe.db.exists("User", email):
        return email
    doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "user_type": user_type,
        "send_welcome_email": 0,
        "new_password": password,
        "roles": [{"role": r} for r in roles],
    })
    doc.insert(ignore_permissions=True)
    return doc.name

def ensure_property(title, price, location, host_email, rules="", features=""):
    if frappe.db.exists("Property", {"title": title}):
        return
    frappe.get_doc({
        "doctype": "Property",
        "title": title,
        "price_per_night": flt(price),
        "location": location,
        "host": host_email,
        "rules": rules,
        "features": features
    }).insert(ignore_permissions=True)

def seed_all():
    # 1) Roles
    ensure_role("Host", desk_access=0)
    ensure_role("Customer", desk_access=0)

    # 2) Users
    host1 = ensure_user("host1@cumbrian.local", "Host One", ["Host"])
    host2 = ensure_user("host2@cumbrian.local", "Host Two", ["Host"])
    host3 = ensure_user("host3@cumbrian.local", "Host Three", ["Host"])

    cust1 = ensure_user("guest1@cumbrian.local", "Guest One", ["Customer"])
    cust2 = ensure_user("guest2@cumbrian.local", "Guest Two", ["Customer"])

    hosts = [host1, host2, host3]

    # 3) Properties (10)
    props = [
        ("Seaside Cottage", 4500, "Alibaug", "No parties after 10pm", "Sea view, WiFi, AC"),
        ("Mountain Vista", 5200, "Mahabaleshwar", "No pets", "Hill view, WiFi, Heater"),
        ("City Studio", 3500, "Pune", "No smoking", "Kitchenette, WiFi"),
        ("Lakeside Retreat", 6000, "Lavasa", "Quiet hours 10pm-7am", "Lake view, BBQ"),
        ("Forest Cabin", 4000, "Lonavala", "No outside fire", "Fireplace, WiFi"),
        ("Heritage Home", 4800, "Nashik", "No loud music", "Courtyard, WiFi"),
        ("Riverside Den", 5200, "Karjat", "Max 4 guests", "River view, AC"),
        ("Sunset Villa", 7000, "Goa", "Pool rules apply", "Pool, WiFi, Kitchen"),
        ("Cliff House", 8000, "Varkala", "No pets", "Cliff view, AC, WiFi"),
        ("Garden Bungalow", 3900, "Panchgani", "No smoking inside", "Garden, WiFi"),
    ]

    for i, (title, price, location, rules, features) in enumerate(props):
        ensure_property(
            title=title,
            price=price,
            location=location,
            host_email=hosts[i % len(hosts)],
            rules=rules,
            features=features
        )

    return {
        "hosts": hosts,
        "customers": [cust1, cust2],
        "properties": frappe.get_all("Property", pluck="name")
    }
