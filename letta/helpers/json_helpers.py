import json
from datetime import datetime


def json_loads(data):
    return json.loads(data, strict=False)


def json_dumps(data, indent=2):
    def safe_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8")
        raise TypeError(f"Type {type(obj)} not serializable")

    return json.dumps(data, indent=indent, default=safe_serializer, ensure_ascii=False)


# Helper functions for clean_json instead of lambda allocations
def strategy_json_loads(output):
    return json_loads(output)


def strategy_json_loads_rcurly(output):
    return json_loads(output + "}")


def strategy_json_loads_r2curly(output):
    return json_loads(output + "}}")


def strategy_json_loads_quote2curly(output):
    return json_loads(output + '"}}')


def strategy_json_loads_strip(output):
    s = output.strip().rstrip(",")
    return json_loads(s + "}")


def strategy_json_loads_strip_r2curly(output):
    s = output.strip().rstrip(",")
    return json_loads(s + "}}")


def strategy_json_loads_strip_quote2curly(output):
    s = output.strip().rstrip(",")
    return json_loads(s + '"}}')


def strategy_repair_json_string(output):
    return json_loads(repair_json_string(output))


def strategy_repair_even_worse_json(output):
    return json_loads(repair_even_worse_json(output))


def strategy_extract_first_json(output):
    return extract_first_json(output + "}}")


def strategy_clean_and_interpret_send_message_json(output):
    return clean_and_interpret_send_message_json(output)


def strategy_json_loads_replace_esc_us(output):
    return json_loads(replace_escaped_underscores(output))


def strategy_extract_first_json_replace_esc_us(output):
    return extract_first_json(replace_escaped_underscores(output) + "}}")


# ----------- Optimized json_dumps ---------------
def _safe_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8")
    raise TypeError(f"Type {type(obj)} not serializable")


def fast_json_dumps(data, indent=2):
    """Avoids allocating closure for default handler; only use if needed."""
    # Fast path: if clearly basic types, avoid default handler
    try:
        return json.dumps(data, indent=indent, ensure_ascii=False)
    except TypeError:
        return json.dumps(data, indent=indent, default=_safe_serializer, ensure_ascii=False)
