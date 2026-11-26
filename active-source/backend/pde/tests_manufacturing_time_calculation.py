"""Synthetic, database-free tests of the manufacturing-time input boundary."""
from copy import deepcopy
from decimal import Decimal
import unittest

from pde.manufacturing_time_calculation import (
    convert_capacity_time, expand_calendar_window as _expand_calendar_window, normalize_policy_payload,
    preview_arrangement_pattern, preview_operation_time, resolve_time_window,
)


def expand_calendar_window(payload, *, start_date, end_date):
    return _expand_calendar_window(payload, start_date=start_date, end_date=end_date,
                                   company_id=9, work_center_id=4)


def segment(start, end, end_day=0, start_day=0, **extra):
    return {"start": start, "end": end, "startDayOffset": start_day,
            "endDayOffset": end_day, **extra}


def arrangement(segments=None, breaks=None, mode="WINDOWS_WITH_BREAKS"):
    return {"inputMode": mode,
            "segments": segments if segments is not None else [segment("09:00", "18:00")],
            "breaks": breaks if breaks is not None else [segment("12:00", "13:00")]}


def shared(processing=None, resource=None, weekdays=("MON",), timezone="Etc/UTC"):
    processing = processing or arrangement()
    return {"timezone": timezone,
            "patterns": {"NORMAL": {"processing": deepcopy(processing),
                                      "resource": deepcopy(resource or processing)}},
            "weeklyPatterns": {key: "NORMAL" if key in weekdays else None
                               for key in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")},
            "exceptions": []}


def component(minutes, *, clock="RESOURCE_WORK_TIME", occupancy="WORK_CENTER", interruptible=True):
    return {"clock": clock, "value": str(minutes), "unit": "MINUTE", "basisReference": "SIMULATED_FOR_TEST",
            "occupancy": occupancy, "interruptible": interruptible, "parallel": False}


def basis():
    return {"standardDaySource": "WORK_SYSTEM_REVISION", "standardPattern": "NORMAL",
            "conversionMode": "LINEAR_NET_MINUTES", "linearApproved": True,
            "processing": {"interruptible": True, "overtimeAllowed": False},
            "preparation": component(30),
            "transfer": component(45, clock="ELAPSED_TIME", occupancy="WAIT_ONLY", interruptible=False),
            "standardCapacityHash": "a" * 64, "businessBasis": "SIMULATED_FOR_TEST",
            "approvalBasis": "SIMULATED_FOR_TEST", "applicability": {"fixtureOnly": True}}


def codes(result):
    return {item["code"] for item in result["errors"]}


class ManufacturingTimeCalculationTests(unittest.TestCase):
    def test_normal_day_and_separate_total_resource_window(self):
        policy = shared(resource=arrangement([segment("08:30", "18:00")]))
        result = normalize_policy_payload("SHARED_ARRANGEMENT", policy, strict=True)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["facts"]["patterns"]["NORMAL"]["processing"]["netMinutes"], "480")
        self.assertEqual(result["facts"]["patterns"]["NORMAL"]["resource"]["netMinutes"], "510")

    def test_already_net_segments_do_not_deduct_break_again(self):
        value = arrangement([segment("09:00", "12:00"), segment("13:00", "18:00")], mode="NET_WORK_SEGMENTS")
        result = normalize_policy_payload("SHARED_ARRANGEMENT", shared(value))
        fact = result["facts"]["patterns"]["NORMAL"]["processing"]
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(fact["netMinutes"], "480")
        self.assertEqual(fact["deductedRestMinutes"], "0")

    def test_overlapping_net_work_and_rest_is_rejected(self):
        value = arrangement(mode="NET_WORK_SEGMENTS")
        result = normalize_policy_payload("SHARED_ARRANGEMENT", shared(value))
        self.assertIn("REST_OVERLAPS_NET_WORK", codes(result))
        self.assertFalse(result["ready"])

    def test_overlap_diagnostic_never_approves_union(self):
        value = arrangement([segment("09:00", "13:00"), segment("12:00", "18:00")], [])
        result = normalize_policy_payload("SHARED_ARRANGEMENT", shared(value), strict=True)
        self.assertIn("OVERLAPPING_INTERVAL", codes(result))
        self.assertFalse(result["ready"])
        self.assertTrue(any("segments[1]" in item["path"] for item in result["errors"]))

    def test_duplicate_breaks_not_double_deducted_but_must_be_corrected(self):
        value = arrangement(breaks=[segment("12:00", "13:00"), segment("12:30", "13:00")])
        result = normalize_policy_payload("SHARED_ARRANGEMENT", shared(value))
        fact = result["facts"]["patterns"]["NORMAL"]["processing"]
        self.assertEqual(fact["restMinutes"], "90")
        self.assertEqual(fact["uniqueRestMinutes"], "60")
        self.assertEqual(fact["netMinutes"], "480")
        self.assertFalse(result["ready"])

    def test_break_outside_window_rejected(self):
        result = normalize_policy_payload("SHARED_ARRANGEMENT", shared(arrangement(breaks=[segment("08:00", "08:30")])))
        self.assertIn("REST_OUTSIDE_WORK_WINDOW", codes(result))

    def test_unknown_nested_field_is_not_silently_saved(self):
        policy = shared()
        policy["patterns"]["NORMAL"]["processing"]["segments"][0]["capacityMultiplier"] = 2
        result = normalize_policy_payload("SHARED_ARRANGEMENT", policy)
        self.assertIn("UNKNOWN_FIELD", codes(result))
        self.assertTrue(any(item["severity"] == "ERROR" for item in result["errors"]))

    def test_bad_json_enum_types_report_errors_instead_of_raising(self):
        policy = shared()
        policy["patterns"]["NORMAL"]["processing"]["inputMode"] = []
        policy["exceptions"] = [{"date": [], "dateBasis": {}, "target": [], "action": []}]
        result = normalize_policy_payload("SHARED_ARRANGEMENT", policy)
        self.assertFalse(result["ready"])
        self.assertIn("STRING_REQUIRED", codes(result))
        value = basis()
        value["conversionMode"] = {}
        value["standardPattern"] = []
        value["preparation"]["clock"] = []
        value["preparation"]["unit"] = {}
        value["preparation"]["occupancy"] = []
        value["preparation"]["basisReference"] = {}
        self.assertFalse(normalize_policy_payload("CAPACITY_TIME_BASIS", value)["ready"])

    def test_empty_structured_conditions_do_not_confirm_capacity_basis(self):
        value = basis()
        value["applicability"] = {"conditions": "  "}
        result = normalize_policy_payload("CAPACITY_TIME_BASIS", value, strict=True)
        self.assertFalse(result["ready"])
        self.assertIn("APPLICABILITY_REQUIRED", codes(result))

    def test_boolean_is_not_numeric_time_or_quantity(self):
        value = basis()
        value["preparation"]["value"] = True
        result = convert_capacity_time(demand_quantity=True, capacity_quantity=120, basis=value, standard_day_minutes=480)
        self.assertFalse(result["ready"])
        self.assertIn("INVALID_NUMBER", codes(result))

    def test_incomplete_draft_has_diagnostics_not_exact_dates(self):
        policy = {"timezone": "Etc/UTC", "patterns": {"NORMAL": {"processing": arrangement()}}}
        result = normalize_policy_payload("SHARED_ARRANGEMENT", policy)
        self.assertFalse(result["ready"])
        self.assertTrue(all(item["severity"] == "INCOMPLETE" for item in result["errors"]))
        expanded = expand_calendar_window(policy, start_date="2026-11-02", end_date="2026-11-02")
        self.assertFalse(expanded["ready"])
        self.assertEqual(expanded["processingIntervals"], [])

    def test_original_and_returned_payload_are_isolated(self):
        policy = shared()
        original = deepcopy(policy)
        result = normalize_policy_payload("SHARED_ARRANGEMENT", policy)
        result["payload"]["patterns"]["NORMAL"]["processing"]["segments"][0]["start"] = "00:00"
        self.assertEqual(policy, original)

    def test_processing_cannot_open_outside_total_resource_window(self):
        result = normalize_policy_payload("SHARED_ARRANGEMENT", shared(resource=arrangement([segment("10:00", "18:00")])))
        self.assertIn("PROCESSING_OUTSIDE_RESOURCE", codes(result))

    def test_overnight_natural_and_production_day_conservation(self):
        night = arrangement([segment("22:00", "06:00", 1)], [segment("01:00", "01:30", 1, 1)])
        result = expand_calendar_window(shared(night), start_date="2026-11-02", end_date="2026-11-03")
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "120")
        self.assertEqual(result["naturalDays"]["2026-11-03"]["processingMinutes"], "330")
        self.assertEqual(result["productionDays"]["2026-11-02"]["processingMinutes"], "450")

    def test_single_draft_pattern_observation_does_not_fabricate_resource_identity(self):
        night = arrangement([segment("22:00", "06:00", 1)], [segment("01:00", "01:30", 1, 1)])
        policy = shared(night)
        del policy["weeklyPatterns"]
        result = preview_arrangement_pattern(policy, pattern_name="NORMAL", production_date="2026-11-02")
        self.assertTrue(result["patternCalculationReady"], result["errors"])
        self.assertFalse(result["ready"])
        self.assertFalse(result["isEffectivePolicyProof"])
        self.assertNotIn("companyId", result)
        self.assertNotIn("workCenterId", result)
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "120")
        self.assertEqual(result["naturalDays"]["2026-11-03"]["processingMinutes"], "330")
        self.assertEqual(result["productionDays"]["2026-11-02"]["processingMinutes"], "450")

    def test_single_pattern_observation_refuses_unresolved_dst(self):
        policy = shared(arrangement([segment("01:15", "03:00")], []), timezone="America/New_York")
        result = preview_arrangement_pattern(policy, pattern_name="NORMAL", production_date="2026-11-01")
        self.assertFalse(result["patternCalculationReady"])
        self.assertIn("AMBIGUOUS_LOCAL_TIME", codes(result))
        self.assertEqual(result["processingIntervals"], [])

    def test_prior_production_day_carry_in_is_read(self):
        night = arrangement([segment("22:00", "06:00", 1)], [])
        result = expand_calendar_window(shared(night), start_date="2026-11-03", end_date="2026-11-03")
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-03"]["processingMinutes"], "360")
        self.assertEqual(result["productionDays"]["2026-11-02"]["processingMinutes"], "360")

    def test_invalid_or_extreme_preview_dates_are_diagnostics(self):
        for start, end in (("2026-11-03", "2026-11-02"), ("0001-01-01", "0001-01-01"),
                           ("9999-12-31", "9999-12-31"), ("2026-01-01", "2027-02-01")):
            result = expand_calendar_window(shared(), start_date=start, end_date=end)
            self.assertFalse(result["ready"])
            self.assertIn("INVALID_PREVIEW_WINDOW", codes(result))

    def test_natural_date_closure_removes_previous_day_carry_in(self):
        night = arrangement([segment("22:00", "06:00", 1)], [])
        policy = shared(night)
        policy["exceptions"] = [{"date": "2026-11-03", "dateBasis": "NATURAL_DATE", "target": "BOTH", "action": "CLOSE"}]
        result = expand_calendar_window(policy, start_date="2026-11-02", end_date="2026-11-03")
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "120")
        self.assertNotIn("2026-11-03", result["naturalDays"])

    def test_production_day_closure_removes_entire_cross_midnight_cycle(self):
        night = arrangement([segment("22:00", "06:00", 1)], [])
        policy = shared(night)
        policy["exceptions"] = [{"date": "2026-11-02", "dateBasis": "PRODUCTION_DAY", "target": "BOTH", "action": "CLOSE"}]
        result = expand_calendar_window(policy, start_date="2026-11-02", end_date="2026-11-03")
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["processingIntervals"], [])

    def test_nonexistent_and_ambiguous_local_times_refused(self):
        policy = shared(arrangement([segment("02:15", "04:00")], []), weekdays=("SUN",), timezone="America/New_York")
        result = expand_calendar_window(policy, start_date="2026-03-08", end_date="2026-03-08")
        self.assertIn("NONEXISTENT_LOCAL_TIME", codes(result))
        self.assertFalse(result["ready"])
        policy = shared(arrangement([segment("01:15", "03:00")], []), weekdays=("SUN",), timezone="America/New_York")
        result = expand_calendar_window(policy, start_date="2026-11-01", end_date="2026-11-01")
        self.assertIn("AMBIGUOUS_LOCAL_TIME", codes(result))

    def test_explicit_dst_fold_is_accepted(self):
        value = arrangement([segment("01:15", "03:00", startFold=1)], [])
        result = expand_calendar_window(shared(value, weekdays=("SUN",), timezone="America/New_York"), start_date="2026-11-01", end_date="2026-11-01")
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-01"]["processingMinutes"], "105")

    def test_same_priority_exception_conflicts_refused(self):
        policy = shared()
        policy["exceptions"] = [
            {"date": "2026-11-02", "dateBasis": "NATURAL_DATE", "target": "BOTH", "action": "CLOSE"},
            {"date": "2026-11-02", "dateBasis": "NATURAL_DATE", "target": "PROCESSING", "action": "ADD", "pattern": {"processing": arrangement()}},
        ]
        self.assertIn("EXCEPTION_CONFLICT", codes(normalize_policy_payload("SHARED_ARRANGEMENT", policy)))

    def test_center_stop_cannot_be_opened_by_operation_window(self):
        center = {"mode": "INHERIT", "exceptions": [{"date": "2026-11-02", "dateBasis": "NATURAL_DATE", "target": "RESOURCE", "action": "CLOSE"}]}
        restriction = {"patterns": {"OPEN": {"processing": arrangement([segment("00:00", "24:00")], [])}},
                       "weeklyPatterns": {key: "OPEN" for key in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")}}
        result = resolve_time_window(shared(), center=center, restrictions=[restriction], start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["resourceIntervals"], [])
        self.assertEqual(result["processingIntervals"], [])

    def test_operation_general_and_actual_center_limits_intersect(self):
        def restriction(start, end):
            return {"patterns": {"OPEN": {"processing": arrangement([segment(start, end)], [])}},
                    "weeklyPatterns": {key: "OPEN" for key in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")}}
        result = resolve_time_window(shared(), restrictions=[restriction("11:00", "16:00"), restriction("14:00", "17:00")], start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "120")

    def test_same_center_books_once_different_center_or_company_does_not_conflict(self):
        bookings = {"9:4": [{"start": "2026-11-02T13:00:00+00:00", "end": "2026-11-02T13:30:00+00:00"}]}
        original = deepcopy(bookings)
        same = resolve_time_window(shared(), start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4, bookings=bookings)
        other_center = resolve_time_window(shared(), start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=5, bookings=bookings)
        other_company = resolve_time_window(shared(), start_date="2026-11-02", end_date="2026-11-02", company_id=10, work_center_id=4, bookings=bookings)
        self.assertEqual(same["naturalDays"]["2026-11-02"]["processingMinutes"], "450")
        self.assertEqual(other_center["naturalDays"]["2026-11-02"]["processingMinutes"], "480")
        self.assertEqual(other_company["naturalDays"]["2026-11-02"]["processingMinutes"], "480")
        self.assertEqual(bookings, original)

    def test_explicit_resource_add_does_not_add_processing_capacity(self):
        policy = shared()
        center = {"mode": "INHERIT", "exceptions": [{"date": "2026-11-02", "dateBasis": "NATURAL_DATE",
            "target": "RESOURCE", "action": "ADD", "pattern": {"resource": arrangement([segment("08:30", "09:00")], [])}}]}
        result = resolve_time_window(policy, center=center, start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-02"]["resourceMinutes"], "510")
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "480")

    def test_natural_date_replace_is_complete_not_added_to_old_day(self):
        policy = shared()
        short = arrangement([segment("10:00", "12:00")], [])
        policy["exceptions"] = [{"date": "2026-11-02", "dateBasis": "NATURAL_DATE", "target": "BOTH",
                                 "action": "REPLACE", "pattern": {"processing": short, "resource": short}}]
        result = expand_calendar_window(policy, start_date="2026-11-02", end_date="2026-11-02")
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "120")

    def test_company_production_day_close_not_reopened_by_center_add(self):
        policy = shared(weekdays=())
        policy["exceptions"] = [{"date": "2026-11-02", "dateBasis": "PRODUCTION_DAY", "target": "BOTH", "action": "CLOSE"}]
        short = arrangement([segment("10:00", "12:00")], [])
        center = {"mode": "INHERIT", "exceptions": [{"date": "2026-11-02", "dateBasis": "PRODUCTION_DAY",
            "target": "BOTH", "action": "ADD", "pattern": {"processing": short, "resource": short}}]}
        result = resolve_time_window(policy, center=center, start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["processingIntervals"], [])

    def test_center_exception_cannot_loosen_general_operation_restriction(self):
        first = {"patterns": {"OPEN": {"processing": arrangement([segment("11:00", "16:00")], [])}},
                 "weeklyPatterns": {key: "OPEN" for key in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")}}
        second = {"exceptions": [{"date": "2026-11-02", "dateBasis": "NATURAL_DATE", "target": "PROCESSING", "action": "ADD",
                    "pattern": {"processing": arrangement([segment("09:00", "10:00")], [])}}]}
        result = resolve_time_window(shared(), restrictions=[first, second], start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["naturalDays"]["2026-11-02"]["processingMinutes"], "240")

    def test_operation_no_interruption_cannot_be_loosened_by_capacity_setting(self):
        window = resolve_time_window(shared(), restrictions=[{"interruptible": False}], start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        value = basis()
        value["preparation"] = component(0)
        result = preview_operation_time(window, demand_quantity=100, capacity_quantity=120, basis=value, standard_day_minutes=480,
                                        not_before="2026-11-02T09:00:00+00:00", company_id=9, work_center_id=4)
        self.assertFalse(result["ready"])
        self.assertIn("INSUFFICIENT_LEGAL_TIME_WINDOW", codes(result))

    def test_existing_bookings_cannot_hide_unapproved_longer_processing_day(self):
        extra = arrangement([segment("09:00", "20:00")])
        bookings = {"9:4": [{"start": "2026-11-02T18:00:00+00:00", "end": "2026-11-02T20:00:00+00:00"}]}
        window = resolve_time_window(shared(extra), start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4, bookings=bookings)
        self.assertEqual(window["productionDays"]["2026-11-02"]["processingMinutes"], "480")
        self.assertEqual(window["configuredProductionDays"]["2026-11-02"]["processingMinutes"], "600")
        result = preview_operation_time(window, demand_quantity=60, capacity_quantity=120, basis=basis(), standard_day_minutes=480,
                                        not_before="2026-11-02T09:00:00+00:00", company_id=9, work_center_id=4, bookings=bookings)
        self.assertIn("OVERTIME_CAPACITY_NOT_APPROVED", codes(result))
        self.assertFalse(result["ready"])

    def test_legacy_days_remain_theoretical_and_no_implicit_old_point_one_conversion(self):
        value = basis()
        value["preparation"] = {"clock": "UNRESOLVED", "value": "0.1", "unit": "DAY"}
        result = convert_capacity_time(demand_quantity="78.048", capacity_quantity="500", basis=value, standard_day_minutes="480")
        self.assertEqual(result["productionStandardDays"], "0.156096")
        self.assertIsNone(result["processingMinutes"])
        self.assertIsNone(result["preparation"]["minutes"])
        self.assertIn("TIME_BASIS_UNRESOLVED", codes(result))

    def test_no_standard_day_or_no_linear_authorization_blocks(self):
        self.assertFalse(convert_capacity_time(demand_quantity=60, capacity_quantity=120, basis=basis())["ready"])
        value = basis()
        value["linearApproved"] = False
        result = convert_capacity_time(demand_quantity=60, capacity_quantity=120, basis=value, standard_day_minutes=480)
        self.assertIn("LINEAR_CONVERSION_NOT_APPROVED", codes(result))

    def test_non_linear_mode_is_not_silently_converted(self):
        value = basis()
        value["conversionMode"] = "DISCRETE_BATCH"
        result = convert_capacity_time(demand_quantity=60, capacity_quantity=120, basis=value, standard_day_minutes=480)
        self.assertIn("MODE_NOT_SUPPORTED", codes(result))
        self.assertIsNone(result["processingMinutes"])

    def test_independent_day_components_need_their_own_basis(self):
        value = basis()
        value["preparation"].update(clock="STANDARD_CAPACITY_DAY", value="0.1", unit="DAY")
        result = convert_capacity_time(demand_quantity=60, capacity_quantity=120, basis=value, standard_day_minutes=480)
        self.assertFalse(result["ready"])
        self.assertIsNone(result["preparation"]["minutes"])
        value["preparation"]["standardDayMinutes"] = "300"
        result = convert_capacity_time(demand_quantity=60, capacity_quantity=120, basis=value, standard_day_minutes=480)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["preparation"]["minutes"], "30.0")

    def test_standard_day_wait_does_not_masquerade_as_elapsed_minutes(self):
        value = basis()
        value["transfer"].update(clock="STANDARD_CAPACITY_DAY", value="0.1", unit="DAY", standardDayMinutes="300")
        result = convert_capacity_time(demand_quantity=60, capacity_quantity=120, basis=value, standard_day_minutes=480)
        self.assertFalse(result["ready"])
        self.assertIn("STANDARD_DAY_WAIT_MODE_NOT_SUPPORTED", codes(result))

    def test_normal_sample_full_preview_and_input_booking_isolation(self):
        policy = shared(resource=arrangement([segment("08:30", "18:00")]))
        window = resolve_time_window(policy, start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        bookings = {}
        result = preview_operation_time(window, demand_quantity=60, capacity_quantity=120, basis=basis(), standard_day_minutes=480,
                                        not_before="2026-11-02T08:30:00+00:00", company_id=9, work_center_id=4, bookings=bookings)
        self.assertTrue(result["ready"], result["errors"])
        self.assertEqual(result["start"], "2026-11-02T08:30:00+00:00")
        self.assertEqual(result["end"], "2026-11-02T14:45:00+00:00")
        self.assertEqual([row["minutes"] for row in result["phases"]], ["30", "240.0", "45"])
        self.assertEqual(len(result["bookings"]["9:4"]), 3)
        self.assertEqual(bookings, {})

    def test_incomplete_later_stage_does_not_publish_partial_occupancy(self):
        policy = shared(resource=arrangement([segment("08:30", "18:00")]))
        window = resolve_time_window(policy, start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        value = basis()
        value["transfer"] = component(1000)
        result = preview_operation_time(window, demand_quantity=60, capacity_quantity=120, basis=value, standard_day_minutes=480,
                                        not_before="2026-11-02T08:30:00+00:00", company_id=9, work_center_id=4, bookings={})
        self.assertFalse(result["ready"])
        self.assertEqual(result["phases"], [])
        self.assertEqual(result["bookings"], {})

    def test_forbidden_interruption_does_not_stitch_across_rest(self):
        window = resolve_time_window(shared(), start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        value = basis()
        value["preparation"] = component(0)
        value["processing"]["interruptible"] = False
        result = preview_operation_time(window, demand_quantity=100, capacity_quantity=120, basis=value, standard_day_minutes=480,
                                        not_before="2026-11-02T09:00:00+00:00", company_id=9, work_center_id=4, bookings={})
        self.assertFalse(result["ready"])
        self.assertIn("INSUFFICIENT_LEGAL_TIME_WINDOW", codes(result))

    def test_more_available_processing_time_does_not_authorize_overtime_capacity(self):
        extra = arrangement([segment("09:00", "20:00")])
        window = resolve_time_window(shared(extra), start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        result = preview_operation_time(window, demand_quantity=60, capacity_quantity=120, basis=basis(), standard_day_minutes=480,
                                        not_before="2026-11-02T09:00:00+00:00", company_id=9, work_center_id=4, bookings={})
        self.assertIn("OVERTIME_CAPACITY_NOT_APPROVED", codes(result))
        self.assertFalse(result["ready"])

    def test_window_scope_mismatch_refused(self):
        window = resolve_time_window(shared(), start_date="2026-11-02", end_date="2026-11-02", company_id=9, work_center_id=4)
        result = preview_operation_time(window, demand_quantity=60, capacity_quantity=120, basis=basis(), standard_day_minutes=480,
                                        not_before="2026-11-02T09:00:00+00:00", company_id=10, work_center_id=4)
        self.assertIn("RESOURCE_SCOPE_MISMATCH", codes(result))


if __name__ == "__main__":
    unittest.main()
