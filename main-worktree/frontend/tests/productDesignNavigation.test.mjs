import assert from 'node:assert/strict'
import {designOrderQuery,designNavigationTarget} from '../src/meta/runtime/productDesignNavigation.js'
const context={orderNo:'A',companyId:'1',salesOrderId:'5',salesOrderItemId:'8',orderEngineeringInstanceId:'7',sourceRecordId:'15',sourceVersion:'1',authorizationId:'2',baselineId:'6',debug:'no'}
assert.deepEqual(designOrderQuery(context,'B'),{orderNo:'B'})
assert.deepEqual(designOrderQuery(context,''),{})
assert.deepEqual(designOrderQuery({},'B'),{orderNo:'B'})
const same=designOrderQuery(context,'A');assert.equal(same.sourceRecordId,'15');assert.equal(same.authorizationId,'2');assert.equal(same.baselineId,undefined);assert.equal(same.debug,undefined)
const target={label:'产品版本管理',pageCode:'pde-product-versions',pageUrl:'/pde/product-versions'}
assert.equal(designNavigationTarget('finance',context,target),target)
assert.equal(designNavigationTarget('pde-product-definitions',{},target).pageUrl,target.pageUrl)
assert.equal(new URLSearchParams(designNavigationTarget('pde-product-definitions',context,target).pageUrl.split('?')[1]).get('orderNo'),'A')
const unrelated={label:'评审',pageUrl:'/pde/product-requirement-reviews'};assert.equal(designNavigationTarget('pde-product-definitions',context,unrelated),unrelated)
assert.equal(designNavigationTarget('pde-product-versions',context,{pageUrl:'/pde/product-definitions'}).pageUrl.includes('orderEngineeringInstanceId=7'),true)
console.log('PASS: 12 navigation isolation assertions; unrelated shell targets unchanged')
