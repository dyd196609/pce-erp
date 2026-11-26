

# Native formal date consumer restoration.
def display_timezone_label(identifier, *, fallback=None):
    """Use the agreed business name without changing an IANA identifier.

    Fallback is caller-owned: the catalog retains its existing labels for all
    other zones, while date preview retains its existing identifier display.
    This name is not an offset calculation or a calendar interpretation.
    """
    if identifier == 'Asia/Shanghai':
        return '北京时间（UTC+8）'
    return identifier if fallback is None else fallback
