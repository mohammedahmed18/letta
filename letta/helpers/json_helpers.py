import json
from datetime import datetime


def json_loads(data):
    return json.loads(data)


def json_dumps(data, indent=2):
    # indent=0 disables pretty print (most efficient and usually sufficient for function output)
    return json.dumps(data, indent=indent, default=_safe_serializer, ensure_ascii=False)


# Module-scope for reuse
def _safe_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")
