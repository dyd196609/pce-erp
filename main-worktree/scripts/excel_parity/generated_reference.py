"""AUTO-GENERATED from immutable Excel source AST. NON-PRODUCTION reference only.
Do not edit formulas here; regenerate with analyze.py. Golden parity pending.
"""

# FF_b689b5b31e1f: 拆单基础数据 / 横线
# Source: 拆单基础数据!K2 (6 cells)
# Formula: =J2*2+30
def 横线__ff_b689b5b31e1f(ctx, row, col):
    线型_1 = lambda: ctx.reference('J2', '拆单基础数据', row - 2, col - 11)
    return ctx.binary('+', ctx.binary('*', 线型_1(), 2), 30)

# FF_e9d129d84a66: 拆单基础数据 / 竖线
# Source: 拆单基础数据!L2 (6 cells)
# Formula: =J2+30
def 竖线__ff_e9d129d84a66(ctx, row, col):
    线型_1 = lambda: ctx.reference('J2', '拆单基础数据', row - 2, col - 12)
    return ctx.binary('+', 线型_1(), 30)

# FF_a1b554a798a5: 房门单 / 语义待核对_F
# Source: 房门单!F2 (1 cells)
# Formula: =CONCATENATE(表头!$C$3,"-",K2)
def 语义待核对_F__ff_a1b554a798a5(ctx, row, col):
    订单类别_1 = lambda: ctx.reference('K2', '房门单', row - 2, col - 6)
    订单编号_2 = lambda: ctx.reference('表头!$C$3', '房门单', row - 2, col - 6)
    return ctx.call('CONCATENATE', [lambda: 订单编号_2(), lambda: '-', lambda: 订单类别_1()], row=row, col=col)

# FF_d3fc62f3d1cb: 房门单 / 订单交期
# Source: 房门单!R2 (1 cells)
# Formula: =表头!N3
def 订单交期__ff_d3fc62f3d1cb(ctx, row, col):
    发货_1 = lambda: ctx.reference('表头!N3', '房门单', row - 2, col - 18)
    return 发货_1()

# FF_c44e95df4ffb: 房门单 / 周期
# Source: 房门单!U2 (1 cells)
# Formula: =_xlfn.CONCAT("木",ROUND((R2-N2)*0.6,0),"天  ",CHAR(10),"油",ROUND((R2-N2)*0.4,0),"天")
def 周期__ff_c44e95df4ffb(ctx, row, col):
    下单日期_1 = lambda: ctx.reference('N2', '房门单', row - 2, col - 21)
    订单交期_2 = lambda: ctx.reference('R2', '房门单', row - 2, col - 21)
    return ctx.call('CONCAT', [lambda: '木', lambda: ctx.call('ROUND', [lambda: ctx.binary('*', ctx.binary('-', 订单交期_2(), 下单日期_1()), 0.6), lambda: 0], row=row, col=col), lambda: '天  ', lambda: ctx.call('CHAR', [lambda: 10], row=row, col=col), lambda: '油', lambda: ctx.call('ROUND', [lambda: ctx.binary('*', ctx.binary('-', 订单交期_2(), 下单日期_1()), 0.4), lambda: 0], row=row, col=col), lambda: '天'], row=row, col=col)

# FF_0c81aaeeb4aa: 房门单 / 语义待核对_F
# Source: 房门单!F3 (1 cells)
# Formula: =表头!C4
def 语义待核对_F__ff_0c81aaeeb4aa(ctx, row, col):
    地_址_1 = lambda: ctx.reference('表头!C4', '房门单', row - 3, col - 6)
    return 地_址_1()

# FF_743d4f108af9: 房门单 / 油漆工艺
# Source: 房门单!M3 (1 cells)
# Formula: =INDEX('物料目录(设计)'!$A:$U,MATCH($I$3,'物料目录(设计)'!$G:$G,0),MATCH("油漆工艺(必填)",'物料目录(设计)'!$A$1:$U$1,0))
def 油漆工艺__ff_743d4f108af9(ctx, row, col):
    色版_1 = lambda: ctx.reference('$I$3', '房门单', row - 3, col - 13)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 3, col - 13)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '房门单', row - 3, col - 13)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '房门单', row - 3, col - 13)
    return ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: 色版_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '油漆工艺(必填)', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col)

# FF_916c19053114: 房门单 / 木皮
# Source: 房门单!P3 (1 cells)
# Formula: =INDEX('物料目录(设计)'!$A:$U,MATCH($I$3,'物料目录(设计)'!$G:$G,0),MATCH("木皮种类",'物料目录(设计)'!$A$1:$U$1,0))
def 木皮__ff_916c19053114(ctx, row, col):
    色版_1 = lambda: ctx.reference('$I$3', '房门单', row - 3, col - 16)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 3, col - 16)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '房门单', row - 3, col - 16)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '房门单', row - 3, col - 16)
    return ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: 色版_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '木皮种类', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col)

# FF_d28514ba850e: 房门单 / 坯板
# Source: 房门单!S3 (1 cells)
# Formula: =INDEX('物料目录(设计)'!$A:$U,MATCH($I$3,'物料目录(设计)'!$G:$G,0),MATCH("坯板材质",'物料目录(设计)'!$A$1:$U$1,0))
def 坯板__ff_d28514ba850e(ctx, row, col):
    色版_1 = lambda: ctx.reference('$I$3', '房门单', row - 3, col - 19)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 3, col - 19)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '房门单', row - 3, col - 19)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '房门单', row - 3, col - 19)
    return ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: 色版_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '坯板材质', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col)

# FF_82df6461f465: 房门单 / 客户等级
# Source: 房门单!X3 (1 cells)
# Formula: =VLOOKUP(I2,客户!$A:$C,MATCH("等级",客户!$A$1:$C$1,0),0)
def 客户等级__ff_82df6461f465(ctx, row, col):
    客户名称_1 = lambda: ctx.reference('I2', '房门单', row - 3, col - 24)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('客户!$A$1:$C$1', '房门单', row - 3, col - 24)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('客户!$A:$C', '房门单', row - 3, col - 24)
    return ctx.call('VLOOKUP', [lambda: 客户名称_1(), lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: '等级', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col)

# FF_6131298d871e: 房门单 / 60*18
# Source: 房门单!I6 (2 cells)
# Formula: =IFERROR(SUMIFS($AW:$AW,$AS:$AS,G6,$AV:$AV,H6)+SUMIFS($AY:$AY,$AS:$AS,G6,$AV:$AV,H6)+SUMIFS($BC:$BC,$BA:$BA,G6,$BB:$BB,H6),"")
def field_60_18__ff_6131298d871e(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$AS:$AS', '房门单', row - 6, col - 9)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$AV:$AV', '房门单', row - 6, col - 9)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('$AW:$AW', '房门单', row - 6, col - 9)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('$AY:$AY', '房门单', row - 6, col - 9)
    lookup_or_aggregate_range_5 = lambda: ctx.reference('$BA:$BA', '房门单', row - 6, col - 9)
    lookup_or_aggregate_range_6 = lambda: ctx.reference('$BB:$BB', '房门单', row - 6, col - 9)
    lookup_or_aggregate_range_7 = lambda: ctx.reference('$BC:$BC', '房门单', row - 6, col - 9)
    平板门套线_8 = lambda: ctx.reference('G6', '房门单', row - 6, col - 9)
    field_60_18_9 = lambda: ctx.reference('H6', '房门单', row - 6, col - 9)
    return ctx.call('IFERROR', [lambda: ctx.binary('+', ctx.binary('+', ctx.call('SUMIFS', [lambda: lookup_or_aggregate_range_3(), lambda: lookup_or_aggregate_range_1(), lambda: 平板门套线_8(), lambda: lookup_or_aggregate_range_2(), lambda: field_60_18_9()], row=row, col=col), ctx.call('SUMIFS', [lambda: lookup_or_aggregate_range_4(), lambda: lookup_or_aggregate_range_1(), lambda: 平板门套线_8(), lambda: lookup_or_aggregate_range_2(), lambda: field_60_18_9()], row=row, col=col)), ctx.call('SUMIFS', [lambda: lookup_or_aggregate_range_7(), lambda: lookup_or_aggregate_range_5(), lambda: 平板门套线_8(), lambda: lookup_or_aggregate_range_6(), lambda: field_60_18_9()], row=row, col=col)), lambda: ''], row=row, col=col)

# FF_1fbc94502ca1: 房门单 / 50*18
# Source: 房门单!I8 (1 cells)
# Formula: =IFERROR(SUMIFS($AW:$AW,$AS:$AS,G8,$AV:$AV,H8)+SUMIFS($AY:$AY,$AS:$AS,G8,$AV:$AV,H8)+SUMIFS($BC:$BC,$BA:$BA,G8,$BB:$BB,H8),"")
def field_50_18__ff_1fbc94502ca1(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$AS:$AS', '房门单', row - 8, col - 9)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$AV:$AV', '房门单', row - 8, col - 9)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('$AW:$AW', '房门单', row - 8, col - 9)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('$AY:$AY', '房门单', row - 8, col - 9)
    lookup_or_aggregate_range_5 = lambda: ctx.reference('$BA:$BA', '房门单', row - 8, col - 9)
    lookup_or_aggregate_range_6 = lambda: ctx.reference('$BB:$BB', '房门单', row - 8, col - 9)
    lookup_or_aggregate_range_7 = lambda: ctx.reference('$BC:$BC', '房门单', row - 8, col - 9)
    平板门套线_8 = lambda: ctx.reference('G8', '房门单', row - 8, col - 9)
    field_50_18_9 = lambda: ctx.reference('H8', '房门单', row - 8, col - 9)
    return ctx.call('IFERROR', [lambda: ctx.binary('+', ctx.binary('+', ctx.call('SUMIFS', [lambda: lookup_or_aggregate_range_3(), lambda: lookup_or_aggregate_range_1(), lambda: 平板门套线_8(), lambda: lookup_or_aggregate_range_2(), lambda: field_50_18_9()], row=row, col=col), ctx.call('SUMIFS', [lambda: lookup_or_aggregate_range_4(), lambda: lookup_or_aggregate_range_1(), lambda: 平板门套线_8(), lambda: lookup_or_aggregate_range_2(), lambda: field_50_18_9()], row=row, col=col)), ctx.call('SUMIFS', [lambda: lookup_or_aggregate_range_7(), lambda: lookup_or_aggregate_range_5(), lambda: 平板门套线_8(), lambda: lookup_or_aggregate_range_6(), lambda: field_50_18_9()], row=row, col=col)), lambda: ''], row=row, col=col)

# FF_99f21de6ab30: 房门单 / 空套
# Source: 房门单!G9 (1 cells)
# Formula: =SUMIF($H10:$H1000,"单面套",$M10:$M1000)+SUMIF($H10:$H1000,"双面套",$M10:$M1000)+SUMIF($H10:$H1000,"窗套",$M10:$M1000)
def 空套__ff_99f21de6ab30(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$H10:$H1000', '房门单', row - 9, col - 7)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$M10:$M1000', '房门单', row - 9, col - 7)
    return ctx.binary('+', ctx.binary('+', ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '单面套', lambda: lookup_or_aggregate_range_2()], row=row, col=col), ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '双面套', lambda: lookup_or_aggregate_range_2()], row=row, col=col)), ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '窗套', lambda: lookup_or_aggregate_range_2()], row=row, col=col))

# FF_ad9acf8a80f4: 房门单 / 空套板
# Source: 房门单!I9 (1 cells)
# Formula: =G9*3
def 空套板__ff_ad9acf8a80f4(ctx, row, col):
    空套_1 = lambda: ctx.reference('G9', '房门单', row - 9, col - 9)
    return ctx.binary('*', 空套_1(), 3)

# FF_fa2dd4db99da: 房门单 / 门头板
# Source: 房门单!K9 (1 cells)
# Formula: =SUMIF($H10:$H1000,"门头板",$Q10:$Q1000)
def 门头板__ff_fa2dd4db99da(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$H10:$H1000', '房门单', row - 9, col - 11)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$Q10:$Q1000', '房门单', row - 9, col - 11)
    return ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '门头板', lambda: lookup_or_aggregate_range_2()], row=row, col=col)

# FF_78211945bc71: 房门单 / 门扇
# Source: 房门单!M9 (1 cells)
# Formula: =SUMIF($H10:$H1000,"单开门",$U10:$U1000)+SUMIF($H10:$H1000,"双开门",$U10:$U1000)+SUMIF($H10:$H1000,"子母门",$U10:$U1000)
def 门扇__ff_78211945bc71(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$H10:$H1000', '房门单', row - 9, col - 13)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$U10:$U1000', '房门单', row - 9, col - 13)
    return ctx.binary('+', ctx.binary('+', ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '单开门', lambda: lookup_or_aggregate_range_2()], row=row, col=col), ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '双开门', lambda: lookup_or_aggregate_range_2()], row=row, col=col)), ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '子母门', lambda: lookup_or_aggregate_range_2()], row=row, col=col))

# FF_13345f9170f0: 房门单 / 门套
# Source: 房门单!O9 (1 cells)
# Formula: =SUMIF($H10:$H1000,"单面套",$Q10:$Q1000)+SUMIF($H10:$H1000,"双面套",$Q10:$Q1000)+SUMIF($H10:$H1000,"窗套",$Q10:$Q1000)
def 门套__ff_13345f9170f0(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$H10:$H1000', '房门单', row - 9, col - 15)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$Q10:$Q1000', '房门单', row - 9, col - 15)
    return ctx.binary('+', ctx.binary('+', ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '单面套', lambda: lookup_or_aggregate_range_2()], row=row, col=col), ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '双面套', lambda: lookup_or_aggregate_range_2()], row=row, col=col)), ctx.call('SUMIF', [lambda: lookup_or_aggregate_range_1(), lambda: '窗套', lambda: lookup_or_aggregate_range_2()], row=row, col=col))

# FF_b69691813325: 房门单 / 门套板
# Source: 房门单!Q9 (1 cells)
# Formula: =O9*3
def 门套板__ff_b69691813325(ctx, row, col):
    门套_1 = lambda: ctx.reference('O9', '房门单', row - 9, col - 17)
    return ctx.binary('*', 门套_1(), 3)

# FF_fd9445ff72f3: 房门单 / 见光平方
# Source: 房门单!S9 (1 cells)
# Formula: =SUM(W10:W1000)
def visible_area_m2__ff_fd9445ff72f3(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('W10:W1000', '房门单', row - 9, col - 19)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_2f8e4b6fc8b6: 房门单 / 套板平方
# Source: 房门单!U9 (1 cells)
# Formula: =SUM(X10:X1000)
def frame_area_m2__ff_2f8e4b6fc8b6(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('X10:X1000', '房门单', row - 9, col - 21)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_04a7ba17119b: 房门单 / 门面板
# Source: 房门单!W9 (1 cells)
# Formula: =SUM(Y10:Y1000)
def 门面板__ff_04a7ba17119b(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('Y10:Y1000', '房门单', row - 9, col - 23)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_7e6207dbd768: 房门单 / 序号
# Source: 房门单!A11 (28 cells)
# Formula: =ROW()-10
def row_number__ff_7e6207dbd768(ctx, row, col):
    return ctx.binary('-', ctx.call('ROW', [], row=row, col=col), 10)

# FF_01649050f825: 房门单 / 物料编码(必填)
# Source: 房门单!B11 (28 cells)
# Formula: =IFERROR(INDEX('物料目录(设计)'!$A$1:$U$103,MATCH(AD11,'物料目录(设计)'!$G$1:$G$103,0),MATCH("物料编码(必填)",'物料目录(设计)'!$A$1:$U$1,0)),"")
def material_code__ff_01649050f825(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 11, col - 2)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$103", '房门单', row - 11, col - 2)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$G$1:$G$103", '房门单', row - 11, col - 2)
    finish_reference_4 = lambda: ctx.reference('AD11', '房门单', row - 11, col - 2)
    return ctx.call('IFERROR', [lambda: ctx.call('INDEX', [lambda: lookup_or_aggregate_range_2(), lambda: ctx.call('MATCH', [lambda: finish_reference_4(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '物料编码(必填)', lambda: lookup_or_aggregate_range_1(), lambda: 0], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_7eda01a9afff: 房门单 / 工艺编码(必填)
# Source: 房门单!C11 (28 cells)
# Formula: =IFERROR(VLOOKUP(I11,油漆工艺及编码!$A$1:$B$21,MATCH("工艺编码",油漆工艺及编码!$A$1:$B$1,0),0)&"/"&VLOOKUP($E11,拆单基础数据!$A:$S,MATCH("类别编码",拆单基础数据!$A$1:$S$1,0),0),"")
def process_code__ff_7eda01a9afff(ctx, row, col):
    产品类别_必填_1 = lambda: ctx.reference('$E11', '房门单', row - 11, col - 3)
    paint_process_2 = lambda: ctx.reference('I11', '房门单', row - 11, col - 3)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$A$1:$S$1', '房门单', row - 11, col - 3)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$A:$S', '房门单', row - 11, col - 3)
    lookup_or_aggregate_range_5 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$1', '房门单', row - 11, col - 3)
    lookup_or_aggregate_range_6 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$21', '房门单', row - 11, col - 3)
    return ctx.call('IFERROR', [lambda: ctx.binary('&', ctx.binary('&', ctx.call('VLOOKUP', [lambda: paint_process_2(), lambda: lookup_or_aggregate_range_6(), lambda: ctx.call('MATCH', [lambda: '工艺编码', lambda: lookup_or_aggregate_range_5(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), '/'), ctx.call('VLOOKUP', [lambda: 产品类别_必填_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: '类别编码', lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col)), lambda: ''], row=row, col=col)

# FF_7365d3f62375: 房门单 / 订单类型（必填）
# Source: 房门单!D11 (461 cells)
# Formula: =IF($B11="","",$K$2)
def 订单类型_必填__ff_7365d3f62375(ctx, row, col):
    material_code_1 = lambda: ctx.reference('$B11', '房门单', row - 11, col - 4)
    订单类别_2 = lambda: ctx.reference('$K$2', '房门单', row - 11, col - 4)
    return ctx.call('IF', [lambda: ctx.binary('=', material_code_1(), ''), lambda: '', lambda: 订单类别_2()], row=row, col=col)

# FF_fc6fb8c4ccd7: 房门单 / 油漆工艺(必填)
# Source: 房门单!I11 (17 cells)
# Formula: =IFERROR(INDEX('物料目录(设计)'!$A:$U,MATCH($AD11,'物料目录(设计)'!$G:$G,0),MATCH(I$10,'物料目录(设计)'!$A$1:$U$1,0)),"")
def paint_process__ff_fc6fb8c4ccd7(ctx, row, col):
    finish_reference_1 = lambda: ctx.reference('$AD11', '房门单', row - 11, col - 9)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 11, col - 9)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '房门单', row - 11, col - 9)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '房门单', row - 11, col - 9)
    product_name_5 = lambda: ctx.reference('I$10', '房门单', row - 11, col - 9)
    return ctx.call('IFERROR', [lambda: ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: finish_reference_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: product_name_5(), lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_e5d7975b2645: 房门单 / 门套高
# Source: 房门单!N11 (17 cells)
# Formula: =IFERROR(IF(J11="","",IF(OR(H11="单面套",H11="双面套"),J11,J11-10)),"")
def frame_height_mm__ff_e5d7975b2645(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 14)
    opening_height_mm_2 = lambda: ctx.reference('J11', '房门单', row - 11, col - 14)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', opening_height_mm_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: ctx.binary('=', product_name_1(), '双面套')], row=row, col=col), lambda: opening_height_mm_2(), lambda: ctx.binary('-', opening_height_mm_2(), 10)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_cd8350bcc8e1: 房门单 / 门套宽
# Source: 房门单!O11 (15 cells)
# Formula: =IFERROR(IF(K11="","",IF(OR(H11="单面套",H11="双面套"),K11,K11-20)),"")
def frame_width_mm__ff_cd8350bcc8e1(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 15)
    opening_width_mm_2 = lambda: ctx.reference('K11', '房门单', row - 11, col - 15)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', opening_width_mm_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: ctx.binary('=', product_name_1(), '双面套')], row=row, col=col), lambda: opening_width_mm_2(), lambda: ctx.binary('-', opening_width_mm_2(), 20)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_94d7bbd1bcc8: 房门单 / 门墙厚
# Source: 房门单!P11 (17 cells)
# Formula: =IFERROR(IF(L11="","",L11*1),"")
def frame_wall_thickness_mm__ff_94d7bbd1bcc8(ctx, row, col):
    wall_thickness_mm_1 = lambda: ctx.reference('L11', '房门单', row - 11, col - 16)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', wall_thickness_mm_1(), ''), lambda: '', lambda: ctx.binary('*', wall_thickness_mm_1(), 1)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_94558f4e733f: 房门单 / 门套数量
# Source: 房门单!Q11 (17 cells)
# Formula: =IFERROR(IF(M11="","",M11),"")
def frame_quantity__ff_94558f4e733f(ctx, row, col):
    opening_quantity_1 = lambda: ctx.reference('M11', '房门单', row - 11, col - 17)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', opening_quantity_1(), ''), lambda: '', lambda: opening_quantity_1()], row=row, col=col), lambda: ''], row=row, col=col)

# FF_e55e6ecbe2f5: 房门单 / 门高
# Source: 房门单!R11 (28 cells)
# Formula: =IFERROR(IF(I11<>"免漆",IF(H11="单开门",N11-33,IF(H11="双开门",N11-33,IF(H11="子母门",N11-33,IF(H11="单面套",0,IF(H11="双面套",0,""))))),IF(H11="单开门",N11-28,IF(H11="双开门",N11-28,IF(H11="子母门",N11-28,IF(H11="单面套",0,IF(H11="双面套",0,"")))))),"")
def leaf_height_mm__ff_e55e6ecbe2f5(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 18)
    paint_process_2 = lambda: ctx.reference('I11', '房门单', row - 11, col - 18)
    frame_height_mm_3 = lambda: ctx.reference('N11', '房门单', row - 11, col - 18)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('<>', paint_process_2(), '免漆'), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('-', frame_height_mm_3(), 33), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('-', frame_height_mm_3(), 33), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('-', frame_height_mm_3(), 33), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('-', frame_height_mm_3(), 28), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('-', frame_height_mm_3(), 28), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('-', frame_height_mm_3(), 28), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_2ddbe2157997: 房门单 / 门宽
# Source: 房门单!S11 (28 cells)
# Formula: =IFERROR(IF(I11<>"免漆",IF(H11="单开门",O11-52,IF(H11="双开门",(O11-46)/2,IF(H11="子母门",((O11)-46)&"("&((O11)-46-350-3+10)&","&(350)&")",IF(H11="单面套",0,IF(H11="双面套",0,""))))),IF(H11="单开门",O11-42,IF(H11="双开门",(O11-36)/2,IF(H11="子母门",((O11)-36)&"("&((O11)-36-350-3+10)&","&(350)&")",IF(H11="单面套",0,IF(H11="双面套",0,"")))))),"")
def leaf_width_or_pair_description__ff_2ddbe2157997(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 19)
    paint_process_2 = lambda: ctx.reference('I11', '房门单', row - 11, col - 19)
    frame_width_mm_3 = lambda: ctx.reference('O11', '房门单', row - 11, col - 19)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('<>', paint_process_2(), '免漆'), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('-', frame_width_mm_3(), 52), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('/', ctx.binary('-', frame_width_mm_3(), 46), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('-', frame_width_mm_3(), 46), '('), ctx.binary('+', ctx.binary('-', ctx.binary('-', ctx.binary('-', frame_width_mm_3(), 46), 350), 3), 10)), ','), 350), ')'), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('-', frame_width_mm_3(), 42), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('/', ctx.binary('-', frame_width_mm_3(), 36), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('-', frame_width_mm_3(), 36), '('), ctx.binary('+', ctx.binary('-', ctx.binary('-', ctx.binary('-', frame_width_mm_3(), 36), 350), 3), 10)), ','), 350), ')'), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_2b9e867ba950: 房门单 / 门厚
# Source: 房门单!T11 (28 cells)
# Formula: =IFERROR(_xlfn.IFS(OR(H11="单面套",H11="双面套",H11="移门套",H11="窗套"),"",OR(H11="单开门",H11="双开门",H11="子母门"),45),"")
def leaf_thickness_mm__ff_2b9e867ba950(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 20)
    return ctx.call('IFERROR', [lambda: ctx.call('IFS', [lambda: ctx.call('OR', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: ctx.binary('=', product_name_1(), '移门套'), lambda: ctx.binary('=', product_name_1(), '窗套')], row=row, col=col), lambda: '', lambda: ctx.call('OR', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('=', product_name_1(), '子母门')], row=row, col=col), lambda: 45], row=row, col=col), lambda: ''], row=row, col=col)

# FF_16c1f81ef2f0: 房门单 / 门数量
# Source: 房门单!U11 (28 cells)
# Formula: =IFERROR(IF(H11="单开门",Q11*1,IF(H11="双开门",Q11*2,IF(H11="子母门",Q11*2,IF(H11="单面套",Q11*1,IF(H11="双面套",Q11*1,""))))),"")
def leaf_quantity__ff_16c1f81ef2f0(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 21)
    frame_quantity_2 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 21)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('*', frame_quantity_2(), 1), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('*', frame_quantity_2(), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('*', frame_quantity_2(), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: ctx.binary('*', frame_quantity_2(), 1), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: ctx.binary('*', frame_quantity_2(), 1), lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_1aea682eff65: 房门单 / 单位
# Source: 房门单!V11 (28 cells)
# Formula: =IFERROR(VLOOKUP($H11,拆单基础数据!$C:$S,MATCH(V$10,拆单基础数据!$C$1:$S$1,0),0),"")
def uom__ff_1aea682eff65(ctx, row, col):
    product_name_1 = lambda: ctx.reference('$H11', '房门单', row - 11, col - 22)
    leaf_quantity_2 = lambda: ctx.reference('V$10', '房门单', row - 11, col - 22)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$C$1:$S$1', '房门单', row - 11, col - 22)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$C:$S', '房门单', row - 11, col - 22)
    return ctx.call('IFERROR', [lambda: ctx.call('VLOOKUP', [lambda: product_name_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: leaf_quantity_2(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: ''], row=row, col=col)

# FF_bb1154f33707: 房门单 / 见光平方
# Source: 房门单!W11 (28 cells)
# Formula: =IFERROR((R11/1000*S11/1000*2*U11+N11/1000*P11/1000*2*Q11+O11/1000*P11/1000*Q11),"")
def visible_area_m2__ff_bb1154f33707(ctx, row, col):
    frame_height_mm_1 = lambda: ctx.reference('N11', '房门单', row - 11, col - 23)
    frame_width_mm_2 = lambda: ctx.reference('O11', '房门单', row - 11, col - 23)
    frame_wall_thickness_mm_3 = lambda: ctx.reference('P11', '房门单', row - 11, col - 23)
    frame_quantity_4 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 23)
    leaf_height_mm_5 = lambda: ctx.reference('R11', '房门单', row - 11, col - 23)
    leaf_width_or_pair_description_6 = lambda: ctx.reference('S11', '房门单', row - 11, col - 23)
    leaf_quantity_7 = lambda: ctx.reference('U11', '房门单', row - 11, col - 23)
    return ctx.call('IFERROR', [lambda: ctx.binary('+', ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', leaf_height_mm_5(), 1000), leaf_width_or_pair_description_6()), 1000), 2), leaf_quantity_7()), ctx.binary('*', ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', frame_height_mm_1(), 1000), frame_wall_thickness_mm_3()), 1000), 2), frame_quantity_4())), ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', frame_width_mm_2(), 1000), frame_wall_thickness_mm_3()), 1000), frame_quantity_4())), lambda: ''], row=row, col=col)

# FF_2754778664d5: 房门单 / 套板平方
# Source: 房门单!X11 (17 cells)
# Formula: =IFERROR(N11/1000*P11/1000*2*Q11+O11/1000*P11/1000*Q11,"")
def frame_area_m2__ff_2754778664d5(ctx, row, col):
    frame_height_mm_1 = lambda: ctx.reference('N11', '房门单', row - 11, col - 24)
    frame_width_mm_2 = lambda: ctx.reference('O11', '房门单', row - 11, col - 24)
    frame_wall_thickness_mm_3 = lambda: ctx.reference('P11', '房门单', row - 11, col - 24)
    frame_quantity_4 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 24)
    return ctx.call('IFERROR', [lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', frame_height_mm_1(), 1000), frame_wall_thickness_mm_3()), 1000), 2), frame_quantity_4()), ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', frame_width_mm_2(), 1000), frame_wall_thickness_mm_3()), 1000), frame_quantity_4())), lambda: ''], row=row, col=col)

# FF_085a2f26fd1f: 房门单 / 门面板张
# Source: 房门单!Y11 (28 cells)
# Formula: =IFERROR(IF(M11="","",IF(H11="单开门",M11*2,IF(H11="双开门",M11*4,IF(H11="子母门",M11*3,IF(H11="单面套",M11*0,IF(H11="双面套",M11*0)))))),"")
def door_face_panel_count__ff_085a2f26fd1f(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 25)
    opening_quantity_2 = lambda: ctx.reference('M11', '房门单', row - 11, col - 25)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', opening_quantity_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('*', opening_quantity_2(), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('*', opening_quantity_2(), 4), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('*', opening_quantity_2(), 3), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: ctx.binary('*', opening_quantity_2(), 0), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: ctx.binary('*', opening_quantity_2(), 0)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_9f31702900d0: 房门单 / 封边皮25
# Source: 房门单!Z11 (8 cells)
# Formula: =IF(H11="单开门",(N11/1000*4*Q11+O11/1000*2*Q11),IF(H11="双开门",(N11/1000*4*Q11+O11/1000*2*Q11),IF(H11="单面套",(N11/1000*4*Q11+O11/1000*2*Q11),IF(H11="双面套",(N11/1000*4*Q11+O11/1000*2*Q11),IF(H11="子母门",(N11/1000*4*Q11+O11/1000*2*Q11))))))
def edge_veneer_25_length_m__ff_9f31702900d0(ctx, row, col):
    product_name_1 = lambda: ctx.reference('H11', '房门单', row - 11, col - 26)
    frame_height_mm_2 = lambda: ctx.reference('N11', '房门单', row - 11, col - 26)
    frame_width_mm_3 = lambda: ctx.reference('O11', '房门单', row - 11, col - 26)
    frame_quantity_4 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 26)
    return ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单开门'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_2(), 1000), 4), frame_quantity_4()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_3(), 1000), 2), frame_quantity_4())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双开门'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_2(), 1000), 4), frame_quantity_4()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_3(), 1000), 2), frame_quantity_4())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '单面套'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_2(), 1000), 4), frame_quantity_4()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_3(), 1000), 2), frame_quantity_4())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '双面套'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_2(), 1000), 4), frame_quantity_4()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_3(), 1000), 2), frame_quantity_4())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_1(), '子母门'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_2(), 1000), 4), frame_quantity_4()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_3(), 1000), 2), frame_quantity_4()))], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)

# FF_72be7690c27f: 房门单 / 封边皮50
# Source: 房门单!AA11 (8 cells)
# Formula: =IF(H11="单开门",(N11/1000*2*Q11+O11/1000*2*Q11),IF(H11="双开门",(N11/1000*4*Q11+O11/1000*2*Q11),IF(H11="子母门",(N11/1000*4*Q11+O11/1000*2*Q11),IF(H11="单面套",N11*0,IF(H11="双面套",E11*0)))))
def edge_veneer_50_length_m__ff_72be7690c27f(ctx, row, col):
    产品类别_必填_1 = lambda: ctx.reference('E11', '房门单', row - 11, col - 27)
    product_name_2 = lambda: ctx.reference('H11', '房门单', row - 11, col - 27)
    frame_height_mm_3 = lambda: ctx.reference('N11', '房门单', row - 11, col - 27)
    frame_width_mm_4 = lambda: ctx.reference('O11', '房门单', row - 11, col - 27)
    frame_quantity_5 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 27)
    return ctx.call('IF', [lambda: ctx.binary('=', product_name_2(), '单开门'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_3(), 1000), 2), frame_quantity_5()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_4(), 1000), 2), frame_quantity_5())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_2(), '双开门'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_3(), 1000), 4), frame_quantity_5()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_4(), 1000), 2), frame_quantity_5())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_2(), '子母门'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_height_mm_3(), 1000), 4), frame_quantity_5()), ctx.binary('*', ctx.binary('*', ctx.binary('/', frame_width_mm_4(), 1000), 2), frame_quantity_5())), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_2(), '单面套'), lambda: ctx.binary('*', frame_height_mm_3(), 0), lambda: ctx.call('IF', [lambda: ctx.binary('=', product_name_2(), '双面套'), lambda: ctx.binary('*', 产品类别_必填_1(), 0)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)

# FF_f4ef404f3311: 房门单 / 特殊色版
# Source: 房门单!AB11 (28 cells)
# Formula: =IF(E11="","",IF(AD11=$I$3,"",AD11))
def 特殊色版__ff_f4ef404f3311(ctx, row, col):
    色版_1 = lambda: ctx.reference('$I$3', '房门单', row - 11, col - 28)
    finish_reference_2 = lambda: ctx.reference('AD11', '房门单', row - 11, col - 28)
    产品类别_必填_3 = lambda: ctx.reference('E11', '房门单', row - 11, col - 28)
    return ctx.call('IF', [lambda: ctx.binary('=', 产品类别_必填_3(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.binary('=', finish_reference_2(), 色版_1()), lambda: '', lambda: finish_reference_2()], row=row, col=col)], row=row, col=col)

# FF_75e037f1153b: 房门单 / 颜色/版号
# Source: 房门单!AD11 (28 cells)
# Formula: =IF($E11="","",$I$3)
def finish_reference__ff_75e037f1153b(ctx, row, col):
    产品类别_必填_1 = lambda: ctx.reference('$E11', '房门单', row - 11, col - 30)
    色版_2 = lambda: ctx.reference('$I$3', '房门单', row - 11, col - 30)
    return ctx.call('IF', [lambda: ctx.binary('=', 产品类别_必填_1(), ''), lambda: '', lambda: 色版_2()], row=row, col=col)

# FF_4d62764356d5: 房门单 / 计划系数
# Source: 房门单!AE11 (28 cells)
# Formula: =IFERROR(VLOOKUP($H11,拆单基础数据!$C:$S,MATCH(AE$10,拆单基础数据!$C$1:$S$1,0),0),"")
def 计划系数__ff_4d62764356d5(ctx, row, col):
    product_name_1 = lambda: ctx.reference('$H11', '房门单', row - 11, col - 31)
    finish_reference_2 = lambda: ctx.reference('AE$10', '房门单', row - 11, col - 31)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$C$1:$S$1', '房门单', row - 11, col - 31)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$C:$S', '房门单', row - 11, col - 31)
    return ctx.call('IFERROR', [lambda: ctx.call('VLOOKUP', [lambda: product_name_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: finish_reference_2(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: ''], row=row, col=col)

# FF_730c9031d59f: 房门单 / 计划量
# Source: 房门单!AF11 (28 cells)
# Formula: =IFERROR(IF(OR(AE11="",M11=""),"",AE11*M11),"")
def 计划量__ff_730c9031d59f(ctx, row, col):
    计划系数_1 = lambda: ctx.reference('AE11', '房门单', row - 11, col - 32)
    opening_quantity_2 = lambda: ctx.reference('M11', '房门单', row - 11, col - 32)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', 计划系数_1(), ''), lambda: ctx.binary('=', opening_quantity_2(), '')], row=row, col=col), lambda: '', lambda: ctx.binary('*', 计划系数_1(), opening_quantity_2())], row=row, col=col), lambda: ''], row=row, col=col)

# FF_7434f7b35fba: 房门单 / 语义待核对_AJ
# Source: 房门单!AJ11 (24 cells)
# Formula: =IF(I11="平",O11*2*0.001+P11*2*0.001,)
def 语义待核对_AJ__ff_7434f7b35fba(ctx, row, col):
    paint_process_1 = lambda: ctx.reference('I11', '房门单', row - 11, col - 36)
    frame_width_mm_2 = lambda: ctx.reference('O11', '房门单', row - 11, col - 36)
    frame_wall_thickness_mm_3 = lambda: ctx.reference('P11', '房门单', row - 11, col - 36)
    return ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '平'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), 2), 0.001), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), 2), 0.001)), lambda: ctx.omitted], row=row, col=col)

# FF_1e1f4b3a2bf8: 房门单 / 套板板材平方
# Source: 房门单!AK11 (24 cells)
# Formula: =IF(I11="双",O11*Q11*0.000001*2+P11*Q11*0.000001,IF(I11="单",O11*Q11*0.000001*2+P11*Q11*0.000001,IF(I11="整",O11*70*0.000001*2+P11*70*0.000001,IF(I11="双开",O11*70*0.000001*2+P11*70*0.000001,IF(I11="子母",O11*70*0.000001*2+P11*70*0.000001,IF(I11="双移",O11*70*0.000001*2+P11*70*0.000001,))))))
def 套板板材平方__ff_1e1f4b3a2bf8(ctx, row, col):
    paint_process_1 = lambda: ctx.reference('I11', '房门单', row - 11, col - 37)
    frame_width_mm_2 = lambda: ctx.reference('O11', '房门单', row - 11, col - 37)
    frame_wall_thickness_mm_3 = lambda: ctx.reference('P11', '房门单', row - 11, col - 37)
    frame_quantity_4 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 37)
    return ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '双'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), frame_quantity_4()), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), frame_quantity_4()), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '单'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), frame_quantity_4()), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), frame_quantity_4()), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '整'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), 70), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), 70), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '双开'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), 70), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), 70), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '子母'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), 70), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), 70), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '双移'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), 70), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), 70), 1e-06)), lambda: ctx.omitted], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)

# FF_57dd115fa0d3: 房门单 / 语义待核对_AL
# Source: 房门单!AL11 (24 cells)
# Formula: =IF(I11="整",O11*(Q11-50)*0.000001*2+P11*(Q11-50)*0.000001,IF(I11="双开",O11*(Q11-50)*0.000001*2+P11*(Q11-50)*0.000001,IF(I11="子母",O11*(Q11-50)*0.000001*2+P11*(Q11-50)*0.000001,IF(I11="双移",O11*(Q11-50)*0.000001*2+P11*(Q11-50)*0.000001,))))
def 语义待核对_AL__ff_57dd115fa0d3(ctx, row, col):
    paint_process_1 = lambda: ctx.reference('I11', '房门单', row - 11, col - 38)
    frame_width_mm_2 = lambda: ctx.reference('O11', '房门单', row - 11, col - 38)
    frame_wall_thickness_mm_3 = lambda: ctx.reference('P11', '房门单', row - 11, col - 38)
    frame_quantity_4 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 38)
    return ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '整'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '双开'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '子母'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06)), lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_1(), '双移'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('*', frame_width_mm_2(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06), 2), ctx.binary('*', ctx.binary('*', frame_wall_thickness_mm_3(), ctx.binary('-', frame_quantity_4(), 50)), 1e-06)), lambda: ctx.omitted], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)

# FF_2f2884e4ae34: 房门单 / 是否为空套
# Source: 房门单!AN11 (28 cells)
# Formula: =IFERROR(VLOOKUP($H11,拆单基础数据!$C:$S,MATCH(AN$10,拆单基础数据!$C$1:$S$1,0),FALSE),"")
def 是否为空套__ff_2f2884e4ae34(ctx, row, col):
    product_name_1 = lambda: ctx.reference('$H11', '房门单', row - 11, col - 40)
    封边皮_2 = lambda: ctx.reference('AN$10', '房门单', row - 11, col - 40)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$C$1:$S$1', '房门单', row - 11, col - 40)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$C:$S', '房门单', row - 11, col - 40)
    return ctx.call('IFERROR', [lambda: ctx.call('VLOOKUP', [lambda: product_name_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: 封边皮_2(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: False], row=row, col=col), lambda: ''], row=row, col=col)

# FF_a64e35ccfd3b: 房门单 / 横加
# Source: 房门单!AO11 (28 cells)
# Formula: =AQ11*2+100
def 横加__ff_a64e35ccfd3b(ctx, row, col):
    线宽_1 = lambda: ctx.reference('AQ11', '房门单', row - 11, col - 41)
    return ctx.binary('+', ctx.binary('*', 线宽_1(), 2), 100)

# FF_aa14e1627fc7: 房门单 / 竖加
# Source: 房门单!AP11 (28 cells)
# Formula: =AQ11+100
def 竖加__ff_aa14e1627fc7(ctx, row, col):
    线宽_1 = lambda: ctx.reference('AQ11', '房门单', row - 11, col - 42)
    return ctx.binary('+', 线宽_1(), 100)

# FF_f6a8f0521d90: 房门单 / 线宽
# Source: 房门单!AQ11 (28 cells)
# Formula: =TRIM(LEFT(AS11,FIND("*",AS11)-1))
def 线宽__ff_f6a8f0521d90(ctx, row, col):
    trim_specification_1 = lambda: ctx.reference('AS11', '房门单', row - 11, col - 43)
    return ctx.call('TRIM', [lambda: ctx.call('LEFT', [lambda: trim_specification_1(), lambda: ctx.binary('-', ctx.call('FIND', [lambda: '*', lambda: trim_specification_1()], row=row, col=col), 1)], row=row, col=col)], row=row, col=col)

# FF_9791bfccc541: 房门单 / 单边横线
# Source: 房门单!AR11 (28 cells)
# Formula: =IF(K11,(K11+AO11),(O11+AO11))
def 单边横线__ff_9791bfccc541(ctx, row, col):
    横加_1 = lambda: ctx.reference('AO11', '房门单', row - 11, col - 44)
    opening_width_mm_2 = lambda: ctx.reference('K11', '房门单', row - 11, col - 44)
    frame_width_mm_3 = lambda: ctx.reference('O11', '房门单', row - 11, col - 44)
    return ctx.call('IF', [lambda: opening_width_mm_2(), lambda: ctx.binary('+', opening_width_mm_2(), 横加_1()), lambda: ctx.binary('+', frame_width_mm_3(), 横加_1())], row=row, col=col)

# FF_4412a3b79417: 房门单 / 竖线净长
# Source: 房门单!AT11 (28 cells)
# Formula: =IF(J11,J11+AP11,N11+AP11)
def 竖线净长__ff_4412a3b79417(ctx, row, col):
    竖加_1 = lambda: ctx.reference('AP11', '房门单', row - 11, col - 46)
    opening_height_mm_2 = lambda: ctx.reference('J11', '房门单', row - 11, col - 46)
    frame_height_mm_3 = lambda: ctx.reference('N11', '房门单', row - 11, col - 46)
    return ctx.call('IF', [lambda: opening_height_mm_2(), lambda: ctx.binary('+', opening_height_mm_2(), 竖加_1()), lambda: ctx.binary('+', frame_height_mm_3(), 竖加_1())], row=row, col=col)

# FF_56638d1b30f9: 房门单 / 横线净长
# Source: 房门单!AU11 (28 cells)
# Formula: =IF(K11,(K11+AO11)*2,(O11+AO11)*2)
def 横线净长__ff_56638d1b30f9(ctx, row, col):
    横加_1 = lambda: ctx.reference('AO11', '房门单', row - 11, col - 47)
    opening_width_mm_2 = lambda: ctx.reference('K11', '房门单', row - 11, col - 47)
    frame_width_mm_3 = lambda: ctx.reference('O11', '房门单', row - 11, col - 47)
    return ctx.call('IF', [lambda: opening_width_mm_2(), lambda: ctx.binary('*', ctx.binary('+', opening_width_mm_2(), 横加_1()), 2), lambda: ctx.binary('*', ctx.binary('+', frame_width_mm_3(), 横加_1()), 2)], row=row, col=col)

# FF_fc5f706a0412: 房门单 / 竖线开料长
# Source: 房门单!AV11 (28 cells)
# Formula: =IF(AT11<=2440,2440,IF(AT11<=2600,2600,IF(AT11<=2800,2800,IF(AT11<=3050,3050,IF(AT11<=3600,3600,"")))))
def 竖线开料长__ff_fc5f706a0412(ctx, row, col):
    竖线净长_1 = lambda: ctx.reference('AT11', '房门单', row - 11, col - 48)
    return ctx.call('IF', [lambda: ctx.binary('<=', 竖线净长_1(), 2440), lambda: 2440, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 竖线净长_1(), 2600), lambda: 2600, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 竖线净长_1(), 2800), lambda: 2800, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 竖线净长_1(), 3050), lambda: 3050, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 竖线净长_1(), 3600), lambda: 3600, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)

# FF_6172b8a3a02a: 房门单 / 竖线条数
# Source: 房门单!AW11 (28 cells)
# Formula: =IF(AZ11="双",4,2)*Q11
def 竖线条数__ff_6172b8a3a02a(ctx, row, col):
    线条单双_1 = lambda: ctx.reference('AZ11', '房门单', row - 11, col - 49)
    frame_quantity_2 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 49)
    return ctx.binary('*', ctx.call('IF', [lambda: ctx.binary('=', 线条单双_1(), '双'), lambda: 4, lambda: 2], row=row, col=col), frame_quantity_2())

# FF_38be392bce2b: 房门单 / 横线开料长
# Source: 房门单!AX11 (28 cells)
# Formula: =IF(AR11<2440,IF(AR11<2440,2440,IF(AU11<=2600,2600,IF(AU11<=2800,2800,IF(AU11<=3050,3050,IF(AU11<=3600,3600,""))))),IF(AR11<2440,2440,IF(AR11<=2440,2440,IF(AR11<=2600,2600,IF(AR11<=2800,2800,IF(AR11<=3050,3050,IF(AR11<=3600,3600,"")))))))
def 横线开料长__ff_38be392bce2b(ctx, row, col):
    单边横线_1 = lambda: ctx.reference('AR11', '房门单', row - 11, col - 50)
    横线净长_2 = lambda: ctx.reference('AU11', '房门单', row - 11, col - 50)
    return ctx.call('IF', [lambda: ctx.binary('<', 单边横线_1(), 2440), lambda: ctx.call('IF', [lambda: ctx.binary('<', 单边横线_1(), 2440), lambda: 2440, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 横线净长_2(), 2600), lambda: 2600, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 横线净长_2(), 2800), lambda: 2800, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 横线净长_2(), 3050), lambda: 3050, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 横线净长_2(), 3600), lambda: 3600, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ctx.call('IF', [lambda: ctx.binary('<', 单边横线_1(), 2440), lambda: 2440, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 单边横线_1(), 2440), lambda: 2440, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 单边横线_1(), 2600), lambda: 2600, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 单边横线_1(), 2800), lambda: 2800, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 单边横线_1(), 3050), lambda: 3050, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 单边横线_1(), 3600), lambda: 3600, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)

# FF_1e520fd1a320: 房门单 / 横线条数
# Source: 房门单!AY11 (28 cells)
# Formula: =IF(AZ11="单",1,IF(AU11<=2440,1,2))*Q11
def 横线条数__ff_1e520fd1a320(ctx, row, col):
    横线净长_1 = lambda: ctx.reference('AU11', '房门单', row - 11, col - 51)
    线条单双_2 = lambda: ctx.reference('AZ11', '房门单', row - 11, col - 51)
    frame_quantity_3 = lambda: ctx.reference('Q11', '房门单', row - 11, col - 51)
    return ctx.binary('*', ctx.call('IF', [lambda: ctx.binary('=', 线条单双_2(), '单'), lambda: 1, lambda: ctx.call('IF', [lambda: ctx.binary('<=', 横线净长_1(), 2440), lambda: 1, lambda: 2], row=row, col=col)], row=row, col=col), frame_quantity_3())

# FF_c7a6342dcce5: 房门单 / 线条单双
# Source: 房门单!AZ11 (28 cells)
# Formula: =IFERROR(VLOOKUP($H11,拆单基础数据!$C:$S,MATCH(AZ$10,拆单基础数据!$C$1:$S$1,0),FALSE),"")
def 线条单双__ff_c7a6342dcce5(ctx, row, col):
    product_name_1 = lambda: ctx.reference('$H11', '房门单', row - 11, col - 52)
    横线条数_2 = lambda: ctx.reference('AZ$10', '房门单', row - 11, col - 52)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$C$1:$S$1', '房门单', row - 11, col - 52)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$C:$S', '房门单', row - 11, col - 52)
    return ctx.call('IFERROR', [lambda: ctx.call('VLOOKUP', [lambda: product_name_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: 横线条数_2(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: False], row=row, col=col), lambda: ''], row=row, col=col)

# FF_046f9be4c4c5: 房门单 / 套板平方
# Source: 房门单!X19 (11 cells)
# Formula: =IFERROR(IF(L19="","",IF(G19="单开门",L19*2,IF(G19="双开门",L19*4,IF(G19="子母门",L19*3,IF(G19="单面套",L19*0,IF(G19="双面套",L19*0)))))),"")
def frame_area_m2__ff_046f9be4c4c5(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G19', '房门单', row - 19, col - 24)
    wall_thickness_mm_2 = lambda: ctx.reference('L19', '房门单', row - 19, col - 24)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', wall_thickness_mm_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('*', wall_thickness_mm_2(), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('*', wall_thickness_mm_2(), 4), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '子母门'), lambda: ctx.binary('*', wall_thickness_mm_2(), 3), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: ctx.binary('*', wall_thickness_mm_2(), 0), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: ctx.binary('*', wall_thickness_mm_2(), 0)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_8094bb56a5b1: 房门单 / 油漆工艺(必填)
# Source: 房门单!I39 (482 cells)
# Formula: =IFERROR(INDEX('物料目录(设计)'!$A:$U,MATCH($X39,'物料目录(设计)'!$G:$G,0),MATCH(I$10,'物料目录(设计)'!$A$1:$U$1,0)),"")
def paint_process__ff_8094bb56a5b1(ctx, row, col):
    frame_area_m2_1 = lambda: ctx.reference('$X39', '房门单', row - 39, col - 9)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 39, col - 9)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '房门单', row - 39, col - 9)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '房门单', row - 39, col - 9)
    product_name_5 = lambda: ctx.reference('I$10', '房门单', row - 39, col - 9)
    return ctx.call('IFERROR', [lambda: ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: frame_area_m2_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: product_name_5(), lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_237f9831456e: 房门单 / 门洞数量
# Source: 房门单!M39 (482 cells)
# Formula: =IFERROR(IF(I39="","",IF(OR(G39="单面套",G39="双面套"),I39,I39-10)),"")
def opening_quantity__ff_237f9831456e(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G39', '房门单', row - 39, col - 13)
    paint_process_2 = lambda: ctx.reference('I39', '房门单', row - 39, col - 13)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', paint_process_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: ctx.binary('=', 开启方向_1(), '双面套')], row=row, col=col), lambda: paint_process_2(), lambda: ctx.binary('-', paint_process_2(), 10)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_533b4f331679: 房门单 / 门套高
# Source: 房门单!N39 (482 cells)
# Formula: =IFERROR(IF(J39="","",IF(OR(G39="单面套",G39="双面套"),J39,J39-20)),"")
def frame_height_mm__ff_533b4f331679(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G39', '房门单', row - 39, col - 14)
    opening_height_mm_2 = lambda: ctx.reference('J39', '房门单', row - 39, col - 14)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', opening_height_mm_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: ctx.binary('=', 开启方向_1(), '双面套')], row=row, col=col), lambda: opening_height_mm_2(), lambda: ctx.binary('-', opening_height_mm_2(), 20)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_884dcddf3c1d: 房门单 / 门套宽
# Source: 房门单!O39 (482 cells)
# Formula: =IFERROR(IF(K39="","",K39*1),"")
def frame_width_mm__ff_884dcddf3c1d(ctx, row, col):
    opening_width_mm_1 = lambda: ctx.reference('K39', '房门单', row - 39, col - 15)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', opening_width_mm_1(), ''), lambda: '', lambda: ctx.binary('*', opening_width_mm_1(), 1)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_f9342bb093c0: 房门单 / 门墙厚
# Source: 房门单!P39 (482 cells)
# Formula: =IFERROR(IF(L39="","",L39),"")
def frame_wall_thickness_mm__ff_f9342bb093c0(ctx, row, col):
    wall_thickness_mm_1 = lambda: ctx.reference('L39', '房门单', row - 39, col - 16)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', wall_thickness_mm_1(), ''), lambda: '', lambda: wall_thickness_mm_1()], row=row, col=col), lambda: ''], row=row, col=col)

# FF_bfd6741e313a: 房门单 / 门套数量
# Source: 房门单!Q39 (482 cells)
# Formula: =IFERROR(IF(H39<>"免漆",IF(G39="单开门",M39-33,IF(G39="双开门",M39-33,IF(G39="子母门",M39-33,IF(G39="单面套",0,IF(G39="双面套",0,""))))),IF(G39="单开门",M39-28,IF(G39="双开门",M39-28,IF(G39="子母门",M39-28,IF(G39="单面套",0,IF(G39="双面套",0,"")))))),"")
def frame_quantity__ff_bfd6741e313a(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G39', '房门单', row - 39, col - 17)
    product_name_2 = lambda: ctx.reference('H39', '房门单', row - 39, col - 17)
    opening_quantity_3 = lambda: ctx.reference('M39', '房门单', row - 39, col - 17)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('<>', product_name_2(), '免漆'), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('-', opening_quantity_3(), 33), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('-', opening_quantity_3(), 33), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '子母门'), lambda: ctx.binary('-', opening_quantity_3(), 33), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('-', opening_quantity_3(), 28), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('-', opening_quantity_3(), 28), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '子母门'), lambda: ctx.binary('-', opening_quantity_3(), 28), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_fd80c4aba47b: 房门单 / 门高
# Source: 房门单!R39 (482 cells)
# Formula: =IFERROR(IF(H39<>"免漆",IF(G39="单开门",N39-52,IF(G39="双开门",(N39-46)/2,IF(G39="子母门",((N39)-46)&"("&((N39)-46-350-3+10)&","&(350)&")",IF(G39="单面套",0,IF(G39="双面套",0,""))))),IF(G39="单开门",N39-42,IF(G39="双开门",(N39-36)/2,IF(G39="子母门",((N39)-36)&"("&((N39)-36-350-3+10)&","&(350)&")",IF(G39="单面套",0,IF(G39="双面套",0,"")))))),"")
def leaf_height_mm__ff_fd80c4aba47b(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G39', '房门单', row - 39, col - 18)
    product_name_2 = lambda: ctx.reference('H39', '房门单', row - 39, col - 18)
    frame_height_mm_3 = lambda: ctx.reference('N39', '房门单', row - 39, col - 18)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('<>', product_name_2(), '免漆'), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('-', frame_height_mm_3(), 52), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('/', ctx.binary('-', frame_height_mm_3(), 46), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '子母门'), lambda: ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('-', frame_height_mm_3(), 46), '('), ctx.binary('+', ctx.binary('-', ctx.binary('-', ctx.binary('-', frame_height_mm_3(), 46), 350), 3), 10)), ','), 350), ')'), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('-', frame_height_mm_3(), 42), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('/', ctx.binary('-', frame_height_mm_3(), 36), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '子母门'), lambda: ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('-', frame_height_mm_3(), 36), '('), ctx.binary('+', ctx.binary('-', ctx.binary('-', ctx.binary('-', frame_height_mm_3(), 36), 350), 3), 10)), ','), 350), ')'), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: 0, lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: 0, lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_54d8b54acb61: 房门单 / 门宽
# Source: 房门单!S39 (482 cells)
# Formula: =IFERROR(_xlfn.IFS(OR(G39="单面套",G39="双面套",G39="移门套",G39="窗套"),"",OR(G39="单开门",G39="双开门",G39="子母门"),45),"")
def leaf_width_or_pair_description__ff_54d8b54acb61(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G39', '房门单', row - 39, col - 19)
    return ctx.call('IFERROR', [lambda: ctx.call('IFS', [lambda: ctx.call('OR', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: ctx.binary('=', 开启方向_1(), '移门套'), lambda: ctx.binary('=', 开启方向_1(), '窗套')], row=row, col=col), lambda: '', lambda: ctx.call('OR', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('=', 开启方向_1(), '子母门')], row=row, col=col), lambda: 45], row=row, col=col), lambda: ''], row=row, col=col)

# FF_834ec8fbd920: 房门单 / 门厚
# Source: 房门单!T39 (482 cells)
# Formula: =IFERROR(IF(G39="单开门",P39*1,IF(G39="双开门",P39*2,IF(G39="子母门",P39*2,IF(G39="单面套",P39*1,IF(G39="双面套",P39*1,""))))),"")
def leaf_thickness_mm__ff_834ec8fbd920(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('G39', '房门单', row - 39, col - 20)
    frame_wall_thickness_mm_2 = lambda: ctx.reference('P39', '房门单', row - 39, col - 20)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单开门'), lambda: ctx.binary('*', frame_wall_thickness_mm_2(), 1), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双开门'), lambda: ctx.binary('*', frame_wall_thickness_mm_2(), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '子母门'), lambda: ctx.binary('*', frame_wall_thickness_mm_2(), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '单面套'), lambda: ctx.binary('*', frame_wall_thickness_mm_2(), 1), lambda: ctx.call('IF', [lambda: ctx.binary('=', 开启方向_1(), '双面套'), lambda: ctx.binary('*', frame_wall_thickness_mm_2(), 1), lambda: ''], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_8f74c6a9c5f2: 房门单 / 门数量
# Source: 房门单!U39 (482 cells)
# Formula: =IFERROR(VLOOKUP($G39,拆单基础数据!$C:$S,MATCH(V$10,拆单基础数据!$C$1:$S$1,0),0),"")
def leaf_quantity__ff_8f74c6a9c5f2(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('$G39', '房门单', row - 39, col - 21)
    leaf_quantity_2 = lambda: ctx.reference('V$10', '房门单', row - 39, col - 21)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$C$1:$S$1', '房门单', row - 39, col - 21)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$C:$S', '房门单', row - 39, col - 21)
    return ctx.call('IFERROR', [lambda: ctx.call('VLOOKUP', [lambda: 开启方向_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: leaf_quantity_2(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: ''], row=row, col=col)

# FF_adf3afce97d5: 房门单 / 单位
# Source: 房门单!V39 (482 cells)
# Formula: =IFERROR(INDEX('物料目录(设计)'!$A:$U,MATCH($X39,'物料目录(设计)'!$G:$G,0),MATCH(R$3,'物料目录(设计)'!$A$1:$U$1,0)),"")
def uom__ff_adf3afce97d5(ctx, row, col):
    frame_area_m2_1 = lambda: ctx.reference('$X39', '房门单', row - 39, col - 22)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '房门单', row - 39, col - 22)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '房门单', row - 39, col - 22)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '房门单', row - 39, col - 22)
    语义待核对_R_5 = lambda: ctx.reference('R$3', '房门单', row - 39, col - 22)
    return ctx.call('IFERROR', [lambda: ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: frame_area_m2_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: 语义待核对_R_5(), lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_72f3a88de20b: 房门单 / 颜色/版号
# Source: 房门单!AD39 (482 cells)
# Formula: =IFERROR(VLOOKUP($G39,拆单基础数据!$C:$S,MATCH(AE$10,拆单基础数据!$C$1:$S$1,0),0),"")
def finish_reference__ff_72f3a88de20b(ctx, row, col):
    开启方向_1 = lambda: ctx.reference('$G39', '房门单', row - 39, col - 30)
    finish_reference_2 = lambda: ctx.reference('AE$10', '房门单', row - 39, col - 30)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$C$1:$S$1', '房门单', row - 39, col - 30)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$C:$S', '房门单', row - 39, col - 30)
    return ctx.call('IFERROR', [lambda: ctx.call('VLOOKUP', [lambda: 开启方向_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: finish_reference_2(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: ''], row=row, col=col)

# FF_e75f815a7f13: 房门单 / 计划系数
# Source: 房门单!AE39 (482 cells)
# Formula: =IFERROR(IF(OR(AD39="",L39=""),"",AD39*L39),"")
def 计划系数__ff_e75f815a7f13(ctx, row, col):
    finish_reference_1 = lambda: ctx.reference('AD39', '房门单', row - 39, col - 31)
    wall_thickness_mm_2 = lambda: ctx.reference('L39', '房门单', row - 39, col - 31)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', finish_reference_1(), ''), lambda: ctx.binary('=', wall_thickness_mm_2(), '')], row=row, col=col), lambda: '', lambda: ctx.binary('*', finish_reference_1(), wall_thickness_mm_2())], row=row, col=col), lambda: ''], row=row, col=col)

# FF_a43d769070cf: 房门单 / 计划量
# Source: 房门单!AF39 (482 cells)
# Formula: =IFERROR((Q39/1000*R39/1000*2*T39+M39/1000*O39/1000*2*P39+N39/1000*O39/1000*P39),"")
def 计划量__ff_a43d769070cf(ctx, row, col):
    opening_quantity_1 = lambda: ctx.reference('M39', '房门单', row - 39, col - 32)
    frame_height_mm_2 = lambda: ctx.reference('N39', '房门单', row - 39, col - 32)
    frame_width_mm_3 = lambda: ctx.reference('O39', '房门单', row - 39, col - 32)
    frame_wall_thickness_mm_4 = lambda: ctx.reference('P39', '房门单', row - 39, col - 32)
    frame_quantity_5 = lambda: ctx.reference('Q39', '房门单', row - 39, col - 32)
    leaf_height_mm_6 = lambda: ctx.reference('R39', '房门单', row - 39, col - 32)
    leaf_thickness_mm_7 = lambda: ctx.reference('T39', '房门单', row - 39, col - 32)
    return ctx.call('IFERROR', [lambda: ctx.binary('+', ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', frame_quantity_5(), 1000), leaf_height_mm_6()), 1000), 2), leaf_thickness_mm_7()), ctx.binary('*', ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', opening_quantity_1(), 1000), frame_width_mm_3()), 1000), 2), frame_wall_thickness_mm_4())), ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', frame_height_mm_2(), 1000), frame_width_mm_3()), 1000), frame_wall_thickness_mm_4())), lambda: ''], row=row, col=col)

# FF_f4cfad53d5e1: 三合一生产单 / 语义待核对_F
# Source: 三合一生产单!F2 (1 cells)
# Formula: =CONCATENATE(表头!$C$3,"-",J2)
def 语义待核对_F__ff_f4cfad53d5e1(ctx, row, col):
    订单类别_1 = lambda: ctx.reference('J2', '三合一生产单', row - 2, col - 6)
    订单编号_2 = lambda: ctx.reference('表头!$C$3', '三合一生产单', row - 2, col - 6)
    return ctx.call('CONCATENATE', [lambda: 订单编号_2(), lambda: '-', lambda: 订单类别_1()], row=row, col=col)

# FF_94068ddf9c8c: 三合一生产单 / 订单交期
# Source: 三合一生产单!O2 (1 cells)
# Formula: =表头!N3
def 订单交期__ff_94068ddf9c8c(ctx, row, col):
    发货_1 = lambda: ctx.reference('表头!N3', '三合一生产单', row - 2, col - 15)
    return 发货_1()

# FF_036fc772ded4: 三合一生产单 / 生产周期
# Source: 三合一生产单!R2 (1 cells)
# Formula: =_xlfn.CONCAT("木",ROUND((O2-L2)*0.6,0),"天  ",CHAR(10),"油",ROUND((O2-L2)*0.4,0),"天")
def 生产周期__ff_036fc772ded4(ctx, row, col):
    下单日期_1 = lambda: ctx.reference('L2', '三合一生产单', row - 2, col - 18)
    订单交期_2 = lambda: ctx.reference('O2', '三合一生产单', row - 2, col - 18)
    return ctx.call('CONCAT', [lambda: '木', lambda: ctx.call('ROUND', [lambda: ctx.binary('*', ctx.binary('-', 订单交期_2(), 下单日期_1()), 0.6), lambda: 0], row=row, col=col), lambda: '天  ', lambda: ctx.call('CHAR', [lambda: 10], row=row, col=col), lambda: '油', lambda: ctx.call('ROUND', [lambda: ctx.binary('*', ctx.binary('-', 订单交期_2(), 下单日期_1()), 0.4), lambda: 0], row=row, col=col), lambda: '天'], row=row, col=col)

# FF_f87f9bee09a9: 三合一生产单 / 语义待核对_F
# Source: 三合一生产单!F3 (1 cells)
# Formula: =表头!C4
def 语义待核对_F__ff_f87f9bee09a9(ctx, row, col):
    地_址_1 = lambda: ctx.reference('表头!C4', '三合一生产单', row - 3, col - 6)
    return 地_址_1()

# FF_0fa5f36896a8: 三合一生产单 / 油漆工艺/木皮/坯板
# Source: 三合一生产单!L3 (1 cells)
# Formula: =INDEX('物料目录(设计)'!$A:$U,MATCH($H$3,'物料目录(设计)'!$G:$G,0),MATCH("油漆工艺(必填)",'物料目录(设计)'!$A$1:$U$1,0))&"/"&(INDEX('物料目录(设计)'!$A:$U,MATCH($H$3,'物料目录(设计)'!$G:$G,0),MATCH("木皮种类",'物料目录(设计)'!$A$1:$U$1,0)))&"/"&(INDEX('物料目录(设计)'!$A:$U,MATCH($H$3,'物料目录(设计)'!$G:$G,0),MATCH("坯板材质",'物料目录(设计)'!$A$1:$U$1,0)))
def 油漆工艺_木皮_坯板__ff_0fa5f36896a8(ctx, row, col):
    色版号_1 = lambda: ctx.reference('$H$3', '三合一生产单', row - 3, col - 12)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '三合一生产单', row - 3, col - 12)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '三合一生产单', row - 3, col - 12)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '三合一生产单', row - 3, col - 12)
    return ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: 色版号_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '油漆工艺(必填)', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col), '/'), ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: 色版号_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '木皮种类', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col)), '/'), ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: 色版号_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '坯板材质', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col))

# FF_4c2a5d2cdaa3: 三合一生产单 / 客户等级
# Source: 三合一生产单!Q3 (1 cells)
# Formula: =VLOOKUP(H2,客户!$A:$C,MATCH("等级",客户!$A$1:$C$1,0),0)
def 客户等级__ff_4c2a5d2cdaa3(ctx, row, col):
    客户名称_1 = lambda: ctx.reference('H2', '三合一生产单', row - 3, col - 17)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('客户!$A$1:$C$1', '三合一生产单', row - 3, col - 17)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('客户!$A:$C', '三合一生产单', row - 3, col - 17)
    return ctx.call('VLOOKUP', [lambda: 客户名称_1(), lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: '等级', lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col)

# FF_71c31112a64e: 三合一生产单 / 白色/绿呈
# Source: 三合一生产单!T3 (1 cells)
# Formula: =表头!P2
def 白色_绿呈__ff_71c31112a64e(ctx, row, col):
    邓尚荣_1 = lambda: ctx.reference('表头!P2', '三合一生产单', row - 3, col - 20)
    return 邓尚荣_1()

# FF_0a2947b61045: 三合一生产单 / 白色/绿呈
# Source: 三合一生产单!U3 (1 cells)
# Formula: =表头!N2
def 白色_绿呈__ff_0a2947b61045(ctx, row, col):
    语义待核对_N_1 = lambda: ctx.reference('表头!N2', '三合一生产单', row - 3, col - 21)
    return 语义待核对_N_1()

# FF_1e42da43e489: 三合一生产单 / 语义待核对_M
# Source: 三合一生产单!M5 (1 cells)
# Formula: =SUM(M7:M73)
def 语义待核对_M__ff_1e42da43e489(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('M7:M73', '三合一生产单', row - 5, col - 13)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_01ebedf7327c: 三合一生产单 / 语义待核对_Q
# Source: 三合一生产单!Q5 (1 cells)
# Formula: =SUM(Q7:Q73)
def 语义待核对_Q__ff_01ebedf7327c(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('Q7:Q73', '三合一生产单', row - 5, col - 17)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_ea40795bcbec: 三合一生产单 / 语义待核对_R
# Source: 三合一生产单!R5 (1 cells)
# Formula: =SUM(R7:R73)
def 语义待核对_R__ff_ea40795bcbec(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('R7:R73', '三合一生产单', row - 5, col - 18)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_3862905331ef: 三合一生产单 / 语义待核对_S
# Source: 三合一生产单!S5 (1 cells)
# Formula: =SUM(S7:S73)
def 语义待核对_S__ff_3862905331ef(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('S7:S73', '三合一生产单', row - 5, col - 19)
    return ctx.call('SUM', [lambda: lookup_or_aggregate_range_1()], row=row, col=col)

# FF_2204175db59c: 三合一生产单 / 序号
# Source: 三合一生产单!A7 (67 cells)
# Formula: =ROW()-6
def row_number__ff_2204175db59c(ctx, row, col):
    return ctx.binary('-', ctx.call('ROW', [], row=row, col=col), 6)

# FF_41e386154efe: 三合一生产单 / 物料编码(必填)
# Source: 三合一生产单!B7 (67 cells)
# Formula: =IFERROR(INDEX('物料目录(设计)'!$A$1:$U$103,MATCH(V7,'物料目录(设计)'!$G$1:$G$103,0),MATCH("物料编码(必填)",'物料目录(设计)'!$A$1:$U$1,0)),"")
def material_code__ff_41e386154efe(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '三合一生产单', row - 7, col - 2)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$103", '三合一生产单', row - 7, col - 2)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$G$1:$G$103", '三合一生产单', row - 7, col - 2)
    finish_reference_4 = lambda: ctx.reference('V7', '三合一生产单', row - 7, col - 2)
    return ctx.call('IFERROR', [lambda: ctx.call('INDEX', [lambda: lookup_or_aggregate_range_2(), lambda: ctx.call('MATCH', [lambda: finish_reference_4(), lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: '物料编码(必填)', lambda: lookup_or_aggregate_range_1(), lambda: 0], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_10d885884644: 三合一生产单 / 工艺编码(必填)
# Source: 三合一生产单!C7 (67 cells)
# Formula: =IFERROR(VLOOKUP(I7,油漆工艺及编码!$A$1:$B$21,MATCH("工艺编码",油漆工艺及编码!$A$1:$B$1,0),0)&"/"&VLOOKUP($E7,拆单基础数据!$A:$S,MATCH("类别编码",拆单基础数据!$A$1:$S$1,0),0),"")
def process_code__ff_10d885884644(ctx, row, col):
    产品类别_必填_1 = lambda: ctx.reference('$E7', '三合一生产单', row - 7, col - 3)
    paint_process_2 = lambda: ctx.reference('I7', '三合一生产单', row - 7, col - 3)
    lookup_or_aggregate_range_3 = lambda: ctx.reference('拆单基础数据!$A$1:$S$1', '三合一生产单', row - 7, col - 3)
    lookup_or_aggregate_range_4 = lambda: ctx.reference('拆单基础数据!$A:$S', '三合一生产单', row - 7, col - 3)
    lookup_or_aggregate_range_5 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$1', '三合一生产单', row - 7, col - 3)
    lookup_or_aggregate_range_6 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$21', '三合一生产单', row - 7, col - 3)
    return ctx.call('IFERROR', [lambda: ctx.binary('&', ctx.binary('&', ctx.call('VLOOKUP', [lambda: paint_process_2(), lambda: lookup_or_aggregate_range_6(), lambda: ctx.call('MATCH', [lambda: '工艺编码', lambda: lookup_or_aggregate_range_5(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), '/'), ctx.call('VLOOKUP', [lambda: 产品类别_必填_1(), lambda: lookup_or_aggregate_range_4(), lambda: ctx.call('MATCH', [lambda: '类别编码', lambda: lookup_or_aggregate_range_3(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col)), lambda: ''], row=row, col=col)

# FF_5f1b2a1dc7cf: 三合一生产单 / 订单类型（必填）
# Source: 三合一生产单!D7 (67 cells)
# Formula: =IF($B7="","",$J$2)
def 订单类型_必填__ff_5f1b2a1dc7cf(ctx, row, col):
    material_code_1 = lambda: ctx.reference('$B7', '三合一生产单', row - 7, col - 4)
    订单类别_2 = lambda: ctx.reference('$J$2', '三合一生产单', row - 7, col - 4)
    return ctx.call('IF', [lambda: ctx.binary('=', material_code_1(), ''), lambda: '', lambda: 订单类别_2()], row=row, col=col)

# FF_23ef55bd6d2e: 三合一生产单 / 油漆工艺(必填)
# Source: 三合一生产单!I7 (67 cells)
# Formula: =IFERROR(INDEX('物料目录(设计)'!$A:$U,MATCH($V7,'物料目录(设计)'!$G:$G,0),MATCH(I$6,'物料目录(设计)'!$A$1:$U$1,0)),"")
def paint_process__ff_23ef55bd6d2e(ctx, row, col):
    finish_reference_1 = lambda: ctx.reference('$V7', '三合一生产单', row - 7, col - 9)
    lookup_or_aggregate_range_2 = lambda: ctx.reference("'物料目录(设计)'!$A$1:$U$1", '三合一生产单', row - 7, col - 9)
    lookup_or_aggregate_range_3 = lambda: ctx.reference("'物料目录(设计)'!$A:$U", '三合一生产单', row - 7, col - 9)
    lookup_or_aggregate_range_4 = lambda: ctx.reference("'物料目录(设计)'!$G:$G", '三合一生产单', row - 7, col - 9)
    型号_5 = lambda: ctx.reference('I$6', '三合一生产单', row - 7, col - 9)
    return ctx.call('IFERROR', [lambda: ctx.call('INDEX', [lambda: lookup_or_aggregate_range_3(), lambda: ctx.call('MATCH', [lambda: finish_reference_1(), lambda: lookup_or_aggregate_range_4(), lambda: 0], row=row, col=col), lambda: ctx.call('MATCH', [lambda: 型号_5(), lambda: lookup_or_aggregate_range_2(), lambda: 0], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_29b3f9b532a4: 三合一生产单 / 见光平方
# Source: 三合一生产单!Q7 (67 cells)
# Formula: =IFERROR(_xlfn.IFS(O7="单",J7/1000*K7/1000*M7,O7="双",J7/1000*K7/1000*M7*2,O7="白坯",J7/1000*0),"")
def visible_area_m2__ff_29b3f9b532a4(ctx, row, col):
    height_mm_1 = lambda: ctx.reference('J7', '三合一生产单', row - 7, col - 17)
    width_mm_2 = lambda: ctx.reference('K7', '三合一生产单', row - 7, col - 17)
    quantity_3 = lambda: ctx.reference('M7', '三合一生产单', row - 7, col - 17)
    exposed_sides_4 = lambda: ctx.reference('O7', '三合一生产单', row - 7, col - 17)
    return ctx.call('IFERROR', [lambda: ctx.call('IFS', [lambda: ctx.binary('=', exposed_sides_4(), '单'), lambda: ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), width_mm_2()), 1000), quantity_3()), lambda: ctx.binary('=', exposed_sides_4(), '双'), lambda: ctx.binary('*', ctx.binary('*', ctx.binary('/', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), width_mm_2()), 1000), quantity_3()), 2), lambda: ctx.binary('=', exposed_sides_4(), '白坯'), lambda: ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), 0)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_100e47a2666a: 三合一生产单 / 封边长度
# Source: 三合一生产单!R7 (67 cells)
# Formula: =IFERROR(IF(P7="一长",J7/1000*M7,IF(P7="一宽",K7/1000*M7,IF(P7="两长",J7/1000*M7*2,IF(P7="两宽",K7/1000*M7*2,IF(P7="一长一宽",J7/1000*M7+K7/1000*M7,IF(P7="一长两宽",J7/1000*M7+K7/1000*M7*2,IF(P7="两长一宽",J7/1000*M7*2+K7/1000*M7,IF(P7="四边",J7/1000*M7*2+K7/1000*M7*2,IF(P7="白坯",J7/1000*0))))))))),"")
def edge_length_m__ff_100e47a2666a(ctx, row, col):
    height_mm_1 = lambda: ctx.reference('J7', '三合一生产单', row - 7, col - 18)
    width_mm_2 = lambda: ctx.reference('K7', '三合一生产单', row - 7, col - 18)
    quantity_3 = lambda: ctx.reference('M7', '三合一生产单', row - 7, col - 18)
    edge_selection_4 = lambda: ctx.reference('P7', '三合一生产单', row - 7, col - 18)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '一长'), lambda: ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), quantity_3()), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '一宽'), lambda: ctx.binary('*', ctx.binary('/', width_mm_2(), 1000), quantity_3()), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '两长'), lambda: ctx.binary('*', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), quantity_3()), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '两宽'), lambda: ctx.binary('*', ctx.binary('*', ctx.binary('/', width_mm_2(), 1000), quantity_3()), 2), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '一长一宽'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), quantity_3()), ctx.binary('*', ctx.binary('/', width_mm_2(), 1000), quantity_3())), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '一长两宽'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), quantity_3()), ctx.binary('*', ctx.binary('*', ctx.binary('/', width_mm_2(), 1000), quantity_3()), 2)), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '两长一宽'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), quantity_3()), 2), ctx.binary('*', ctx.binary('/', width_mm_2(), 1000), quantity_3())), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '四边'), lambda: ctx.binary('+', ctx.binary('*', ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), quantity_3()), 2), ctx.binary('*', ctx.binary('*', ctx.binary('/', width_mm_2(), 1000), quantity_3()), 2)), lambda: ctx.call('IF', [lambda: ctx.binary('=', edge_selection_4(), '白坯'), lambda: ctx.binary('*', ctx.binary('/', height_mm_1(), 1000), 0)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_e1734e5f3263: 三合一生产单 / 产品平方
# Source: 三合一生产单!S7 (67 cells)
# Formula: =IFERROR(IF(OR(J7="",K7=""),"",J7*K7*M7/1000000),"")
def product_area_m2__ff_e1734e5f3263(ctx, row, col):
    height_mm_1 = lambda: ctx.reference('J7', '三合一生产单', row - 7, col - 19)
    width_mm_2 = lambda: ctx.reference('K7', '三合一生产单', row - 7, col - 19)
    quantity_3 = lambda: ctx.reference('M7', '三合一生产单', row - 7, col - 19)
    return ctx.call('IFERROR', [lambda: ctx.call('IF', [lambda: ctx.call('OR', [lambda: ctx.binary('=', height_mm_1(), ''), lambda: ctx.binary('=', width_mm_2(), '')], row=row, col=col), lambda: '', lambda: ctx.binary('/', ctx.binary('*', ctx.binary('*', height_mm_1(), width_mm_2()), quantity_3()), 1000000)], row=row, col=col), lambda: ''], row=row, col=col)

# FF_fd290b0904b0: 三合一生产单 / 特殊色版
# Source: 三合一生产单!T7 (37 cells)
# Formula: =IF(E7="","",IF(V7=$H$3,"",V7))
def 特殊色版__ff_fd290b0904b0(ctx, row, col):
    色版号_1 = lambda: ctx.reference('$H$3', '三合一生产单', row - 7, col - 20)
    产品类别_必填_2 = lambda: ctx.reference('E7', '三合一生产单', row - 7, col - 20)
    finish_reference_3 = lambda: ctx.reference('V7', '三合一生产单', row - 7, col - 20)
    return ctx.call('IF', [lambda: ctx.binary('=', 产品类别_必填_2(), ''), lambda: '', lambda: ctx.call('IF', [lambda: ctx.binary('=', finish_reference_3(), 色版号_1()), lambda: '', lambda: finish_reference_3()], row=row, col=col)], row=row, col=col)

# FF_7e8ba2374d7c: 三合一生产单 / 颜色/版号
# Source: 三合一生产单!V7 (67 cells)
# Formula: =IF($E7="","",$H$3)
def finish_reference__ff_7e8ba2374d7c(ctx, row, col):
    产品类别_必填_1 = lambda: ctx.reference('$E7', '三合一生产单', row - 7, col - 22)
    色版号_2 = lambda: ctx.reference('$H$3', '三合一生产单', row - 7, col - 22)
    return ctx.call('IF', [lambda: ctx.binary('=', 产品类别_必填_1(), ''), lambda: '', lambda: 色版号_2()], row=row, col=col)

# FF_848428625aa3: 三合一生产单 / 材料领用量
# Source: 三合一生产单!AG30 (1 cells)
# Formula: =AG29*1.2
def 材料领用量__ff_848428625aa3(ctx, row, col):
    材料用量_1 = lambda: ctx.reference('AG29', '三合一生产单', row - 30, col - 33)
    return ctx.binary('*', 材料用量_1(), 1.2)

# FF_2bd1811c67f8: 三合一生产单 / 语义待核对_AH
# Source: 三合一生产单!AH30 (1 cells)
# Formula: =AH29*1.2
def 语义待核对_AH__ff_2bd1811c67f8(ctx, row, col):
    语义待核对_AH_1 = lambda: ctx.reference('AH29', '三合一生产单', row - 30, col - 34)
    return ctx.binary('*', 语义待核对_AH_1(), 1.2)

# FF_bcd05cc6e880: 三合一生产单 / 语义待核对_AI
# Source: 三合一生产单!AI30 (1 cells)
# Formula: =AI29*1.2
def 语义待核对_AI__ff_bcd05cc6e880(ctx, row, col):
    语义待核对_AI_1 = lambda: ctx.reference('AI29', '三合一生产单', row - 30, col - 35)
    return ctx.binary('*', 语义待核对_AI_1(), 1.2)

# FF_4043c1179fd9: 三合一生产单 / 语义待核对_AJ
# Source: 三合一生产单!AJ30 (1 cells)
# Formula: =AJ29*1.2
def 语义待核对_AJ__ff_4043c1179fd9(ctx, row, col):
    语义待核对_AJ_1 = lambda: ctx.reference('AJ29', '三合一生产单', row - 30, col - 36)
    return ctx.binary('*', 语义待核对_AJ_1(), 1.2)

# FF_381619e849ca: 三合一生产单 / 语义待核对_AK
# Source: 三合一生产单!AK30 (1 cells)
# Formula: =AK29*1.2
def 语义待核对_AK__ff_381619e849ca(ctx, row, col):
    语义待核对_AK_1 = lambda: ctx.reference('AK29', '三合一生产单', row - 30, col - 37)
    return ctx.binary('*', 语义待核对_AK_1(), 1.2)

# FF_78f188dacf66: 三合一生产单 / 语义待核对_AL
# Source: 三合一生产单!AL30 (1 cells)
# Formula: =AL29*1.2
def 语义待核对_AL__ff_78f188dacf66(ctx, row, col):
    语义待核对_AL_1 = lambda: ctx.reference('AL29', '三合一生产单', row - 30, col - 38)
    return ctx.binary('*', 语义待核对_AL_1(), 1.2)

# FF_5c9579580a9f: 三合一生产单 / 2800*1220光板
# Source: 三合一生产单!AM30 (1 cells)
# Formula: =AM29*1.2
def field_2800_1220光板__ff_5c9579580a9f(ctx, row, col):
    field_2800_1220光板_1 = lambda: ctx.reference('AM29', '三合一生产单', row - 30, col - 39)
    return ctx.binary('*', field_2800_1220光板_1(), 1.2)

# FF_2b7cdd184e7c: 三合一生产单 / 语义待核对_AN
# Source: 三合一生产单!AN30 (1 cells)
# Formula: =AN29*1.2
def 语义待核对_AN__ff_2b7cdd184e7c(ctx, row, col):
    语义待核对_AN_1 = lambda: ctx.reference('AN29', '三合一生产单', row - 30, col - 40)
    return ctx.binary('*', 语义待核对_AN_1(), 1.2)

# FF_5540d6168ca2: 三合一生产单 / 语义待核对_AO
# Source: 三合一生产单!AO30 (1 cells)
# Formula: =AO29*1.2
def 语义待核对_AO__ff_5540d6168ca2(ctx, row, col):
    语义待核对_AO_1 = lambda: ctx.reference('AO29', '三合一生产单', row - 30, col - 41)
    return ctx.binary('*', 语义待核对_AO_1(), 1.2)

# FF_5df1a11391ce: 三合一生产单 / 语义待核对_AP
# Source: 三合一生产单!AP30 (1 cells)
# Formula: =AP29*1.2
def 语义待核对_AP__ff_5df1a11391ce(ctx, row, col):
    语义待核对_AP_1 = lambda: ctx.reference('AP29', '三合一生产单', row - 30, col - 42)
    return ctx.binary('*', 语义待核对_AP_1(), 1.2)

# FF_4c6c4a7b24cb: 三合一生产单 / 语义待核对_AQ
# Source: 三合一生产单!AQ30 (1 cells)
# Formula: =AQ29*1.2
def 语义待核对_AQ__ff_4c6c4a7b24cb(ctx, row, col):
    语义待核对_AQ_1 = lambda: ctx.reference('AQ29', '三合一生产单', row - 30, col - 43)
    return ctx.binary('*', 语义待核对_AQ_1(), 1.2)

# FF_d5a8ff252745: 三合一生产单 / 语义待核对_AR
# Source: 三合一生产单!AR30 (1 cells)
# Formula: =AR29*1.2
def 语义待核对_AR__ff_d5a8ff252745(ctx, row, col):
    语义待核对_AR_1 = lambda: ctx.reference('AR29', '三合一生产单', row - 30, col - 44)
    return ctx.binary('*', 语义待核对_AR_1(), 1.2)

# FF_9db72672de43: 客户 / 序号
# Source: 客户!B2 (82 cells)
# Formula: =ROW()-1
def row_number__ff_9db72672de43(ctx, row, col):
    return ctx.binary('-', ctx.call('ROW', [], row=row, col=col), 1)

# FF_76ac97cac847: 物料目录(设计) / 物料名称(必填)
# Source: 物料目录(设计)!A2 (62 cells)
# Formula: =C2&I2
def 物料名称_必填__ff_76ac97cac847(ctx, row, col):
    paint_process_1 = lambda: ctx.reference('C2', '物料目录(设计)', row - 2, col - 1)
    坯板材质_2 = lambda: ctx.reference('I2', '物料目录(设计)', row - 2, col - 1)
    return ctx.binary('&', paint_process_1(), 坯板材质_2())

# FF_0e6b4cbb3da5: 物料目录(设计) / 物料编码(必填)
# Source: 物料目录(设计)!B2 (4 cells)
# Formula: =IFERROR(VLOOKUP($C2,油漆工艺及编码!$A$1:$B$21,MATCH("工艺编码",油漆工艺及编码!$A$1:$B$1,0),0)&TEXT(VLOOKUP(H2,'木皮目录（设计）'!$A$2:$B$60,MATCH("序号",'木皮目录（设计）'!$A$1:$B$1,0),0),"00")&TEXT(VLOOKUP($I2,'坯板目录（设计）'!$A$1:$B$17,MATCH("序号",'坯板目录（设计）'!$A$1:$B$1,0),0),"00")&TEXT(COUNTIF($A2:$A$6,$A2),"000"),"")
def material_code__ff_0e6b4cbb3da5(ctx, row, col):
    物料名称_必填_1 = lambda: ctx.reference('$A2', '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_2 = lambda: ctx.reference('$A2:$A$6', '物料目录(设计)', row - 2, col - 2)
    paint_process_3 = lambda: ctx.reference('$C2', '物料目录(设计)', row - 2, col - 2)
    坯板材质_4 = lambda: ctx.reference('$I2', '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_5 = lambda: ctx.reference("'坯板目录（设计）'!$A$1:$B$1", '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_6 = lambda: ctx.reference("'坯板目录（设计）'!$A$1:$B$17", '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_7 = lambda: ctx.reference("'木皮目录（设计）'!$A$1:$B$1", '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_8 = lambda: ctx.reference("'木皮目录（设计）'!$A$2:$B$60", '物料目录(设计)', row - 2, col - 2)
    木皮种类_9 = lambda: ctx.reference('H2', '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_10 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$1', '物料目录(设计)', row - 2, col - 2)
    lookup_or_aggregate_range_11 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$21', '物料目录(设计)', row - 2, col - 2)
    return ctx.call('IFERROR', [lambda: ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.call('VLOOKUP', [lambda: paint_process_3(), lambda: lookup_or_aggregate_range_11(), lambda: ctx.call('MATCH', [lambda: '工艺编码', lambda: lookup_or_aggregate_range_10(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), ctx.call('TEXT', [lambda: ctx.call('VLOOKUP', [lambda: 木皮种类_9(), lambda: lookup_or_aggregate_range_8(), lambda: ctx.call('MATCH', [lambda: '序号', lambda: lookup_or_aggregate_range_7(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: '00'], row=row, col=col)), ctx.call('TEXT', [lambda: ctx.call('VLOOKUP', [lambda: 坯板材质_4(), lambda: lookup_or_aggregate_range_6(), lambda: ctx.call('MATCH', [lambda: '序号', lambda: lookup_or_aggregate_range_5(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: '00'], row=row, col=col)), ctx.call('TEXT', [lambda: ctx.call('COUNTIF', [lambda: lookup_or_aggregate_range_2(), lambda: 物料名称_必填_1()], row=row, col=col), lambda: '000'], row=row, col=col)), lambda: ''], row=row, col=col)

# FF_3ecf442b0e55: 物料目录(设计) / 物料编码(必填)
# Source: 物料目录(设计)!B6 (98 cells)
# Formula: =IFERROR(VLOOKUP($C6,油漆工艺及编码!$A$1:$B$21,MATCH("工艺编码",油漆工艺及编码!$A$1:$B$1,0),0)&TEXT(VLOOKUP(H6,'木皮目录（设计）'!$A$2:$B$60,MATCH("序号",'木皮目录（设计）'!$A$1:$B$1,0),0),"00")&TEXT(VLOOKUP($I6,'坯板目录（设计）'!$A$1:$B$17,MATCH("序号",'坯板目录（设计）'!$A$1:$B$1,0),0),"00")&TEXT(COUNTIF($A$6:$A6,$A6),"000"),"")
def material_code__ff_3ecf442b0e55(ctx, row, col):
    lookup_or_aggregate_range_1 = lambda: ctx.reference('$A$6:$A6', '物料目录(设计)', row - 6, col - 2)
    物料名称_必填_2 = lambda: ctx.reference('$A6', '物料目录(设计)', row - 6, col - 2)
    paint_process_3 = lambda: ctx.reference('$C6', '物料目录(设计)', row - 6, col - 2)
    坯板材质_4 = lambda: ctx.reference('$I6', '物料目录(设计)', row - 6, col - 2)
    lookup_or_aggregate_range_5 = lambda: ctx.reference("'坯板目录（设计）'!$A$1:$B$1", '物料目录(设计)', row - 6, col - 2)
    lookup_or_aggregate_range_6 = lambda: ctx.reference("'坯板目录（设计）'!$A$1:$B$17", '物料目录(设计)', row - 6, col - 2)
    lookup_or_aggregate_range_7 = lambda: ctx.reference("'木皮目录（设计）'!$A$1:$B$1", '物料目录(设计)', row - 6, col - 2)
    lookup_or_aggregate_range_8 = lambda: ctx.reference("'木皮目录（设计）'!$A$2:$B$60", '物料目录(设计)', row - 6, col - 2)
    木皮种类_9 = lambda: ctx.reference('H6', '物料目录(设计)', row - 6, col - 2)
    lookup_or_aggregate_range_10 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$1', '物料目录(设计)', row - 6, col - 2)
    lookup_or_aggregate_range_11 = lambda: ctx.reference('油漆工艺及编码!$A$1:$B$21', '物料目录(设计)', row - 6, col - 2)
    return ctx.call('IFERROR', [lambda: ctx.binary('&', ctx.binary('&', ctx.binary('&', ctx.call('VLOOKUP', [lambda: paint_process_3(), lambda: lookup_or_aggregate_range_11(), lambda: ctx.call('MATCH', [lambda: '工艺编码', lambda: lookup_or_aggregate_range_10(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), ctx.call('TEXT', [lambda: ctx.call('VLOOKUP', [lambda: 木皮种类_9(), lambda: lookup_or_aggregate_range_8(), lambda: ctx.call('MATCH', [lambda: '序号', lambda: lookup_or_aggregate_range_7(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: '00'], row=row, col=col)), ctx.call('TEXT', [lambda: ctx.call('VLOOKUP', [lambda: 坯板材质_4(), lambda: lookup_or_aggregate_range_6(), lambda: ctx.call('MATCH', [lambda: '序号', lambda: lookup_or_aggregate_range_5(), lambda: 0], row=row, col=col), lambda: 0], row=row, col=col), lambda: '00'], row=row, col=col)), ctx.call('TEXT', [lambda: ctx.call('COUNTIF', [lambda: lookup_or_aggregate_range_1(), lambda: 物料名称_必填_2()], row=row, col=col), lambda: '000'], row=row, col=col)), lambda: ''], row=row, col=col)

FUNCTIONS = {
    'FF_b689b5b31e1f': 横线__ff_b689b5b31e1f,
    'FF_e9d129d84a66': 竖线__ff_e9d129d84a66,
    'FF_a1b554a798a5': 语义待核对_F__ff_a1b554a798a5,
    'FF_d3fc62f3d1cb': 订单交期__ff_d3fc62f3d1cb,
    'FF_c44e95df4ffb': 周期__ff_c44e95df4ffb,
    'FF_0c81aaeeb4aa': 语义待核对_F__ff_0c81aaeeb4aa,
    'FF_743d4f108af9': 油漆工艺__ff_743d4f108af9,
    'FF_916c19053114': 木皮__ff_916c19053114,
    'FF_d28514ba850e': 坯板__ff_d28514ba850e,
    'FF_82df6461f465': 客户等级__ff_82df6461f465,
    'FF_6131298d871e': field_60_18__ff_6131298d871e,
    'FF_1fbc94502ca1': field_50_18__ff_1fbc94502ca1,
    'FF_99f21de6ab30': 空套__ff_99f21de6ab30,
    'FF_ad9acf8a80f4': 空套板__ff_ad9acf8a80f4,
    'FF_fa2dd4db99da': 门头板__ff_fa2dd4db99da,
    'FF_78211945bc71': 门扇__ff_78211945bc71,
    'FF_13345f9170f0': 门套__ff_13345f9170f0,
    'FF_b69691813325': 门套板__ff_b69691813325,
    'FF_fd9445ff72f3': visible_area_m2__ff_fd9445ff72f3,
    'FF_2f8e4b6fc8b6': frame_area_m2__ff_2f8e4b6fc8b6,
    'FF_04a7ba17119b': 门面板__ff_04a7ba17119b,
    'FF_7e6207dbd768': row_number__ff_7e6207dbd768,
    'FF_01649050f825': material_code__ff_01649050f825,
    'FF_7eda01a9afff': process_code__ff_7eda01a9afff,
    'FF_7365d3f62375': 订单类型_必填__ff_7365d3f62375,
    'FF_fc6fb8c4ccd7': paint_process__ff_fc6fb8c4ccd7,
    'FF_e5d7975b2645': frame_height_mm__ff_e5d7975b2645,
    'FF_cd8350bcc8e1': frame_width_mm__ff_cd8350bcc8e1,
    'FF_94d7bbd1bcc8': frame_wall_thickness_mm__ff_94d7bbd1bcc8,
    'FF_94558f4e733f': frame_quantity__ff_94558f4e733f,
    'FF_e55e6ecbe2f5': leaf_height_mm__ff_e55e6ecbe2f5,
    'FF_2ddbe2157997': leaf_width_or_pair_description__ff_2ddbe2157997,
    'FF_2b9e867ba950': leaf_thickness_mm__ff_2b9e867ba950,
    'FF_16c1f81ef2f0': leaf_quantity__ff_16c1f81ef2f0,
    'FF_1aea682eff65': uom__ff_1aea682eff65,
    'FF_bb1154f33707': visible_area_m2__ff_bb1154f33707,
    'FF_2754778664d5': frame_area_m2__ff_2754778664d5,
    'FF_085a2f26fd1f': door_face_panel_count__ff_085a2f26fd1f,
    'FF_9f31702900d0': edge_veneer_25_length_m__ff_9f31702900d0,
    'FF_72be7690c27f': edge_veneer_50_length_m__ff_72be7690c27f,
    'FF_f4ef404f3311': 特殊色版__ff_f4ef404f3311,
    'FF_75e037f1153b': finish_reference__ff_75e037f1153b,
    'FF_4d62764356d5': 计划系数__ff_4d62764356d5,
    'FF_730c9031d59f': 计划量__ff_730c9031d59f,
    'FF_7434f7b35fba': 语义待核对_AJ__ff_7434f7b35fba,
    'FF_1e1f4b3a2bf8': 套板板材平方__ff_1e1f4b3a2bf8,
    'FF_57dd115fa0d3': 语义待核对_AL__ff_57dd115fa0d3,
    'FF_2f2884e4ae34': 是否为空套__ff_2f2884e4ae34,
    'FF_a64e35ccfd3b': 横加__ff_a64e35ccfd3b,
    'FF_aa14e1627fc7': 竖加__ff_aa14e1627fc7,
    'FF_f6a8f0521d90': 线宽__ff_f6a8f0521d90,
    'FF_9791bfccc541': 单边横线__ff_9791bfccc541,
    'FF_4412a3b79417': 竖线净长__ff_4412a3b79417,
    'FF_56638d1b30f9': 横线净长__ff_56638d1b30f9,
    'FF_fc5f706a0412': 竖线开料长__ff_fc5f706a0412,
    'FF_6172b8a3a02a': 竖线条数__ff_6172b8a3a02a,
    'FF_38be392bce2b': 横线开料长__ff_38be392bce2b,
    'FF_1e520fd1a320': 横线条数__ff_1e520fd1a320,
    'FF_c7a6342dcce5': 线条单双__ff_c7a6342dcce5,
    'FF_046f9be4c4c5': frame_area_m2__ff_046f9be4c4c5,
    'FF_8094bb56a5b1': paint_process__ff_8094bb56a5b1,
    'FF_237f9831456e': opening_quantity__ff_237f9831456e,
    'FF_533b4f331679': frame_height_mm__ff_533b4f331679,
    'FF_884dcddf3c1d': frame_width_mm__ff_884dcddf3c1d,
    'FF_f9342bb093c0': frame_wall_thickness_mm__ff_f9342bb093c0,
    'FF_bfd6741e313a': frame_quantity__ff_bfd6741e313a,
    'FF_fd80c4aba47b': leaf_height_mm__ff_fd80c4aba47b,
    'FF_54d8b54acb61': leaf_width_or_pair_description__ff_54d8b54acb61,
    'FF_834ec8fbd920': leaf_thickness_mm__ff_834ec8fbd920,
    'FF_8f74c6a9c5f2': leaf_quantity__ff_8f74c6a9c5f2,
    'FF_adf3afce97d5': uom__ff_adf3afce97d5,
    'FF_72f3a88de20b': finish_reference__ff_72f3a88de20b,
    'FF_e75f815a7f13': 计划系数__ff_e75f815a7f13,
    'FF_a43d769070cf': 计划量__ff_a43d769070cf,
    'FF_f4cfad53d5e1': 语义待核对_F__ff_f4cfad53d5e1,
    'FF_94068ddf9c8c': 订单交期__ff_94068ddf9c8c,
    'FF_036fc772ded4': 生产周期__ff_036fc772ded4,
    'FF_f87f9bee09a9': 语义待核对_F__ff_f87f9bee09a9,
    'FF_0fa5f36896a8': 油漆工艺_木皮_坯板__ff_0fa5f36896a8,
    'FF_4c2a5d2cdaa3': 客户等级__ff_4c2a5d2cdaa3,
    'FF_71c31112a64e': 白色_绿呈__ff_71c31112a64e,
    'FF_0a2947b61045': 白色_绿呈__ff_0a2947b61045,
    'FF_1e42da43e489': 语义待核对_M__ff_1e42da43e489,
    'FF_01ebedf7327c': 语义待核对_Q__ff_01ebedf7327c,
    'FF_ea40795bcbec': 语义待核对_R__ff_ea40795bcbec,
    'FF_3862905331ef': 语义待核对_S__ff_3862905331ef,
    'FF_2204175db59c': row_number__ff_2204175db59c,
    'FF_41e386154efe': material_code__ff_41e386154efe,
    'FF_10d885884644': process_code__ff_10d885884644,
    'FF_5f1b2a1dc7cf': 订单类型_必填__ff_5f1b2a1dc7cf,
    'FF_23ef55bd6d2e': paint_process__ff_23ef55bd6d2e,
    'FF_29b3f9b532a4': visible_area_m2__ff_29b3f9b532a4,
    'FF_100e47a2666a': edge_length_m__ff_100e47a2666a,
    'FF_e1734e5f3263': product_area_m2__ff_e1734e5f3263,
    'FF_fd290b0904b0': 特殊色版__ff_fd290b0904b0,
    'FF_7e8ba2374d7c': finish_reference__ff_7e8ba2374d7c,
    'FF_848428625aa3': 材料领用量__ff_848428625aa3,
    'FF_2bd1811c67f8': 语义待核对_AH__ff_2bd1811c67f8,
    'FF_bcd05cc6e880': 语义待核对_AI__ff_bcd05cc6e880,
    'FF_4043c1179fd9': 语义待核对_AJ__ff_4043c1179fd9,
    'FF_381619e849ca': 语义待核对_AK__ff_381619e849ca,
    'FF_78f188dacf66': 语义待核对_AL__ff_78f188dacf66,
    'FF_5c9579580a9f': field_2800_1220光板__ff_5c9579580a9f,
    'FF_2b7cdd184e7c': 语义待核对_AN__ff_2b7cdd184e7c,
    'FF_5540d6168ca2': 语义待核对_AO__ff_5540d6168ca2,
    'FF_5df1a11391ce': 语义待核对_AP__ff_5df1a11391ce,
    'FF_4c6c4a7b24cb': 语义待核对_AQ__ff_4c6c4a7b24cb,
    'FF_d5a8ff252745': 语义待核对_AR__ff_d5a8ff252745,
    'FF_9db72672de43': row_number__ff_9db72672de43,
    'FF_76ac97cac847': 物料名称_必填__ff_76ac97cac847,
    'FF_0e6b4cbb3da5': material_code__ff_0e6b4cbb3da5,
    'FF_3ecf442b0e55': material_code__ff_3ecf442b0e55,
}
