import { timedMesRead } from '@/meta/runtime/mesReadTiming.js'
import request from './request'
export const finishedGoodsApi={read:params=>timedMesRead(()=>request({method:'GET',url:'/api/planning/finished-goods-handovers/',params,timeout:300000,meta:{module:'MES',readOnly:true}}),'/api/planning/finished-goods-handovers/'),execute:(action,payload)=>request({method:'POST',url:action.apiPath,data:payload,timeout:300000,meta:{module:'MES'}})}
