# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/property.py
import os
import re
import frappe
from frappe.utils import nowdate
from datetime import datetime
from frappe.utils import now_datetime, cint

try:
    from dateutil.relativedelta import relativedelta
except Exception:
    relativedelta = None

def _add_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(month=2, day=28, year=d.year + years)

def _natkey(s):
    # natural sort: 01.jpg, 2.jpg, 10.jpg
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]

def get_context(context):
    name = frappe.form_dict.get("name")
    if not name:
        frappe.local.flags.redirect_location = "/properties"
        raise frappe.Redirect

    fields = [
        "name","title","location","price_per_night","host","features","rules",
        "external_property_id","external_property_widget_id","max_guests",
        "cover_image","rating","reviews","amenities","superhost","summary",
    ]
    meta = frappe.get_meta("Property")
    essential = {"name","title","location","price_per_night","host","features","rules"}
    existing = {df.fieldname for df in meta.fields}
    fields = [f for f in fields if (f in existing) or (f in essential)]

    doc = frappe.get_value("Property", name, fields, as_dict=True)
    if not doc:
        frappe.local.flags.redirect_location = "/properties"
        raise frappe.Redirect

    # ----- Build gallery from DB (child table / cover_image)
    gallery = []
    try:
        imgs = frappe.get_all(
            "Property Image",
            filters={"parent": name},
            fields=["image"],
            order_by="idx asc",
        )
        gallery = [row.image for row in imgs if row.image]
    except Exception:
        pass

    for fn in ["cover_image", "image", "thumbnail"]:
        if doc.get(fn):
            if not gallery or gallery[0] != doc[fn]:
                gallery.insert(0, doc[fn])
            break

    # ----- Fallback: discover static files in /public if DB has none
    if not gallery:
        prop_key = doc.get("external_property_id") or doc["name"]
        base_dir = frappe.get_app_path(
            "cumbrian_dreams", "public", "img", "properties", str(prop_key)
        )
        if os.path.isdir(base_dir):
            exts = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
            files = [f for f in os.listdir(base_dir) if f.lower().endswith(exts)]
            files = sorted(files, key=_natkey)
            gallery = [
                f"/assets/cumbrian_dreams/img/properties/{prop_key}/{f}"
                for f in files
            ]
            # use first as cover if cover_image is empty
            if not doc.get("cover_image") and gallery:
                doc["cover_image"] = gallery[0]

    context.item = doc
    context.gallery = gallery
    context.today = nowdate()

    # 2-year availability URL via your proxy
    today_utc = datetime.utcnow().date()
    to_obj = today_utc + relativedelta(years=2) if relativedelta else _add_years(today_utc, 2)
    from_date = today_utc.strftime("%Y-%m-%d")
    to_date = to_obj.strftime("%Y-%m-%d")
    prop_id = doc.get("external_property_id") or doc["name"]
    context.availability_url = (
        f"/api/method/cumbrian_dreams.api.fetch_external_availability"
        f"?property_id={prop_id}&from_date={from_date}&to_date={to_date}"
    )
    context.current_year = now_datetime().year
    context.no_cache = 1
