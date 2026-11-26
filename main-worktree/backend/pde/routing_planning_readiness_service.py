"""Read-only routing foundation and production-planning handoff assessment.

The service never creates a production plan and never invents resource, time,
capacity or calendar facts.  It projects only persisted routing/master-data
facts and reports the exact formal data still required by planning.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from pfm.models import Shift
from system.models import Process, ProcessTeamCapability, Team, Workshop

from .models import (
    Equipment,
    Routing,
    RoutingStep,
    RoutingVersion,
    StandardCapacity,
    WorkCenter,
    WorkCenterOperationCapability,
    WorkCenterTeamAssignment,
)
from .routing_step_applicability_service import (
    CONTRACT_VERSION as APPLICABILITY_CONTRACT_VERSION,
    NOT_APPLICABLE,
    PENDING,
    RoutingStepApplicabilityResolver,
)


class RoutingPlanningReadinessService:
    CALENDAR_CONTRACT_VERSION = "PCE-MFG-CALENDAR-V1.0"
    CLASSIFICATION_LABELS = {
        "DEVELOPED_USABLE": "已开发且可用",
        "DEVELOPED_DATA_MISSING": "软件已具备，正式数据缺失",
        "DEVELOPED_DEFECTIVE": "已开发但存在缺陷",
        "SOFTWARE_REQUIRED": "缺少必要软件能力",
        "NOT_APPLICABLE": "当前对象不适用",
    }

    @staticmethod
    def _active_on(row, on_date):
        return bool(
            getattr(row, "is_active", True)
            and (getattr(row, "effective_from", None) is None or row.effective_from <= on_date)
            and (getattr(row, "effective_to", None) is None or row.effective_to >= on_date)
        )

    @classmethod
    def _calendar_fact(cls, work_center):
        policy = work_center.capacity_policy if isinstance(work_center.capacity_policy, dict) else {}
        calendar = policy.get("calendar")
        if not isinstance(calendar, dict):
            return {
                "ready": False,
                "contractVersion": cls.CALENDAR_CONTRACT_VERSION,
                "statusCode": "MANUFACTURING_CALENDAR_MISSING",
                "statusLabel": "未维护制造日历",
            }
        weekly = calendar.get("weeklyAvailableMinutes")
        expected_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        valid_weekly = isinstance(weekly, dict) and set(weekly) == expected_days and all(
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and 0 <= value <= 1440
            for value in weekly.values()
        )
        exceptions = calendar.get("exceptions", [])
        valid_exceptions = isinstance(exceptions, list) and all(
            isinstance(item, dict)
            and isinstance(item.get("availableMinutes"), (int, float))
            and not isinstance(item.get("availableMinutes"), bool)
            and 0 <= item["availableMinutes"] <= 1440
            and cls._valid_iso_date(item.get("date"))
            for item in exceptions
        )
        if valid_exceptions:
            exception_dates = [date.fromisoformat(str(item["date"])).isoformat() for item in exceptions]
            valid_exceptions = len(exception_dates) == len(set(exception_dates))
        ready = bool(
            calendar.get("contractVersion") == cls.CALENDAR_CONTRACT_VERSION
            and str(calendar.get("timezone") or "").strip()
            and valid_weekly
            and valid_exceptions
        )
        return {
            "ready": ready,
            "contractVersion": calendar.get("contractVersion") or cls.CALENDAR_CONTRACT_VERSION,
            "timezone": calendar.get("timezone") or "",
            "weeklyAvailableMinutes": weekly if valid_weekly else None,
            "exceptionCount": len(exceptions) if valid_exceptions else None,
            "statusCode": "CALENDAR_READY" if ready else "MANUFACTURING_CALENDAR_INVALID",
            "statusLabel": "制造日历可供计划读取" if ready else "制造日历合同不完整",
        }

    @staticmethod
    def _valid_iso_date(value):
        try:
            date.fromisoformat(str(value))
            return True
        except (TypeError, ValueError):
            return False

    @classmethod
    def foundation_assessment(cls, company_id, *, on_date=None):
        on_date = on_date or date.today()
        work_centers = list(WorkCenter.objects.filter(company_id=company_id))
        active_work_centers = [row for row in work_centers if cls._active_on(row, on_date)]
        valid_calendars = sum(1 for row in active_work_centers if cls._calendar_fact(row)["ready"])
        counts = {
            "routingCount": Routing.objects.filter(company_id=company_id).count(),
            "routingVersionCount": RoutingVersion.objects.filter(routing__company_id=company_id).count(),
            "routingStepCount": RoutingStep.objects.filter(routing_version__routing__company_id=company_id).count(),
            "operationCount": Process.objects.filter(company_id=company_id).count(),
            "workshopCount": Workshop.objects.filter(company_id=company_id).count(),
            "workCenterCount": len(work_centers),
            "equipmentCount": Equipment.objects.filter(work_center__company_id=company_id).count(),
            "teamCount": Team.objects.filter(company_id=company_id).count(),
            "shiftCount": Shift.objects.filter(company_id=company_id).count(),
            "standardCapacityCount": StandardCapacity.objects.filter(company_id=company_id).count(),
            "workCenterOperationCapabilityCount": WorkCenterOperationCapability.objects.filter(
                work_center__company_id=company_id,
            ).count(),
            "processTeamCapabilityCount": ProcessTeamCapability.objects.filter(
                operation__company_id=company_id,
            ).count(),
            "workCenterTeamAssignmentCount": WorkCenterTeamAssignment.objects.filter(
                work_center__company_id=company_id,
            ).count(),
            "workCenterCalendarCount": valid_calendars,
        }

        def capability(code, name, classification, evidence):
            return {
                "code": code,
                "name": name,
                "classificationCode": classification,
                "classificationLabel": cls.CLASSIFICATION_LABELS[classification],
                "evidence": evidence,
            }

        relations_ready = counts["workCenterOperationCapabilityCount"] > 0
        capacity_ready = counts["standardCapacityCount"] > 0
        calendar_ready = counts["workCenterCalendarCount"] > 0
        capabilities = [
            capability("ROUTING_HEADER_VERSION", "路线头与版本", "DEVELOPED_USABLE", "Routing / RoutingVersion正式模型与生命周期字段"),
            capability("ORDERED_DEPENDENCY_GRAPH", "有序步骤、分支与汇合", "DEVELOPED_USABLE", "RoutingStep.sequence + predecessor_sequences"),
            capability("RESOURCE_BOUNDARIES", "车间、工作中心、设备、班组边界", "DEVELOPED_USABLE", "Workshop / WorkCenter / Equipment / Team独立模型"),
            capability(
                "ALTERNATIVE_WORK_CENTERS", "工序主/备选工作中心",
                "DEVELOPED_USABLE" if relations_ready else "DEVELOPED_DATA_MISSING",
                f"WorkCenterOperationCapability正式关系 {counts['workCenterOperationCapabilityCount']} 条",
            ),
            capability("WORKLOAD_AND_TIME", "日产能、准备与转运时间（天）", "DEVELOPED_USABLE", "StandardCapacity数量/天 + preparation_days/transfer_days；历史小时字段不参与APS"),
            capability(
                "MEASURED_CAPACITY", "资源产能",
                "DEVELOPED_USABLE" if capacity_ready else "DEVELOPED_DATA_MISSING",
                f"StandardCapacity正式记录 {counts['standardCapacityCount']} 条",
            ),
            capability(
                "MANUFACTURING_CALENDAR", "工作中心制造日历",
                "DEVELOPED_USABLE" if calendar_ready else "DEVELOPED_DATA_MISSING",
                f"WorkCenter.capacity_policy / {cls.CALENDAR_CONTRACT_VERSION} 有效日历 {valid_calendars} 个",
            ),
            capability("QUALITY_INPUT_OUTPUT", "质量点与投入产出关系", "DEVELOPED_USABLE", "RoutingStep质量字段、applies_to_item与operation_parameters"),
            capability("YIELD_OUTSOURCING", "良率与内部/委外执行", "DEVELOPED_USABLE", "operation_parameters.yieldRate / executionMode通用合同"),
        ]
        return {
            "factSource": "server",
            "assessmentDate": on_date.isoformat(),
            "calendarContractVersion": cls.CALENDAR_CONTRACT_VERSION,
            "inventory": counts,
            "capabilities": capabilities,
            "softwareGapCount": sum(1 for row in capabilities if row["classificationCode"] == "SOFTWARE_REQUIRED"),
            "defectCount": sum(1 for row in capabilities if row["classificationCode"] == "DEVELOPED_DEFECTIVE"),
            "formalDataGapCount": sum(1 for row in capabilities if row["classificationCode"] == "DEVELOPED_DATA_MISSING"),
        }

    @staticmethod
    def _serialize_capacity(row):
        return {
            "id": row.pk,
            "code": row.code,
            "name": row.name,
            "resourceScope": row.resource_scope,
            "workCenterId": row.work_center_id,
            "operationId": row.operation_id,
            "equipmentId": row.equipment_id,
            "measurementStatus": row.measurement_status,
            "quantity": str(row.quantity) if row.quantity is not None else None,
            "uomId": row.uom_id,
            "timeBasis": row.time_basis,
            "timeBasisQuantity": str(row.time_basis_quantity) if row.time_basis_quantity is not None else None,
            "productTypeId": row.product_type_id,
            "preparationDays": str(row.preparation_days) if row.preparation_days is not None else None,
            "transferDays": str(row.transfer_days) if row.transfer_days is not None else None,
            "timeUnit": "DAY",
            "conditions": row.conditions or {},
        }

    @classmethod
    def assess(
        cls, routing_version, *, bom_version=None, on_date=None,
        engineering_calculation=None, engineering_document_version=None,
        order_engineering_baseline=None, order_engineering_instance=None,
        production_plan=None, manufacturing_output=None,
    ):
        from .daily_capacity_service import DailyCapacityReadinessService
        return DailyCapacityReadinessService.assess(
            routing_version, bom_version=bom_version, on_date=on_date,
            engineering_calculation=engineering_calculation,
            engineering_document_version=engineering_document_version,
            order_engineering_baseline=order_engineering_baseline,
            order_engineering_instance=order_engineering_instance,
            production_plan=production_plan, manufacturing_output=manufacturing_output,
        )
