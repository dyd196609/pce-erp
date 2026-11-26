"""Specific regressions for the user's KLG / PPG / MGC preview and shared refs."""
import io
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from openpyxl import load_workbook

from .models import Company, Department, Position, User
from .organization_import_service import OrganizationImportService as Service
from .tests_organization_import_v1 import NamedBytesIO


class OrganizationReferenceTests(TestCase):
    def test_http_target_context_and_chinese_report_use_original_guard(self):
        from rest_framework.test import APIClient
        from django.core.files.uploadedfile import SimpleUploadedFile
        client=APIClient()
        base='/api/access-control/organization-import/departments/'
        self.assertIn(client.get(base+'template/?context=1').status_code,(401,403))
        client.force_authenticate(user=self.user)
        response=client.get(base+'template/?context=1')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data['data']['allowed'])
        content=self.file('departments',[['KLG','开料工序','错误公司','生产部门','','','','','','启用']])
        response=client.post(base+'preview/?report=xlsx',{'file':SimpleUploadedFile('部门.xlsx',content)},format='multipart')
        self.assertEqual(response.status_code,200)
        workbook=load_workbook(io.BytesIO(response.content))
        self.assertEqual(workbook['导入校验报告']['D2'].value,'所属公司')

    @classmethod
    def setUpTestData(cls):
        cls.company=Company.objects.create(code='COMP001',name='引用隔离公司')
        cls.other=Company.objects.create(code='REF-O',name='其他引用公司')
        cls.user=User.objects.create_superuser(username='reference_test',password=None,company_id=cls.company.pk)
        cls.root=Department.objects.create(company=cls.company,code='SCB',name='生产部')
        cls.parent=Department.objects.create(company=cls.company,code='MGC',name='木工车间',parent=cls.root,department_type='PRODUCTION',effective_from=date(2026,9,14),effective_to=date(2027,9,14))

    def file(self,entity,rows,old=False):
        wb=load_workbook(io.BytesIO(Service.template_bytes(entity,user=self.user)))
        ws=wb[Service.schema(entity)['sheet']]
        if old:
            for index,item in enumerate(Service.schema(entity)['fields'],1): ws.cell(1,index,item['aliases'][0])
        for row in rows: ws.append(row)
        out=io.BytesIO();wb.save(out);return out.getvalue()

    def preview(self,entity,rows,old=False):
        content=self.file(entity,rows,old)
        return Service.preview(entity,uploaded_file=NamedBytesIO(content,entity+'.xlsx'),user=self.user)[0]

    def test_company_name_and_old_headers_existing_parent_match(self):
        rows=[['KLG','开料工序',self.company.name,'生产部门','木工车间','','待维护','','','启用'],
              ['PPG','拼皮工序',self.company.name,'生产部门','MGC','','','','','启用'],
              ['MGC','木工车间',self.company.name,'生产部门','SCB','','待维护','2026-09-14','2027-09-14','启用']]
        data=self.preview('departments',rows,True)
        self.assertFalse(data['canCommit'])
        self.assertEqual(data['counts']['create'],0)
        self.assertEqual(data['counts']['reference'],1)
        self.assertEqual(data['counts']['excluded'],2)
        self.assertEqual(data['rows'][0]['decision'],'EXCLUDED')
        self.assertEqual(data['rows'][1]['decision'],'EXCLUDED')
        self.assertEqual(data['rows'][2]['decision'],'REFERENCE')
        self.assertEqual(data['rows'][2]['existingId'],self.parent.pk)
        self.assertEqual(data['rows'][0]['data']['parent_code'],'MGC')
        self.assertEqual(data['rows'][0]['rawData']['responsible_position_code'],'待维护')

    def test_unresolved_company_defers_downstream_instead_of_false_missing(self):
        data=self.preview('departments',[['KLG','开料工序','不存在的公司','生产部门','MGC','开料工序','待维护','','','启用']])
        self.assertEqual([e['errorType'] for e in data['errors']],['TARGET_COMPANY_UNRESOLVED'])
        self.assertIn('暂无法校验',data['rows'][0]['normalizations'][0]['message'])
        self.assertEqual(data['counts']['create'],0)

    def test_cross_company_authorization_does_not_override_canonical_write_scope(self):
        data=self.preview('departments',[['D','部门',self.other.name,'生产部门','','','','','','启用']])
        self.assertFalse(data['canCommit'])
        self.assertEqual(data['counts']['blocked'],1)
        with patch('system.organization_import_service.AuthorizationService.decide',return_value={'allowed':False,'reason':'测试拒绝'}):
            self.assertFalse(Service.target_context('departments',self.user)['allowed'])

    def test_name_code_ambiguity_and_same_file_failed_dependency(self):
        Department.objects.create(company=self.company,code='木工车间',name='另一个部门')
        data=self.preview('departments',[['OTHER','其他生产组',self.company.code,'生产部门','木工车间','','','','','启用']])
        self.assertIn('REFERENCE_AMBIGUOUS',[e['errorType'] for e in data['errors']])
        data=self.preview('departments',[
            ['NEW-CHILD','子部门',self.company.code,'生产部门','BAD-P','','','','','启用'],
            ['BAD-P','错误上级',self.company.code,'错误类型','','','','','','启用']])
        self.assertEqual(data['counts']['blocked'],2)

    def test_existing_differences_dates_and_optional_relations_not_overwritten(self):
        data=self.preview('departments',[['MGC','木工车间',self.company.code,'生产部门','SCB','','待维护','2026-09-14','2076-09-14','启用']])
        self.assertEqual(data['counts']['review'],0)
        self.assertEqual(data['counts']['reference'],1)
        self.assertEqual(data['errors'],[])
        difference=data['rows'][0]['differences'][0]
        self.assertEqual(difference['fieldLabel'],'失效日期')
        self.assertEqual(difference['existingValue'],'2027-09-14')
        self.assertEqual(data['rows'][0]['normalizations'][-1]['rawValue'],'2076-09-14')
        self.parent.refresh_from_db();self.assertEqual(self.parent.effective_to,date(2027,9,14))
        report=load_workbook(io.BytesIO(Service.error_report_bytes(data)))
        ws=report['导入校验报告']
        report_fields=[ws.cell(row,4).value for row in range(2,ws.max_row+1)]
        self.assertIn('本次业务裁决',report_fields)
        self.assertIn('失效日期',report_fields)
        self.assertTrue(ws['H2'].alignment.wrap_text)
        self.assertGreater(ws.row_dimensions[2].height,30)
        self.assertEqual(report['技术明细'].sheet_state,'hidden')

    def test_position_employee_references_resolve_names_and_preserve_no_account_write(self):
        position=Position.objects.create(company=self.company,department=self.parent,code='REF-P',name='引用岗位')
        data=self.preview('positions',[['REF-P2','新岗位',self.company.name,'木工车间','','','','','','','','','启用']])
        self.assertTrue(data['canCommit'],data['errors'])
        data=self.preview('employees',[['REF-E','隔离员工',self.company.name,'木工车间',position.name,'在职','','','','']])
        self.assertTrue(data['canCommit'],data['errors'])
        self.assertEqual(data['rows'][0]['data']['position_code'],'REF-P')
        self.assertNotIn('userId',Service._payload('employees',data['rows'][0]['data'],self.company.pk))
