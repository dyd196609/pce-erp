from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import DesignRevisionApproval,ProductDesignRevision
from .product_design_service import ProductDesignError
from . import design_revision_approval_service as service

def actions(user,obj=None):
    from system.authorization import AuthorizationService
    specs=[('submit','提交当前精确修订','submit',None),('approve','批准资料','approve','pending'),('reject','拒绝资料','approve','pending'),('successor','生成获准后继修订','submit','approved'),('revoke','撤销资料批准','revoke','approved')]
    result=[]
    for action,label,permission,state in specs:
        if state is not None and (obj is None or obj.status!=state):continue
        if state is None and obj is not None:continue
        decision=AuthorizationService.decide(user=user,action_code=service.PREFIX+permission,organization_id=user.company_id,business_object={'organizationId':user.company_id})
        result.append({'action':action,'label':label,'permission':service.PREFIX+permission,'available':bool(decision['allowed'] and not (action in ('approve','reject') and obj and obj.applicant_id==user.pk))})
    return result

def row(obj,user):
    successor=ProductDesignRevision.objects.filter(approval=obj).first()
    return {'actions':actions(user,obj),'id':obj.pk,'statusLabel':{'pending':'待批准','approved':'已批准','rejected':'已拒绝','revoked':'已撤销'}.get(obj.status,'状态未知'),'contentHash':obj.content_hash,'scopeLabel':'测试业务批准' if obj.approval_scope=='TEST_BUSINESS' else '生产业务批准','originNatureLabel':dict(ProductDesignRevision.DESIGN_NATURE_CHOICES).get(obj.origin_nature,'来源性质待核对'),'originNature':obj.origin_nature,'sourceRevisionId':obj.source_revision_id,'sourceRevision':obj.source_revision.revision,'sourceRecordId':obj.source_record_id,'sourceVersion':obj.source_version,'applicant':obj.applicant.real_name,'workflowInstanceId':obj.workflow_instance_id,'decisionId':obj.final_decision_id,'successorRevision':successor.revision if successor else None,'successorRevisionId':successor.pk if successor else None}

class DesignRevisionApprovalView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        revision_id=request.query_params.get('revisionId')
        if not revision_id:return Response({'error':{'message':'请选择精确设计修订。'}},status=400)
        revision=ProductDesignRevision.objects.select_related('design_item').filter(pk=revision_id,design_item__company_id=request.user.company_id).first()
        if not revision:return Response({'error':{'message':'修订不属于当前公司。'}},status=404)
        from .product_version_management_service import _content_snapshot
        return Response({'contentHash':service.digest(_content_snapshot(revision.design_item,revision)),'rows':[row(x,request.user) for x in DesignRevisionApproval.objects.filter(Q(source_revision=revision)|Q(pk=revision.approval_id),company_id=request.user.company_id).order_by('-pk')],'sourceRevisionId':revision.pk,'actions':actions(request.user)})
    def post(self,request):
        data=request.data;key=request.headers.get('Idempotency-Key');action=data.get('action')
        try:
            allowed={'action','instanceContext','revisionId','contentHash'} if action=='submit' else {'action','approvalId','contentHash','reason'}
            if set(data)-allowed:
                raise ProductDesignError('DESIGN_APPROVAL_INPUT_NOT_ALLOWED','不得替换获准内容或自行指定批准用途。',409)
            if action=='submit':obj,replay=service.submit(request.user,data.get('instanceContext') or {},data.get('revisionId'),data.get('contentHash'),key)
            elif action in ('approve','reject'):obj,replay=service.decide(request.user,data.get('approvalId'),'approved' if action=='approve' else 'rejected',data.get('contentHash'),str(data.get('reason') or ''),key)
            elif action=='revoke':obj,replay=service.revoke(request.user,data.get('approvalId'),str(data.get('reason') or ''),key)
            elif action=='successor':
                revision,replay=service.create_successor(request.user,data.get('approvalId'),key);obj=revision.approval
            else:raise ProductDesignError('DESIGN_APPROVAL_ACTION_INVALID','资料批准动作无效。')
            return Response({'success':True,'idempotentReplay':replay,'approval':row(obj,request.user)})
        except ProductDesignError as exc:return Response({'error':{'code':exc.code,'message':exc.message}},status=exc.http_status)
        except (ValueError, TypeError):return Response({"error":{"code":"DESIGN_APPROVAL_INPUT_INVALID","message":"申请标识或输入格式无效。"}},status=400)
        except DesignRevisionApproval.DoesNotExist:return Response({'error':{'code':'DESIGN_APPROVAL_NOT_FOUND','message':'批准申请不属于当前公司。'}},status=404)
