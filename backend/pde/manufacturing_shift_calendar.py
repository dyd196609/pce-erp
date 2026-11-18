"""Use native Shift + WorkCenter.capacity_policy; no parallel calendar store."""
from hashlib import sha256
import json
from pfm.models import Shift
CONTRACT='PCE-SHIFT-CALENDAR-SOURCE-V1'
DAYS=('MON','TUE','WED','THU','FRI','SAT','SUN')
def shift_snapshot(shift):
 return {k:str(getattr(shift,k)) for k in ('id','company_id','code','name','start_time','end_time','break_start','break_end','is_active')}
def fingerprint(shift):
 return sha256(json.dumps(shift_snapshot(shift),sort_keys=True).encode()).hexdigest()
def available_minutes(shift):
 def minutes(t):
  if t is None or t.second or t.microsecond:raise ValueError('班次时间必须为明确分钟')
  return t.hour*60+t.minute
 start,end=minutes(shift.start_time),minutes(shift.end_time)
 if end<=start:end+=1440
 total=end-start
 if bool(shift.break_start)!=bool(shift.break_end):raise ValueError('休息开始及结束必须成对维护')
 if shift.break_start:
  left,right=minutes(shift.break_start),minutes(shift.break_end)
  if left<start:left+=1440
  if right<=left:right+=1440
  if not start<=left<right<=end:raise ValueError('休息时间不在班次范围内')
  total-=right-left
 if not 0<total<=1440:raise ValueError('班次有效工作分钟无效')
 return total
def build_shift_calendar(*,shift,weekdays,exceptions,basis_label,usage_purpose):
 if not shift.is_active or not isinstance(weekdays,list) or not weekdays or any(type(d) is not str for d in weekdays) or len(set(weekdays))!=len(weekdays) or set(weekdays)-set(DAYS):raise ValueError('班次及周工作日配置无效')
 if usage_purpose!='TEST_BUSINESS' or not basis_label:raise ValueError('此生成器只承接明确测试依据')
 count=available_minutes(shift)
 return {'contractVersion':'PCE-MFG-CALENDAR-V1.0','timezone':'Asia/Shanghai','weeklyAvailableMinutes':{d:count if d in weekdays else 0 for d in DAYS},'exceptions':exceptions,'workSystemSource':{'contractVersion':CONTRACT,'shiftId':shift.pk,'sourceHash':fingerprint(shift),'workingWeekdays':weekdays,'basisLabel':basis_label,'usagePurpose':usage_purpose}}
def validate_shift_calendar(*,work_center,calendar):
 source=calendar.get('workSystemSource')
 if source is None:return None
 if not isinstance(source,dict) or source.get('contractVersion')!=CONTRACT or source.get('usagePurpose')!='TEST_BUSINESS' or type(source.get('shiftId')) is not int or source['shiftId']<=0:raise ValueError('班次日历来源合同或用途无效')
 shift=Shift.objects.filter(pk=source.get('shiftId'),company_id=work_center.company_id,is_active=True).first()
 if shift is None or fingerprint(shift)!=source.get('sourceHash'):raise ValueError('班次来源不存在、越公司或已修订，须重新生成日历关联')
 expected=build_shift_calendar(shift=shift,weekdays=source.get('workingWeekdays'),exceptions=calendar.get('exceptions'),basis_label=source.get('basisLabel'),usage_purpose=source.get('usagePurpose'))
 if calendar.get('weeklyAvailableMinutes')!=expected['weeklyAvailableMinutes']:raise ValueError('周可用分钟与班次制度不一致')
 return {**source,'shiftCode':shift.code,'shiftName':shift.name,'dailyAvailableMinutes':available_minutes(shift),'sourceValidated':True}
