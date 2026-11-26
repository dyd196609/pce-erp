"""Bind genuine U03 data gaps to unchanged source-exhaustion evidence."""
from recovery_native_r4 import OUT, p, save, snapshot


def main():
    previous=OUT.parent/'native-supplement-r2/SOURCE_EXHAUSTION_AND_ADJUDICATION.json'
    exhausted=p.read(previous)
    verified=[]
    for row in exhausted['sources']:
        p.require(p.digest(row['path'])==row['sha256'],'PREVIOUS SOURCE SEARCH STALE')
        verified.append({'path':row['path'],'sha':row['sha256']})
    structure=exhausted['structure']
    p.require(p.digest(structure['path'])==structure['sha'],'STRUCTURE SEARCH STALE')
    snapshot()  # Read-only, current DB must still equal the original SHA.
    board=p.read(OUT.parent/'recovery-u03/BOARD_STOCK_AND_REAL_ROW_AUDIT.json')
    gaps=[
        {'id':'U03-R4-01','type':'MATERIAL_APPLICABILITY_AND_EXACT_SPEC','status':'PENDING_USER_SOURCE_FACT',
         'affected':'63 tri rows: 31 geometric candidates without approved material; 32 no exact-thickness spec',
         'question':'这些部件分别适用哪种正式板材（材质及物料编码）？22/24/25/28厚度的实际供料规格是什么；属于组合结构时请给部件/材料关系，不以外包尺寸直接选一张板。',
         'evidence':'Source design material=实木多层板; row7 has 30 equal-size IDs; row31 geometric ID171=OSB; active thickness gaps 22/24/25/28.',
         'forbidden_inference':['nearest thickness','1.8 automatically converted to18','pick first ID','invent composite construction'],
         'source_rows':board['rows']},
        {'id':'U03-R4-02','type':'VISIBLE_AND_EDGE_APPLICABILITY','status':'PENDING_USER_SOURCE_FACT',
         'question':'三合一第36行“图7餐边柜/格栅屏风”的见光方式及封边方式是什么？第9、60、68行“辅助板”是否封边、封哪些边？',
         'evidence':'O36 missing; P9/P36/P60/P68 missing. Native known-area subtotal does not fill these facts.',
         'forbidden_inference':['blank equals no veneer','blank equals no edge banding','zero business requirement from missing condition']},
        {'id':'U03-R4-03','type':'EDGE_MATERIAL_AND_ALLOWANCE_POLICY','status':'PENDING_USER_SOURCE_FACT',
         'question':'实际封边条物料/宽厚/颜色及每边预留毫米数如何确定；是否存在可读取的已确认企业参数？',
         'evidence':'No formal allowance value supplied. 20mm/0mm test fixtures are not approved parameters.',
         'forbidden_inference':['use synthetic20mm as real','missing allowance equals0','use unified percentage instead of edge allowance']}
    ]
    save('BUSINESS_GAPS_U01_U04.json',{'previous_exhaustion_evidence':str(previous),'previous_exhaustion_sha':p.digest(previous),
        'unchanged_sources_reverified':verified,'structure_reverified':structure['path'],'db_unchanged':True,
        'source_search_scope':'Existing registered engineering copies, 05/08/10/12/13, formula families/homologs, engineering structure, formal material/rules/history; no global knowledge claim',
        'original_U03_01_through_04':'RESOLVED; NOT_REOPENED','U01':'NOT_TRIGGERED; structural ambiguity remains in-scope U03, no new structural model proposed',
        'U02':'NOT_TRIGGERED; no verified historical business oracle contradicts the restored ledger',
        'U03':gaps,'direction_new_U03':0,'U04':'NOT_TRIGGERED; no positive evidence to classify any actual row as random/manual; target channels preserved',
        'native_runner_error':'TECHNICAL_ONLY; not a user business decision',
        'immediate_user_action':'One ordinary double-click of fully prechecked 191-case suffix; business data decisions independent and not auto-written',
        'production_write':0,'domain_formalization':'NOT_ENTERED'})
    print('Three bounded U03 data-gap groups recorded; original four decisions remain closed.')


if __name__=='__main__': main()
