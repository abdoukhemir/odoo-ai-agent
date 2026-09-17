import base64
import logging
import re

from odoo import fields as odoo_fields

_logger = logging.getLogger(__name__)

# HTML tag stripping regex
HTML_TAG_RE = re.compile(r'<[^>]+>')


def format_for_llm(records_data, model_obj, fields_list=None, raw_html=False):
    """
    Format Odoo record data for LLM consumption.

    - Many2one: [id, name] -> {"id": id, "name": name}
    - Selection: value -> {"value": value, "label": label}
    - Binary: base64 data -> placeholder string
    - HTML: strip tags (unless raw_html=True)
    - false -> null (handled by JSON serializer)
    """
    if not records_data:
        return records_data

    field_defs = {}
    if model_obj:
        try:
            all_fields = fields_list or list(records_data[0].keys()) if records_data else []
            field_defs = model_obj.fields_get(all_fields, attributes=['type', 'selection', 'string'])
        except Exception:
            pass

    formatted = []
    for record in records_data:
        formatted_record = {}
        for field_name, value in record.items():
            if field_name == 'id':
                formatted_record['id'] = value
                continue

            field_info = field_defs.get(field_name, {})
            field_type = field_info.get('type', '')

            formatted_record[field_name] = _format_field_value(
                value, field_type, field_info, field_name, raw_html
            )
        formatted.append(formatted_record)
    return formatted


def _format_field_value(value, field_type, field_info, field_name, raw_html):
    """Format a single field value for LLM output."""
    if value is False or value is None:
        return None

    if field_type == 'many2one':
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return {'id': value[0], 'name': value[1]}
        return value

    if field_type in ('one2many', 'many2many'):
        if isinstance(value, list):
            return value
        return value

    if field_type == 'selection':
        selection = field_info.get('selection', [])
        label = value
        for sel_val, sel_label in selection:
            if sel_val == value:
                label = sel_label
                break
        return {'value': value, 'label': label}

    if field_type == 'binary':
        if value and isinstance(value, str) and len(value) > 100:
            try:
                size_bytes = len(base64.b64decode(value))
                if size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
                elif size_bytes > 1024:
                    size_str = f"{size_bytes / 1024:.1f}KB"
                else:
                    size_str = f"{size_bytes}B"
            except Exception:
                size_str = "unknown"
            return f"<binary:{field_name}:{size_str}>"
        return value

    if field_type == 'html':
        if not raw_html and isinstance(value, str):
            return strip_html(value)
        return value

    return value


def strip_html(html_string):
    """Strip HTML tags and return plain text."""
    if not html_string:
        return ''
    text = HTML_TAG_RE.sub('', html_string)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_smart_default_fields(model_obj, max_fields=15):
    """
    Get a smart subset of fields for a model.
    Excludes binary fields, internal fields, and limits to useful fields.
    """
    try:
        all_fields = model_obj.fields_get(
            attributes=['type', 'string', 'store', 'readonly']
        )
    except Exception:
        return ['id', 'display_name']

    # Always include these
    priority_fields = ['id', 'display_name', 'name']
    result = [f for f in priority_fields if f in all_fields]

    # Skip these field types and patterns
    skip_types = {'binary', 'one2many', 'many2many'}
    skip_prefixes = ('avatar_', 'image_', 'message_', 'activity_', 'website_message_')
    skip_fields = {
        'id', 'display_name', 'name',  # already added
        '__last_update', 'write_uid', 'create_uid',
        'message_is_follower', 'message_needaction',
        'message_has_error', 'has_message',
    }

    for fname, finfo in all_fields.items():
        if len(result) >= max_fields:
            break
        if fname in skip_fields:
            continue
        if finfo.get('type') in skip_types:
            continue
        if any(fname.startswith(p) for p in skip_prefixes):
            continue
        result.append(fname)

    return result


def generate_summary(records_data, total_count, offset, limit, model_name):
    """
    Generate a natural language summary of search/browse results.
    Helps AI assistants quickly understand the dataset.
    """
    showing_count = len(records_data)
    start = offset + 1
    end = offset + showing_count

    parts = [f"Found {total_count} {model_name} record(s)."]

    if total_count > 0:
        parts.append(f"Showing {start}-{end}.")

    if total_count > showing_count:
        remaining = total_count - end
        parts.append(f"{remaining} more available.")

    # Try to generate top aggregations from the data
    if records_data and showing_count >= 3:
        agg = _generate_aggregations(records_data)
        if agg:
            parts.append(agg)

    return ' '.join(parts)


def _generate_aggregations(records_data):
    """Try to find categorical fields and generate top-N aggregations."""
    if not records_data or len(records_data) < 3:
        return ''

    # Look for common categorical fields
    cat_fields = ['state', 'status', 'type', 'category_id', 'country_id', 'city']
    for field in cat_fields:
        if field not in records_data[0]:
            continue

        counts = {}
        for record in records_data:
            val = record.get(field)
            if val is None or val is False:
                continue
            if isinstance(val, dict):
                val = val.get('name') or val.get('label') or str(val.get('value', ''))
            val = str(val)
            if val:
                counts[val] = counts.get(val, 0) + 1

        if len(counts) >= 2:
            top = sorted(counts.items(), key=lambda x: -x[1])[:3]
            items = ', '.join(f"{k} ({v})" for k, v in top)
            field_label = field.replace('_id', '').replace('_', ' ').title()
            return f"Top {field_label}: {items}."

    return ''
