from datetime import date
from decimal import Decimal
from django.test import SimpleTestCase
from .daily_capacity_service import DailyCapacityError, duration_days, working_date_window


class DailyCapacityDateTests(SimpleTestCase):
    def calendar(self, **kw):
        return {"contractVersion":"PCE-MFG-CALENDAR-V1.0", "timezone":"Asia/Shanghai",
                "weeklyAvailableMinutes":dict(MON=480,TUE=480,WED=480,THU=480,FRI=480,SAT=0,SUN=0),
                "exceptions":[], **kw}

    def duration(self, **kw):
        return duration_days(**dict(demand_quantity="198", capacity_quantity="99", demand_uom_id=1,
                                    capacity_uom_id=1, preparation_days="0.5", transfer_days="0.25", **kw))

    def test_quantity_per_day_plus_explicit_day_times(self):
        facts=self.duration()
        self.assertEqual(Decimal(facts["productionDays"]),2)
        self.assertEqual(Decimal(facts["durationDays"]),Decimal("2.75"))
        self.assertNotIn("durationHours",facts)

    def test_missing_times_are_not_assumed_zero(self):
        for field in ("preparation_days","transfer_days"):
            values=dict(demand_quantity=1,capacity_quantity=1,demand_uom_id=1,capacity_uom_id=1,preparation_days=0,transfer_days=0)
            values[field]=None
            with self.assertRaises(DailyCapacityError):duration_days(**values)

    def test_unit_mismatch_never_converts_pieces_to_area(self):
        with self.assertRaises(DailyCapacityError) as caught:
            duration_days(demand_quantity=1,capacity_quantity=99,demand_uom_id=1,capacity_uom_id=2,preparation_days=0,transfer_days=0)
        self.assertEqual(caught.exception.code,"CAPACITY_UOM_MISMATCH")

    def test_zero_or_negative_capacity_is_not_available(self):
        for capacity in (0,-1,"NaN","Infinity"):
            with self.assertRaises(DailyCapacityError):
                duration_days(demand_quantity=1,capacity_quantity=capacity,demand_uom_id=1,capacity_uom_id=1,preparation_days=0,transfer_days=0)

    def test_explicit_zero_day_times_are_preserved(self):
        result=duration_days(demand_quantity="0.5",capacity_quantity=1,demand_uom_id=1,capacity_uom_id=1,preparation_days="0",transfer_days="0")
        self.assertEqual(result['durationDays'],'0.5')

    def test_weekend_and_fractional_workdays(self):
        result=working_date_window(start_date=date(2026,10,16),duration="2.75",calendar=self.calendar())
        self.assertEqual(result['startDate'],'2026-10-16')
        self.assertEqual(result['endDate'],'2026-10-20')
        self.assertEqual([r['allocatedDays'] for r in result['allocations']],['1','1','0.75'])

    def test_resource_cannot_be_booked_twice_on_same_day(self):
        bookings={}
        first=working_date_window(start_date=date(2026,10,13),duration="1.5",calendar=self.calendar(),daily_bookings=bookings)
        second=working_date_window(start_date=date(2026,10,13),duration="1",calendar=self.calendar(),daily_bookings=bookings)
        self.assertEqual(first['endDate'],'2026-10-14')
        self.assertEqual(second['startDate'],'2026-10-14')
        self.assertEqual(second['endDate'],'2026-10-15')
        self.assertTrue(all(Decimal(v)<=1 for v in bookings.values()))

    def test_date_exception_closed_day_is_respected(self):
        cal=self.calendar(exceptions=[{'date':'2026-10-13','availableMinutes':0}])
        result=working_date_window(start_date=date(2026,10,13),duration=1,calendar=cal)
        self.assertEqual(result['startDate'],'2026-10-14')

    def test_missing_calendar_cannot_create_dates(self):
        with self.assertRaises(DailyCapacityError):
            working_date_window(start_date=date(2026,10,13),duration=1,calendar={})

    def test_failed_horizon_does_not_partially_book_resource(self):
        bookings={'2026-10-13':'0.25'}
        with self.assertRaises(DailyCapacityError):
            working_date_window(start_date=date(2026,10,13),duration=100,calendar=self.calendar(),daily_bookings=bookings,horizon_days=1)
        self.assertEqual(bookings,{'2026-10-13':'0.25'})

    def test_duplicate_calendar_exception_is_rejected(self):
        cal=self.calendar(exceptions=[{'date':'2026-10-13','availableMinutes':480},{'date':'2026-10-13','availableMinutes':0}])
        with self.assertRaises(DailyCapacityError):working_date_window(start_date=date(2026,10,13),duration=1,calendar=cal)
