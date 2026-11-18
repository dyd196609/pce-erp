"""Regression for the complete URL registration and real API response contract."""
import io
import json
from pathlib import Path

from django.urls import resolve
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook

from .tests_organization_import_v1 import OrganizationImportV1Tests
from .organization_import_service import OrganizationImportService


class OrganizationImportRuntimeTests(OrganizationImportV1Tests):
    def test_all_registered_handlers_and_http_file_preview_commit_chain(self):
        self.client.force_authenticate(user=self.admin)
        out = Path(__file__).resolve().parents[2] / 'docs/evidence/pce-dual-entry-template-runtime-20260915/isolated-api-files'
        out.mkdir(parents=True, exist_ok=True)
        cases = {
            'departments': ['HTTP-D', '隔离接口部门', self.company.code, '职能部门', '', '', '', '', '', '启用'],
            'positions': ['HTTP-P', '隔离接口岗位', self.company.code, 'HTTP-D', '', '', '', '', '', '', '', '', '启用'],
            'employees': ['HTTP-E', '隔离接口员工', self.company.code, 'HTTP-D', 'HTTP-P', '在职', '', '', '', ''],
        }
        evidence=[]
        for entity, row in cases.items():
            base='/api/access-control/organization-import/'+entity+'/'
            for action, cls in [('template','OrganizationImportTemplateView'),('preview','OrganizationImportPreviewView'),('commit','OrganizationImportCommitView')]:
                self.assertEqual(resolve(base+action+'/').func.view_class.__name__, cls)
            response=self.client.get(base+'template/')
            self.assertEqual(response.status_code,200)
            self.assertIn('spreadsheetml.sheet',response['Content-Type'])
            self.assertIn('attachment;',response['Content-Disposition'])
            self.assertTrue(response.content.startswith(b'PK'))
            workbook=load_workbook(io.BytesIO(response.content))
            sheet=workbook[OrganizationImportService.schema(entity)['sheet']]
            self.assertEqual(sheet.max_row,1)
            self.assertEqual(set(workbook.sheetnames),{sheet.title,'填写说明','引用资料'})
            self.assertEqual(workbook['引用资料']['B2'].value,self.company.code)
            (out/(entity+'-isolated-template.xlsx')).write_bytes(response.content)
            sheet.append(row)
            stream=io.BytesIO(); workbook.save(stream); content=stream.getvalue()
            def upload():
                return SimpleUploadedFile(entity+'.xlsx',content,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            preview=self.client.post(base+'preview/',{'file':upload()},format='multipart')
            self.assertEqual(preview.status_code,200,preview.data)
            data=preview.data['data']
            self.assertTrue(data['canCommit'],data)
            saved=self.client.post(base+'commit/',{'file':upload(),'confirmed':'true','previewFingerprint':data['previewFingerprint'],'previewActorBinding':json.dumps(data['previewActorBinding']),'idempotencyKey':'http-'+entity},format='multipart')
            self.assertEqual(saved.status_code,200,saved.data)
            self.assertEqual(saved.data['data']['created'],1)
            repeated=self.client.post(base+'preview/',{'file':upload()},format='multipart')
            self.assertEqual(repeated.data['data']['counts']['match'],1)
            evidence.append({'entity':entity,'template':200,'preview':200,'confirm':200,'createdInTestDatabase':1,'repeatMatch':1,'blankInput':True,'sheetNames':workbook.sheetnames,'headers':[c.value for c in sheet[1]]})
        (out/'VALIDATION.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
