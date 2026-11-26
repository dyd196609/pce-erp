"""Bounded source exhaustion and business questions; no source/ERP writes."""
import collections
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'scripts/excel_parity'), str(REPO / 'tools/excel-golden-runner')]
import package_support as p
from workbook_source import SourceBook, SOURCE, ALTERNATE, coord
from native_supplement_closure import ROOT
from technical_closure import database_snapshot


def facts(book, sheet, predicate):
    return [{'sheet': sheet, 'cell': a, 'formula': c['formula'], 'constant': c['value'] if not c['formula'] else None, 'cached_value_used': False} for a, c in book.sheets[sheet].items() if predicate(a, c)]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    target = ROOT / 'SOURCE_EXHAUSTION_AND_ADJUDICATION.json'
    p.require(not target.exists(), 'APPEND-ONLY SOURCE AUDIT EXISTS')
    before = database_snapshot()
    source = SourceBook(SOURCE)
    alternate = SourceBook(ALTERNATE)
    differences = []
    for s in set(source.sheets) | set(alternate.sheets):
        for a in set(source.sheets.get(s, {})) | set(alternate.sheets.get(s, {})):
            c, d = source.sheets.get(s, {}).get(a, {}), alternate.sheets.get(s, {}).get(a, {})
            def identity(x):
                return {'formula': x.get('formula'), 'constant': x.get('value') if not x.get('formula') else None}
            if identity(c) != identity(d):
                differences.append({'sheet': s, 'cell': a, 'registered': identity(c), 'alternate': identity(d)})
    sources = [SOURCE, ALTERNATE] + [next(SOURCE.parent.glob(prefix + '*.xlsx')) for prefix in ('05', '08', '10', '12', '13')]
    inventory, ancillary = [], []
    for path in sources:
        book = source if path == SOURCE else alternate if path == ALTERNATE else SourceBook(path)
        inventory.append({'path': str(path), 'sha256': p.digest(path), 'sheets': book.inventory, 'authority': 'REGISTERED_ENGINEERING_FORMULA' if path == SOURCE else 'RECOVERY_CROSS_REFERENCE_ONLY', 'cached_values_oracle': False})
        if path not in (SOURCE, ALTERNATE):
            # Complete formula texts plus actual headings; facts inventories do
            # not turn these workbooks into calculation authority.
            ancillary.append({'path': str(path), 'formulas': [f for s in book.sheets for f in facts(book, s, lambda a,c: bool(c['formula']))], 'headings': [f for s in book.sheets for f in facts(book, s, lambda a,c: coord(a)[0] <= 3)], 'material_role_matches': [f for s in book.sheets for f in facts(book, s, lambda a,c: not c['formula'] and any(k in str(c['value']) for k in ('木皮', '封边', '板材', '光板')))]})
    discovered = subprocess.run(['rg', '--files', r'C:\Users\DAODA\Documents\Codex', r'D:\Dev-PCE', '-g', '*.xlsx', '-g', '!node_modules', '-g', '!runs', '-g', '!prechecks', '-g', '!test-results', '-g', '!backups', '-g', '!artifacts', '-g', '!venv', '-g', '!site-packages'], capture_output=True, text=True, encoding='utf-8', check=True).stdout.splitlines()
    # Only registered/alternate engineering copies are independent workbook
    # sources. Generated confirmation previews are not historical oracles.
    file_search = [{'path': s, 'disposition': 'READ_SOURCE' if Path(s) in sources else 'OTHER_MASTER_LIST_NOT_FORMULA_HISTORY' if '\\sources\\' in s else 'GENERATED_CONFIRMATION_OR_AUDIT_NOT_ORIGINAL_HISTORY'} for s in discovered]
    contextual = []
    for s in source.sheets:
        formulas = facts(source, s, lambda a,c: bool(c['formula']))
        patterns = collections.defaultdict(list)
        for f in formulas:
            if ('物料目录(设计)' in f['formula'] and 'MATCH(' in f['formula']) or ('SUM(' in f['formula'] and s in ('木饰面', '柜子单', '隐形门模板 (2)', '三合一生产单')):
                pattern = re.sub(r'(?<=[A-Z])\d+', '<row>', f['formula'])
                patterns[pattern].append(f)
        contextual.append({'sheet': s, 'formulas_scanned': len(formulas), 'matching_patterns': [{'pattern': k, 'count': len(v), 'first': v[0], 'last': v[-1]} for k,v in patterns.items()]})
    selected = []
    for s in ('木饰面', '柜子单', '隐形门模板 (2)'):
        selected += facts(source, s, lambda a,c: coord(a)[0] in (5,6,7,27,28,30,31,32,33,34,36,37,38,40,41) and coord(a)[1] >= 11)
    selected += facts(source, '三合一生产单', lambda a,c: coord(a)[0] in (5,6,7,25,26,27,28,29,30,31,73) and coord(a)[1] >= 15)
    selected += facts(source, '房门单', lambda a,c: coord(a)[0] in (3,10,38,39,520))
    selected += facts(source, '物料目录(设计)', lambda a,c: coord(a)[0] == 1)
    selected += facts(source, '木门单公式', lambda a,c: True)
    structure_path = REPO / 'backend/masterdata/group3_comparison_source.json'
    structure = p.read(structure_path)['engineeringBreakdown']
    # Numeric structure quantities are never admitted as truth; only identities.
    structure_rows = [{k:r.get(k) for k in ('sourceFile','sourceSheet','sourceRow','productCategory','space','productName','model','materialCode')} for r in structure['rows']]
    db = REPO / 'backend/db.sqlite3'
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.row_factory = sqlite3.Row
        rules = [dict(r) for r in conn.execute('SELECT rule_code,rule_name,version,status,specification FROM pde_engineering_rule_definition')]
        history = [dict(r) for r in conn.execute('SELECT calculation_no,status,scope,trace FROM pde_engineering_calculation_record')]
    questions = [
        {'id':'U03-01','families':1,'cells':'房门单!W39:W520（482格）','calculation':'旧房门模板的目录属性查询，不是已证明的见光面积公式','original':'INDEX 目录；首个 MATCH 用 X 行查颜色；第二个 MATCH 的列选择条件变为 #REF!','current':'本次输入的查找先失败，Native 返回空文本；这不能识别被删掉的目录字段','actual_business_result':'未找到可关联的已确认历史输出','searched':'上下行、482格同族、全工作簿目录查询族、木门单公式、两份原始副本、结构和4条正式规则','why_unresolved':'W38 是几何面积，W39 是另一布局的目录查询；目录有木皮种类/坯板材质/单位等多列，没有证据唯一选定','candidate_options':['保留目录查询，并明确应该取得的目录属性','若该区域已废弃，按业务确认排除其适用范围；不删除源记录'],'recommendation':'不把 W38 复制到 W39；先确认旧模板此栏的业务含义','business_question':'房门表第39行起这一旧模板区域是否仍使用？若使用，这一栏原本应取得什么业务属性？'},
        {'id':'U03-02','families':12,'cells':'三合一生产单!AG29:AR29','calculation':'12种厚度的板材用量汇总','original':'12格均为 =#REF!；下行各乘1.2；三种板长桶及厚度条件仍可见','current':'Native 为 #REF!；36个材料桶候选已原生验证，但汇总行范围已经丢失','actual_business_result':'08派生样例没有稳定订单/结构键能证明本表汇总答案；既有BOM只有结构参考资格','searched':'三张同构表、所有材料桶/汇总公式、原副本、05/08/10/12/13来源、结构与正式规则','why_unresolved':'柜子单汇总7:26，木饰面/隐形门模板的桶汇总21:26；三合一有效行延伸至71，表头又有一列错位；不能唯一确定应包括哪些行和板长桶','candidate_options':['按对应板长及厚度汇总全部有效明细','按业务确认的分段/部件范围汇总'],'recommendation':'保持真实条件分桶，不根据错位表头或同构表行号机械复制；业务确定汇总范围后再验证','business_question':'这组板材用量应汇总哪些部件/明细范围？它对应2440板长桶还是其它业务分组？'},
        {'id':'U03-03','families':1,'cells':'三合一生产单!AV30','calculation':'木皮领用面积','original':'=#REF!*1.2；单位㎡','current':'原生 #REF!；损耗倍率1.2可见，基数丢失','actual_business_result':'没有与这些明细同身份、已确认的木皮领用历史数量','searched':'木皮目录/12木皮/采购清单，三张同构表 R/M 面积逻辑及汇总，材料清单，正式计算历史','why_unresolved':'同构表木皮汇总存在 R（按单/双/白坯）与 M（单则1否则2）两种逻辑，以及7:26和21:26范围差异；不能仅凭名称选出本表基数','candidate_options':['按单/双/白坯的木皮覆盖面积汇总后乘1.2','按净产品面积或另一经确认的贴皮范围汇总后乘1.2'],'recommendation':'只保留源有1.2，不凭行业经验新增倍率或把所有见光面自动当贴皮面','business_question':'木皮领用的基数按哪些贴皮面和哪些明细汇总？白坯件是否计木皮？'},
        {'id':'U03-04','families':1,'cells':'三合一生产单!AV31','calculation':'封边用量','original':'=#REF!；摘要单位㎡，明细R列为封边长度','current':'原生 #REF!；同构表也出现“封边米数 m”和摘要“㎡”并存','actual_business_result':'没有已确认的封边用量/单位记录能消除此歧义','searched':'封边条件、R列长度公式、三张同构表、采购/半成品清单、材料汇总、结构和正式计算历史','why_unresolved':'无法确定应输出长度，还是长度乘条宽后的面积；同构范围也不一致。不能自主把㎡改成m','candidate_options':['输出封边总长度，单位m','输出封边面积，补充实际封边宽度与换算口径'],'recommendation':'业务先确认数量维度；保留源单位冲突，不静默修正','business_question':'这里需要的是封边长度（米）还是封边面积（平方米），应包括哪些明细？'},
    ]
    p.require(database_snapshot() == before, 'PRODUCTION DRIFT')
    data = {'timestamp':p.now(),'scope':'EXISTING GOVERNED SOURCE CORPUS ONLY; NO GLOBAL EXHAUSTION CLAIM','sources':inventory,'file_search':file_search,'formula_constant_differences_between_engineering_copies':differences,'ancillary':ancillary,'formula_search':contextual,'recovery_context_facts':selected,'structure':{'path':str(structure_path),'sha':p.digest(structure_path),'rows':structure_rows,'role':'STRUCTURAL_REFERENCE_ONLY; NO NUMERIC AUTHORITY'},'formal_rules':rules,'formal_calculation_history':history,'historical_candidate_output_oracle_found':False,'user_decisions':questions,'U01':'NOT_TRIGGERED','U02':'NOT_TRIGGERED_NO_VERIFIED_REAL_BUSINESS_CONTRADICTION','U03':'TRIGGERED_FOR_15_FAMILIES_IN_4_BUSINESS_QUESTIONS','U04':'NOT_TRIGGERED_NO_MANUAL_MATERIAL_EVIDENCE','source_sha':p.digest(SOURCE),'production':before,'writes':0}
    p.write(target,data)
    print(json.dumps({'file':str(target),'sha':p.digest(target),'source_count':len(inventory),'source_formula_constant_differences':len(differences),'formula_scanned':sum(x['formulas_scanned'] for x in contextual),'questions':questions},ensure_ascii=False))


if __name__ == '__main__':
    main()
