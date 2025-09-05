# apps/cumbrian_dreams/cumbrian_dreams/api.py
import frappe
from frappe.utils import get_datetime, getdate
from typing import Optional
from datetime import datetime
from urllib.parse import quote

ALLOWED_ROLES_DELEGATED = {"System Manager", "Support", "Host"}

def _exists_booking(property_name: str, dt):
    return frappe.db.exists("Booking", {"property": property_name, "booking_date": dt})

@frappe.whitelist(allow_guest=True, methods=["GET"])
def list_properties(
    limit: Optional[int] = 20,
    offset: Optional[int] = 0,
    q: Optional[str] = None,          # free text search (title/location/features)
    host: Optional[str] = None,       # filter by host (User name / email)
    location: Optional[str] = None,   # partial match
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    order_by: Optional[str] = "modified desc"  # e.g. "price asc", "title desc"
):
    """Public listing of properties with paging & filters.

    Query params (all optional):
      - limit (1..100), offset (>=0)
      - q           : free text search on title/location/features
      - host        : exact host user (email/name)
      - location    : partial match
      - min_price   : >=
      - max_price   : <=
      - order_by    : one of [price|title|location|modified|name] + [asc|desc]
    """
    # sanitize paging
    try:
        limit = int(limit)
    except Exception:
        limit = 20
    limit = max(1, min(limit, 100))

    try:
        offset = int(offset)
    except Exception:
        offset = 0
    offset = max(0, offset)

    # fields to return
    fields = [
        "name",                 # e.g., PROP-0001
        "title",                # display name
        "price_per_night",
        "location",
        "host",
        "features",
        "rules",
        "modified"
    ]

    # filters
    filters = []
    if host:
        filters.append(["Property", "host", "=", host])
    if location:
        filters.append(["Property", "location", "like", f"%{location}%"])
    if min_price is not None and str(min_price) != "":
        try:
            filters.append(["Property", "price_per_night", ">=", float(min_price)])
        except Exception:
            pass
    if max_price is not None and str(max_price) != "":
        try:
            filters.append(["Property", "price_per_night", "<=", float(max_price)])
        except Exception:
            pass

    # OR search across a few text fields
    or_filters = None
    if q:
        like = f"%{q}%"
        or_filters = [
            ["Property", "title", "like", like],
            ["Property", "location", "like", like],
            ["Property", "features", "like", like],
        ]

    # order by (whitelist)
    safe_map = {
        "price": "price_per_night",
        "title": "title",
        "location": "location",
        "modified": "modified",
        "name": "name",
    }
    order_clause = "modified desc"
    if isinstance(order_by, str):
        parts = order_by.strip().split()
        key = safe_map.get(parts[0].lower(), "modified") if parts else "modified"
        direction = parts[1].lower() if len(parts) > 1 and parts[1].lower() in ("asc", "desc") else "desc"
        order_clause = f"{key} {direction}"

    # fetch one extra row to know if there's another page
    rows = frappe.get_all(
        "Property",
        fields=fields,
        filters=filters,
        or_filters=or_filters,
        limit_start=offset,
        limit_page_length=limit + 1,
        order_by=order_clause,
    )

    has_more = len(rows) > limit
    items = rows[:limit]

    return {
        "ok": True,
        "items": items,
        "paging": {
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": (offset + limit) if has_more else None,
            "order_by": order_clause,
        },
    }

# GET /api/method/cumbrian_dreams.api.get_property?name=PROP-0001
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_property(name: str = None):
    if not name:
        frappe.local.response["http_status_code"] = 400
        return {"ok": False, "message": "Query param 'name' is required."}
    try:
        doc = frappe.get_doc("Property", name)
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"ok": False, "message": "Property not found."}

    host_full_name = frappe.db.get_value("User", doc.host, "full_name")
    return {
        "ok": True,
        "item": {
            "name": doc.name,
            "title": doc.title,
            "price_per_night": doc.price_per_night,
            "location": doc.location,
            "host": doc.host,
            "host_full_name": host_full_name,
            "features": doc.features,
            "rules": doc.rules,
            "modified": str(doc.modified),
        },
    }

from frappe.utils import get_datetime

# GET /api/method/cumbrian_dreams.api.list_bookings
# Query params (all optional unless noted):
#   property        : Booking.property (e.g., PROP-0001)
#   user            : Booking.user (email/name)
#   host            : filter by host user (email/name) — returns bookings for properties owned by that host
#   q               : text search on Property (title/location/features)
#   status          : Active | Cancelled | All   (default: Active)
#   include_cancelled : (legacy flag) 1/0 — if 1 and status not provided, shows both statuses
#   from_datetime   : 'YYYY-MM-DD HH:mm:ss'
#   to_datetime     : 'YYYY-MM-DD HH:mm:ss'
#   limit           : 1..100 (default 20)
#   offset          : >=0   (default 0)
#   order_by        : [booking_date|modified|name] [asc|desc] (default: booking_date desc)
#   include_property: 1/0 add property details (title, location, host, price_per_night)
#   include_user    : 1/0 add user details (full_name, email)
@frappe.whitelist(methods=["GET"])
def list_bookings(
    property: str | None = None,
    user: str | None = None,
    host: str | None = None,
    q: str | None = None,
    status: str | None = None,
    include_cancelled: int | None = None,
    from_datetime: str | None = None,
    to_datetime: str | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str = "booking_date desc",
    include_property: int = 0,
    include_user: int = 0,
):
    from frappe.utils import get_datetime

    # ---- paging ----
    try:
        limit = int(limit)
    except Exception:
        limit = 20
    limit = max(1, min(limit, 100))

    try:
        offset = int(offset)
    except Exception:
        offset = 0
    offset = max(0, offset)

    # ---- base filters ----
    filters = []

    # Status logic (default Active; legacy include_cancelled=1 -> All)
    show_all_status = False
    if status:
        s = str(status).lower()
        if s in ("all", "any", "*"):
            show_all_status = True
        elif s in ("active", "cancelled"):
            filters.append(["Booking", "status", "=", s.capitalize()])
        else:
            filters.append(["Booking", "status", "=", "Active"])
    else:
        if str(include_cancelled) in ("1", "true", "True"):
            show_all_status = True
        else:
            filters.append(["Booking", "status", "=", "Active"])

    if property:
        filters.append(["Booking", "property", "=", property])

    if from_datetime:
        filters.append(["Booking", "booking_date", ">=", get_datetime(from_datetime)])
    if to_datetime:
        filters.append(["Booking", "booking_date", "<=", get_datetime(to_datetime)])

    # ---- property allowlist from 'host' and/or 'q' ----
    prop_name_allowlist = None

    if host:
        prop_name_allowlist = set(
            frappe.get_all("Property", filters=[["Property", "host", "=", host]], pluck="name")
        )

    if q:
        like = f"%{q}%"
        matches = set(
            frappe.get_all(
                "Property",
                or_filters=[
                    ["Property", "title", "like", like],
                    ["Property", "location", "like", like],
                    ["Property", "features", "like", like],
                ],
                pluck="name",
            )
        )
        prop_name_allowlist = matches if prop_name_allowlist is None else (prop_name_allowlist & matches)

    if prop_name_allowlist is not None:
        if not prop_name_allowlist:
            return {
                "ok": True,
                "items": [],
                "paging": {"offset": offset, "limit": limit, "has_more": False, "next_offset": None, "order_by": "booking_date desc"},
                "filters_applied": {"property": property, "user": user, "host": host, "q": q, "status": "All" if show_all_status else (status or "Active")},
            }
        filters.append(["Booking", "property", "in", list(prop_name_allowlist)])

    if user:
        filters.append(["Booking", "user", "=", user])

    # ---- permission model ----
    session_user = frappe.session.user
    roles = set(frappe.get_roles(session_user))

    if "System Manager" not in roles:
        is_host = "Host" in roles
        if is_host:
            if property:
                # If host asked for a specific property, allow full visibility only if they own it.
                prop_host = frappe.db.get_value("Property", property, "host")
                if prop_host != session_user:
                    # Not their property -> restrict to their own bookings
                    filters.append(["Booking", "user", "=", session_user])
            else:
                # No property specified -> limit to properties owned by the host
                host_props = set(frappe.get_all("Property", filters={"host": session_user}, pluck="name"))
                if prop_name_allowlist is None:
                    prop_name_allowlist = host_props
                else:
                    prop_name_allowlist = prop_name_allowlist & host_props
                if not prop_name_allowlist:
                    return {
                        "ok": True,
                        "items": [],
                        "paging": {"offset": offset, "limit": limit, "has_more": False, "next_offset": None, "order_by": "booking_date desc"},
                        "filters_applied": {"property": property, "user": user, "host": host, "q": q, "status": "All" if show_all_status else (status or "Active")},
                    }
                # ensure an 'in' filter is applied for property
                has_in_filter = any(isinstance(f, list) and len(f) >= 3 and f[1] == "property" and f[2] == "in" for f in filters)
                if not has_in_filter:
                    filters.append(["Booking", "property", "in", list(prop_name_allowlist)])
        else:
            # Normal user -> only their own bookings
            filters.append(["Booking", "user", "=", session_user])

    # ---- order by (whitelist) ----
    safe_keys = {"booking_date": "booking_date", "modified": "modified", "name": "name"}
    ob = "booking_date desc"
    if isinstance(order_by, str):
        parts = order_by.strip().split()
        key = safe_keys.get((parts[0].lower() if parts else ""), "booking_date")
        dirn = (parts[1].lower() if len(parts) > 1 else "desc")
        dirn = "asc" if dirn == "asc" else "desc"
        ob = f"{key} {dirn}"

    # ---- query ----
    base_fields = ["name", "property", "user", "booking_date", "payment_completed", "status", "modified"]
    rows = frappe.get_all(
        "Booking",
        fields=base_fields,
        filters=filters,
        order_by=ob,
        limit_start=offset,
        limit_page_length=limit + 1,  # one extra to compute has_more
    )

    has_more = len(rows) > limit
    items = rows[:limit]

    # ---- enrichment (optional) ----
    if str(include_property) in ("1", "true", "True") and items:
        prop_names = list({r["property"] for r in items})
        prop_map = {
            p["name"]: p
            for p in frappe.get_all(
                "Property",
                fields=["name", "title", "location", "host", "price_per_night"],
                filters=[["Property", "name", "in", prop_names]],
            )
        }
        for r in items:
            r["property_details"] = prop_map.get(r["property"])

    if str(include_user) in ("1", "true", "True") and items:
        user_names = list({r["user"] for r in items})
        user_map = {
            u["name"]: {"name": u["name"], "email": u["email"], "full_name": u["full_name"]}
            for u in frappe.get_all(
                "User",
                fields=["name", "email", "full_name"],
                filters=[["User", "name", "in", user_names]],
            )
        }
        for r in items:
            r["user_details"] = user_map.get(r["user"])

    return {
        "ok": True,
        "items": items,
        "paging": {
            "offset": offset,
            "limit": limit,
            "has_more": has_more,
            "next_offset": (offset + limit) if has_more else None,
            "order_by": ob,
        },
        "filters_applied": {
            "property": property,
            "user": user,
            "host": host,
            "q": q,
            "status": "All" if show_all_status else (status or "Active"),
        },
    }


# POST /api/method/cumbrian_dreams.api.cancel_booking
# Body can be:
#   {"name":"BOOK-0001", "cancel_reason":"..."}
# OR
#   {"property":"PROP-0001","booking_date":"2025-09-01 18:30:00","user":"guest1@...","cancel_reason":"..."}
# If "user" omitted, defaults to session user for identification.
@frappe.whitelist(methods=["POST"])
def cancel_booking(name: str | None = None,
                   property: str | None = None,
                   booking_date: str | None = None,
                   user: str | None = None,
                   cancel_reason: str | None = None):
    # locate the booking
    if name:
        try:
            booking = frappe.get_doc("Booking", name)
        except frappe.DoesNotExistError:
            frappe.local.response["http_status_code"] = 404
            return {"ok": False, "message": "Booking not found."}
    else:
        if not property or not booking_date:
            frappe.local.response["http_status_code"] = 400
            return {"ok": False, "message": "Provide either 'name' OR ('property' + 'booking_date')."}
        dt = get_datetime(booking_date)

        # default user context if not supplied (helps disambiguate)
        if not user:
            user = frappe.session.user

        filters = {
            "property": property,
            "booking_date": dt,
            "status": "Active",
        }
        # If caller is not System Manager or property host, restrict by user
        session_user = frappe.session.user
        roles = set(frappe.get_roles(session_user))
        prop_host = frappe.db.get_value("Property", property, "host")

        if "System Manager" in roles or session_user == prop_host:
            # ok to search broadly
            pass
        else:
            filters["user"] = user or session_user

        names = frappe.get_all("Booking", filters=filters, pluck="name")
        if not names:
            frappe.local.response["http_status_code"] = 404
            return {"ok": False, "message": "Active booking not found for given details."}
        if len(names) > 1:
            frappe.local.response["http_status_code"] = 409
            return {"ok": False, "message": "Multiple bookings match; provide 'name' to cancel a specific one."}
        booking = frappe.get_doc("Booking", names[0])

    # permission: booker, property host, or System Manager
    session_user = frappe.session.user
    roles = set(frappe.get_roles(session_user))
    prop_host = frappe.db.get_value("Property", booking.property, "host")

    allowed = (
        "System Manager" in roles
        or session_user == booking.user
        or session_user == prop_host
    )
    if not allowed:
        frappe.local.response["http_status_code"] = 403
        return {"ok": False, "message": "Not permitted to cancel this booking."}

    if booking.status == "Cancelled":
        return {"ok": True, "message": "Already cancelled.", "booking": booking.name}

    # mark cancelled (no delete)
    booking.status = "Cancelled"
    booking.cancel_reason = cancel_reason
    booking.cancelled_by = session_user
    booking.cancelled_at = now_datetime()
    booking.save(ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True, "message": "Booking cancelled.", "booking": booking.name}

def _exists_booking_day(property_name: str, d):
    return frappe.db.exists("Booking", {"property": property_name, "booking_date": d, "status": "Active"})

@frappe.whitelist(allow_guest=True, methods=["GET"])
def is_property_available(property: str, booking_date: str):
    d = getdate(booking_date)
    available = not _exists_booking_day(property, d)
    return {"ok": True, "property": property, "booking_date": str(d), "available": available}

def book_property(property: str, user: str | None = None, booking_date: str | None = None, payment_completed: int = 0):
    """Create a booking. Allows delegated booking only for:
       - System Manager / Support
       - Host (but only for properties they host)
    """
    d = getdate(booking_date)

    # prevent double-book
    if frappe.db.exists("Booking", {"property": property, "booking_date": d, "status": "Active"}):
        frappe.local.response["http_status_code"] = 409
        return {"ok": False, "message": "Property already booked for that date."}

    session_user = frappe.session.user

    # If no user provided, default to session user
    target_user = user or session_user

    # If booking for someone else, enforce permissions
    if target_user != session_user:
        # System Manager/Support always allowed
        if _user_has_any(ALLOWED_ROLES_DELEGATED):
            # Hosts can only book for their own properties
            if "Host" in frappe.get_roles(session_user):
                if not _property_owned_by_user(property, session_user):
                    raise frappe.PermissionError("Hosts can only book for their own properties.")
        else:
            raise frappe.PermissionError("You are not allowed to book on behalf of another user.")

    doc = frappe.get_doc({
        "doctype": "Booking",
        "property": property,
        "user": target_user,
        "booking_date": d,
        "payment_completed": int(payment_completed) or 0,
        "status": "Active",
    })
    doc.insert()  # normal permission checks apply
    frappe.db.commit()
    return {"ok": True, "message": "Booking confirmed.", "booking": {"name": doc.name}}

# GET /api/method/cumbrian_dreams.api.get_unavailable_dates?property=PROP-0001&from_date=2025-09-01&to_date=2025-09-30
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_unavailable_dates(property: str, from_date: str, to_date: str):
    fd, td = getdate(from_date), getdate(to_date)
    rows = frappe.get_all(
        "Booking",
        filters={
            "property": property,
            "status": "Active",
            "booking_date": ["between", [fd, td]],
        },
        pluck="booking_date"
    )
    # Ensure ISO strings
    return {"ok": True, "property": property, "dates": [str(d) for d in rows]}

def _user_has_any(roles: set[str]) -> bool:
    user_roles = set(frappe.get_roles(frappe.session.user))
    return bool(user_roles & roles)

def _property_owned_by_user(prop: str, user: str) -> bool:
    return frappe.db.exists("Property", {"name": prop, "host": user})

# Create Property
@frappe.whitelist(methods=["POST"])
def create_property(title: str, price_per_night: float, location: str,
                    features: str = "", rules: str = "", host: str | None = None):
    """Create a Property. 
    - Host can create properties for themselves (host is forced to session user).
    - System Manager may optionally set `host` to any user.
    """
    user = frappe.session.user
    if user == "Guest":
        raise frappe.PermissionError("Login required.")

    roles = set(frappe.get_roles(user))
    is_sm = "System Manager" in roles
    is_host = "Host" in roles

    if not (is_sm or is_host):
        raise frappe.PermissionError("Host or System Manager role required.")

    # Choose who will own the property
    host_user = None
    if is_sm and host:                 # allow SM to create for someone else
        host_user = host
    else:
        host_user = user               # Host always creates for themselves

    # Basic validation
    if not title or not location:
        frappe.throw("Title and Location are required.")
    try:
        price = float(price_per_night)
    except Exception:
        frappe.throw("Price per Night must be a number.")

    doc = frappe.get_doc({
        "doctype": "Property",
        "title": title.strip(),
        "price_per_night": price,
        "location": location.strip(),
        "host": host_user,
        "features": (features or "").strip(),
        "rules": (rules or "").strip(),
    })
    doc.insert()   # normal permissions apply
    frappe.db.commit()

    return {"ok": True, "message": "Property created.", "property": {"name": doc.name}}

# Update Property
@frappe.whitelist(methods=["POST"])
def update_property(name: str,
                    title: str | None = None,
                    price_per_night: float | None = None,
                    location: str | None = None,
                    features: str | None = None,
                    rules: str | None = None,
                    host: str | None = None):
    """Update a Property.
    - Host can edit ONLY properties they host (cannot change host).
    - System Manager can edit any property and may change host.
    """
    user = frappe.session.user
    if user == "Guest":
        raise frappe.PermissionError("Login required.")

    roles = set(frappe.get_roles(user))
    is_sm = "System Manager" in roles
    is_host_role = "Host" in roles

    if not (is_sm or is_host_role):
        raise frappe.PermissionError("Host or System Manager role required.")

    doc = frappe.get_doc("Property", name)

    # Permission: Hosts may only edit their own properties
    if not is_sm and is_host_role:
        if doc.host != user:
            raise frappe.PermissionError("You can only edit properties you host.")

    # Normalize and assign
    if title is not None:
        doc.title = title.strip()
    if price_per_night is not None and price_per_night != "":
        try:
            doc.price_per_night = float(price_per_night)
        except Exception:
            frappe.throw("Price per Night must be a number.")
    if location is not None:
        doc.location = (location or "").strip()
    if features is not None:
        doc.features = (features or "").strip()
    if rules is not None:
        doc.rules = (rules or "").strip()

    # Only SM can change host
    if is_sm and host is not None and host != "":
        doc.host = host

    doc.save()  # normal perms
    frappe.db.commit()
    return {
        "ok": True,
        "message": "Property updated.",
        "property": {"name": doc.name}
    }

# Delete Property
@frappe.whitelist(methods=["POST"])
def delete_property(name: str):
    """Delete a Property document.
    - Host: may delete only properties they host.
    - System Manager: may delete any property.
    - If any Booking references the property (Active or Cancelled), deletion is blocked.
    """
    user = frappe.session.user
    if user == "Guest":
        raise frappe.PermissionError("Login required.")

    roles = set(frappe.get_roles(user))
    is_sm = "System Manager" in roles
    is_host_role = "Host" in roles

    # Load the doc (raises DoesNotExistError if invalid name)
    doc = frappe.get_doc("Property", name)

    # Permission: Hosts can delete only their own properties
    if not is_sm:
        if not is_host_role or doc.host != user:
            raise frappe.PermissionError("You can only delete properties you host.")

    # Hard safety: block delete if any bookings exist
    bookings_count = frappe.db.count("Booking", {"property": name})
    if bookings_count > 0:
        frappe.local.response["http_status_code"] = 409
        return {
            "ok": False,
            "message": f"Cannot delete: {bookings_count} booking(s) reference this property. "
                       "Cancel & delete those bookings first."
        }

    # Delete
    frappe.delete_doc("Property", name)  # respects link checks, permissions already validated
    frappe.db.commit()
    return {"ok": True, "message": "Property deleted."}

import frappe
from datetime import datetime, timedelta
from urllib.parse import quote

@frappe.whitelist(allow_guest=True)
def fetch_external_availability(property_id: str, from_date: str, to_date: str):
    """
    Chunked proxy for FreeToBook per-property availability.
    - Accepts up to multi-year ranges from the frontend.
    - Splits into <=186-day chunks upstream (uses 180 to be safe).
    - Warms cookies on the property page and uses browser-like headers.
    - Merges results and returns one combined list.
    """
    # ---- validate inputs ----
    if not property_id:
        frappe.throw("Missing property_id", exc=frappe.ValidationError)
    if not from_date or not to_date:
        frappe.throw("Missing from_date/to_date", exc=frappe.ValidationError)
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end   = datetime.strptime(to_date, "%Y-%m-%d").date()
    except Exception:
        frappe.throw("Invalid date format. Use YYYY-MM-DD.", exc=frappe.ValidationError)
    if start > end:
        frappe.throw("from_date must be <= to_date", exc=frappe.ValidationError)

    base = f"https://freetobook.com/booking-pages/property/{quote(str(property_id))}"
    avail_url = f"{base}/availability"

    # Browser-like headers; Referer must be the property page
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    headers_page = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    headers_api = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
        "Origin": "https://freetobook.com",
        "Referer": base,
        "X-Requested-With": "XMLHttpRequest",
    }

    # ---- perform chunked fetch ----
    CHUNK_DAYS = 180  # <=186 per FTB constraint
    merged_by_date = {}  # date -> entry

    try:
        import requests
        sess = requests.Session()

        # Warm cookies (non-fatal if it fails)
        try:
            sess.get(base, headers=headers_page, timeout=12, allow_redirects=True)
        except requests.RequestException:
            pass

        cur = start
        while cur <= end:
            chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
            params = {
                "from_date": cur.strftime("%Y-%m-%d"),
                "to_date":   chunk_end.strftime("%Y-%m-%d"),
            }

            r = sess.get(avail_url, params=params, headers=headers_api, timeout=15, allow_redirects=True)
            if r.status_code == 403:
                # retry without X-Requested-With (some stacks dislike it)
                hdr_retry = dict(headers_api)
                hdr_retry.pop("X-Requested-With", None)
                r = sess.get(avail_url, params=params, headers=hdr_retry, timeout=15, allow_redirects=True)

            r.raise_for_status()
            try:
                data = r.json()
            except ValueError:
                frappe.log_error(r.text[:800], "FTB availability non-JSON")
                frappe.throw("Upstream did not return JSON.", exc=frappe.ValidationError)

            # Extract list in either camelCase or snake_case
            arr = []
            if isinstance(data, dict):
                arr = (data.get("datedPropertyAvailabilities")
                       or data.get("dated_property_availabilities")
                       or [])
            elif isinstance(data, list):
                arr = data

            for entry in arr:
                date_str = (entry.get("date")
                            or entry.get("Date"))
                if not date_str:
                    continue
                merged_by_date[date_str] = entry  # last one wins if dup

            cur = chunk_end + timedelta(days=1)

        # Build sorted combined list
        out_list = [merged_by_date[d] for d in sorted(merged_by_date.keys())]
        return {
            "propertyId": property_id,
            "fromDate": from_date,
            "toDate": to_date,
            "datedPropertyAvailabilities": out_list,
        }

    except requests.HTTPError as e:
        resp = getattr(e, "response", None)
        status = getattr(resp, "status_code", "???")
        body = getattr(resp, "text", "")[:800]
        frappe.log_error(f"FTB HTTP {status}: {body}", "fetch_external_availability")
        frappe.throw("Failed to fetch availability (HTTP).", exc=frappe.ValidationError)
    except requests.RequestException as e:
        frappe.log_error(f"FTB network error: {e}", "fetch_external_availability")
        frappe.throw("Failed to fetch availability (network).", exc=frappe.ValidationError)
