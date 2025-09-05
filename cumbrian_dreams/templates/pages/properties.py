# apps/cumbrian_dreams/cumbrian_dreams/templates/pages/properties.py
import os
import json
import frappe
from frappe.utils import now_datetime, cint

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif")

def _coerce_prop_id(prop) -> str:
    """
    Return a string property id from external_property_id (preferred) or name.
    Handles ints/floats/None gracefully.
    """
    raw = None
    try:
        raw = prop.get("external_property_id") or prop.get("name") or ""
    except AttributeError:
        # in the unlikely event prop isn't a dict
        raw = prop or ""
    return str(raw).strip()

def _assets_dir_for(prop) -> tuple[str, str]:
    """Return (filesystem_dir, prop_id) for this property."""
    prop_id = _coerce_prop_id(prop)
    base = os.path.join(
        frappe.get_app_path("cumbrian_dreams"),
        "public","img", "properties", prop_id
    )
    return base, prop_id

def _first_asset_image(prop) -> str | None:
    """
    Pick the first reasonable image for this property from /public/properties/<id>/.
    Preference: cover.*, 01.*, 1.*, main.*, hero.* — then alphabetical.
    """
    base, prop_id = _assets_dir_for(prop)
    if not os.path.isdir(base):
        return None

    preferred_stems = ("cover", "01", "1", "main", "hero")
    for stem in preferred_stems:
        for ext in IMAGE_EXTS:
            fn = f"{stem}{ext}"
            p = os.path.join(base, fn)
            if os.path.isfile(p):
                return f"/assets/cumbrian_dreams/img/properties/{prop_id}/{fn}"

    try:
        for fn in sorted(os.listdir(base), key=str.lower):
            full = os.path.join(base, fn)
            if os.path.isfile(full) and fn.lower().endswith(IMAGE_EXTS):
                return f"/assets/cumbrian_dreams/img/properties/{prop_id}/{fn}"
    except Exception:
        pass

    return None

def get_context(context):
    form = frappe.form_dict
    limit = cint(form.get("limit") or 24)
    offset = cint(form.get("offset") or 0)

    fields = ["name", "title", "location", "price_per_night"]
    meta = frappe.get_meta("Property")
    def has(fn): return any(df.fieldname == fn for df in meta.fields)
    for fn in ["cover_image", "summary", "amenities", "badge", "superhost", "external_property_id"]:
        if has(fn):
            fields.append(fn)

    items = frappe.get_all(
        "Property",
        filters={},
        fields=fields,
        order_by="modified desc",
        start=offset,
        page_length=limit,
        as_list=False,
    )

    placeholder = "/assets/cumbrian_dreams/img/placeholder.jpg"

    for p in items:
        # normalize amenities to a list if it's a JSON string or CSV
        am = p.get("amenities")
        if isinstance(am, str):
            try:
                p["amenities"] = json.loads(am)
            except Exception:
                p["amenities"] = [a.strip() for a in am.split(",") if a.strip()]

        # fill cover_image from assets folder if DB field is empty
        if not p.get("cover_image"):
            p["cover_image"] = _first_asset_image(p) or placeholder

    context.items = items
    context.filters = {
        "limit": limit,
        "offset": offset,
        "location": form.get("location") or "",
        "from_date": form.get("from_date") or "",
        "to_date": form.get("to_date") or "",
    }
    context.paging = {"has_more": len(items) == limit, "next_offset": offset + limit}
    context.current_year = now_datetime().year
    context.no_cache = 1
