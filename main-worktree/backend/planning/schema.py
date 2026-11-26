from django.db import connection


ORDER_PLANNING_TABLES = {
    "planning_mps_run",
    "planning_mps_line",
    "planning_mps_demand_allocation",
    "planning_mrp_run",
    "planning_mrp_proposal",
}


def order_planning_schema_status():
    """Expose deployment separately from a legitimately empty planning result."""
    try:
        present = set(connection.introspection.table_names())
        missing = sorted(ORDER_PLANNING_TABLES - present)
        return {
            "status": "DEPLOYED" if not missing else "NOT_DEPLOYED",
            "deployed": not missing,
            "requiredTables": sorted(ORDER_PLANNING_TABLES),
            "missingTables": missing,
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "READ_FAILED",
            "deployed": False,
            "requiredTables": sorted(ORDER_PLANNING_TABLES),
            "missingTables": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def order_planning_schema_ready():
    """Backward-compatible boolean capability check."""
    return order_planning_schema_status()["deployed"]
