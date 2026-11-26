"""Close this continuation with truthful gates and sealed read-only evidence."""
import collections
import sys
from pathlib import Path
from native_supplement_closure import ROOT, RUN, RUN_SHA, verify, p
from technical_closure import database_snapshot


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    _, _, plan, _, _ = verify()
    m = p.load_manifest()
    audit = Path(m['revision']['audit']).parent
    summary = p.read(audit / 'SUMMARY.json')
    p.verify_hashes(p.read(audit / 'AUDIT_MANIFEST.json')['files'], audit)
    p.require(p.digest(audit/'SUMMARY.json') == m['revision']['audit_sha'], 'AUDIT SUMMARY DRIFT')
    pre = Path(sys.argv[1])
    precheck = p.read(pre/'PACKAGE_PRECHECK.json')
    p.require(precheck['status'] == 'PASS', 'FULL PACKAGE PRECHECK REQUIRED')
    p.require(precheck['package_manifest_sha'] == p.digest(p.ROOT/'RUNNER_MANIFEST.json'), 'TESTED != PACKAGED')
    p.require(precheck['tested_files'] == m['files'], 'TESTED FILE SET DRIFT')
    p.verify_hashes(p.read(pre/'RUN_MANIFEST.json')['files'], pre)
    p.require(p.read(pre/'NATIVE_EXCEL_RUN.json')['execution_status'] == 'NOT_EXECUTED', 'PRECHECK IS NOT NATIVE EXECUTION')
    for name in ('reference_runtime.py', 'generated_reference.py', 'differential.py', 'formula_ast.py', 'workbook_source.py'):
        path = str(Path(m['reference_directory']) / name)
        p.require(p.digest(path) == summary['code_hashes'][path], 'AUDITED SEMANTIC CODE != DELIVERED CODE')
    register = p.read(audit/'BROKEN_FAMILY_RECOVERY_REGISTER.json')
    source = p.read(ROOT/'SOURCE_EXHAUSTION_AND_ADJUDICATION.json')
    outputs = p.read(audit/'SUPPLEMENT_OUTPUT_MATRIX.json')['results']
    real_ids = {c['case_id'] for c in plan['cases'] if c['cohort'] == 'RECOVERY_CANDIDATE_ONLY' and c['real_source_row'] is not None}
    for item in register:
        if item['status'] == 'NATIVE_VERIFIED_CANDIDATE_NOT_BUSINESS_FORMALIZED':
            rows = [r for r in outputs if r['candidate_family'] == item['family_id'] and r['case_id'] in real_ids]
            item.update(confidence='MEDIUM_CONFIDENCE', confidence_factors={'structure_match':'AREA_BUCKET_STRUCTURE_MATCH', 'input_match':'SOURCE_J_K_L_M_TO_HOMOLOG_E_F_G_H', 'output_match':'NATIVE_REFERENCE_PASS_NOT_HISTORICAL_BUSINESS_PROOF', 'branch_match':'ORIGINAL_LENGTH_THICKNESS_CONDITIONS_PRESERVED; GUARD_VARIANTS_EXPLAINED', 'neighbor_formula_match':'SAME_NEIGHBOR_STRUCTURE_BUT_NEIGHBOR_REFERENCES_ALSO_BROKEN', 'historical_result_match':'NO_INDEPENDENT_MATCHED_HISTORICAL_OUTPUT_FOUND', 'BOM_structure_match':'PRODUCT_COMPONENT_AREA_ROLE_CONSISTENT; NO_NUMERIC_AUTHORITY'}, source_guard_decision='PRESERVE_EXISTING_S_AREA_GUARD; DO_NOT_COPY_UNGUARDED_T_OVER_S', real_input_candidate_outputs=len(rows), real_input_positive_native_outputs=[{'cell':r['candidate_source_cell'],'value':r['excel_raw_value']} for r in rows if r['excel_raw_value']['type']=='number' and r['excel_raw_value']['value'] != 0], recovered_verified=False)
        else:
            addr = item['source_cells'][0]
            qid = 'U03-01' if addr.startswith('房门单!') else 'U03-03' if addr.endswith('!AV30') else 'U03-04' if addr.endswith('!AV31') else 'U03-02'
            item.update(status='USER_DECISION_REQUIRED', escalation=qid, user_decision_requested=True, confidence='LOW_CONFIDENCE_NO_UNIQUE_FORMULA', recovered_verified=False)
    target = ROOT/'FINAL_RECOVERY_REGISTER.json'
    p.require(not target.exists(), 'APPEND-ONLY DELIVERY REGISTER')
    p.write(target, {'families':register,'counts':dict(collections.Counter(r['status'] for r in register)), 'source_broken_families_still_unchanged':51,'business_verified_recovered':0,'user_questions':source['user_decisions']})
    before = summary['production_after']
    after = database_snapshot()
    p.require(before == after, 'PRODUCTION REGRESSION')
    gate = {'A_all_eligible_closed':summary['level1_all_eligible_pass'],'B_initial_13_classified':sum(summary['dependency_classifications'].values()) == 13,'C_all_real_row_eligible_outputs_native_compared':set(summary['real_counts']) <= {'PARITY_PASS','BROKEN_SOURCE'},'D_all_51_recovery_objects_accounted':len(register)==51}
    p.require(all(gate.values()), 'CURRENT STAGE STOP GATE NOT MET')
    result = {'timestamp':p.now(),'continuation':True,'original_instruction_overall':'NOT_COMPLETED','stage_stop_gates':gate,'current_stop':'U03_BUSINESS_IDENTITY_AGGREGATION_AND_UNIT_DECISIONS; NO_DOMAIN_FORMALIZATION','native_run':str(RUN),'native_manifest_sha':RUN_SHA,'run_preserved':True,'audit':str(audit),'summary':summary,'package_version':m['package_version'],'package_manifest_sha':p.digest(p.ROOT/'RUNNER_MANIFEST.json'),'precheck':str(pre),'python_tests':precheck['unit_test_count'],'powershell_tests':precheck['powershell_contract_test_count'],'tested_code_equals_packaged_code':True,'collector_change_native_executed':False,'native_error_identity_gaps':44,'gaps_are_ancillary_not_real_row_or_level1':True,'global_excel_compatibility_claim':False,'new_native_run_requested_now':False,'production':after,'writes':{'business':0,'REAL_rule':0,'BOM':0,'capacity':0,'planning':0,'production_batch':0,'migration':0,'source_excel':0},'ui_changes':0,'ui_gate':'NOT_APPLICABLE','domain_formalization':'NOT_ENTERED','U01':'NOT_TRIGGERED','U02':'NOT_TRIGGERED','U03':{'questions':4,'families':15},'U04':'NOT_TRIGGERED','recovery_register_sha':p.digest(target),'source_exhaustion_sha':p.digest(ROOT/'SOURCE_EXHAUSTION_AND_ADJUDICATION.json'),'self_script_sha':p.digest(__file__)}
    p.require(not (ROOT/'FINAL_DELIVERY_AUDIT.json').exists(), 'APPEND-ONLY DELIVERY AUDIT')
    p.write(ROOT/'FINAL_DELIVERY_AUDIT.json',result)
    print(__import__('json').dumps({'file':str(ROOT/'FINAL_DELIVERY_AUDIT.json'),'sha':p.digest(ROOT/'FINAL_DELIVERY_AUDIT.json'),'tests':[result['python_tests'],result['powershell_tests']],'gates':gate,'recovery_counts':dict(collections.Counter(r['status'] for r in register))},ensure_ascii=False))


if __name__ == '__main__':
    main()
