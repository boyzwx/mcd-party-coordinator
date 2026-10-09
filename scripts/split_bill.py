#!/usr/bin/env python3
"""
聚餐 AA 分摊计算器
输入总价、人数、每人额外消费，输出精确到分的分摊账单。

设计要点：
1. 尾差必须被完整分配，sum(每人实付) == 总价，不出现 0.01 元差额
2. 额外消费归属到具体成员，不做平均摊
3. 折扣按人均比例摊，不归于某个人
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple

CENT = Decimal("0.01")


def _to_cents(amount: Decimal) -> int:
    """金额转为整数分，避免浮点误差。"""
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cents_to_yuan(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)


def split_bill(
    total: Decimal,
    members: List[str],
    extras: Optional[Dict[str, Decimal]] = None,
    coupons: Optional[Dict[str, Decimal]] = None,
) -> Tuple[List[Dict], Decimal]:
    """
    拆分聚餐账单。

    金额语义（重要）：
        total 是「实付总价」，即已扣完全部优惠、已含配送费后的金额。
        因此个人优惠券不应再次从基数中扣除，否则会重复扣减导致总额校验失败。
        优惠券的真实作用是让整桌付得更少，其收益由全桌共享，
        所以它只作为展示信息出现在报告中，不参与分摊计算。

    Args:
        total: 整桌实付总价（已扣优惠、已含配送费）
        members: 成员名单，顺序即分摊顺序
        extras: 额外消费 {成员: 金额}，如某人多点了一份大份，已含在 total 中
        coupons: 成员优惠券抵扣 {成员: 金额}，仅用于报告展示，不参与分摊

    Returns:
        (分摊明细列表, 校验和)
    """
    if not members:
        raise ValueError("成员名单不能为空")
    if total < 0:
        raise ValueError("总价不能为负数")
    if len(set(members)) != len(members):
        raise ValueError("成员名单存在重名，无法区分")

    extras = extras or {}
    coupons = coupons or {}

    unknown = (set(extras) | set(coupons)) - set(members)
    if unknown:
        raise ValueError(f"存在不在名单中的成员: {sorted(unknown)}")

    n = len(members)
    total_cents = _to_cents(total)

    # 额外消费归属到具体成员，不参与均摊，需从均摊基数中扣除
    extra_cents = {m: _to_cents(extras.get(m, Decimal(0))) for m in members}
    coupon_cents = {m: _to_cents(coupons.get(m, Decimal(0))) for m in members}

    base_cents = total_cents - sum(extra_cents.values())
    if base_cents < 0:
        raise ValueError("额外消费之和已超过实付总价，请检查金额")

    per_head = base_cents // n
    remainder = base_cents - per_head * n

    rows: List[Dict] = []
    # 余数按成员顺序依次分配，每人最多多分 1 分
    for i, member in enumerate(members):
        share = per_head + (1 if i < remainder else 0)
        payable = share + extra_cents[member]
        rows.append(
            {
                "member": member,
                "base": _cents_to_yuan(share),
                "extra": _cents_to_yuan(extra_cents[member]),
                "coupon": _cents_to_yuan(coupon_cents[member]),
                "payable": _cents_to_yuan(payable),
            }
        )

    check = sum((r["payable"] for r in rows), Decimal(0))
    return rows, check


def verify_split(
    total: Decimal,
    members: List[str],
    extras: Optional[Dict[str, Decimal]] = None,
    coupons: Optional[Dict[str, Decimal]] = None,
) -> bool:
    """校验分摊总额是否与实付总价完全一致。"""
    _, check = split_bill(total, members, extras, coupons)
    return check == total.quantize(CENT)


def format_table(rows: List[Dict]) -> str:
    """渲染为 Markdown 表格。"""
    header = "| 成员 | 基本分摊 | 额外消费 | 贡献优惠券 | 实付 |\n"
    sep = "|---|---:|---:|---:|---:|\n"
    body = ""
    for r in rows:
        extra = f"{r['extra']}" if r["extra"] > 0 else "-"
        coupon = f"{r['coupon']}" if r["coupon"] > 0 else "-"
        body += (
            f"| {r['member']} | {r['base']} | {extra} | {coupon} "
            f"| **{r['payable']}** |\n"
        )
    return header + sep + body


if __name__ == "__main__":
    import sys

    cases = [
        ("6 人 / 总价 386.00 / 无人额外", Decimal("386.00"),
         ["A", "B", "C", "D", "E", "F"], {}, {}),
        ("6 人 / 总价 400.01 / C 多点大份 18 元", Decimal("400.01"),
         ["A", "B", "C", "D", "E", "F"], {"C": Decimal("18.00")}, {}),
        ("5 人 / 总价 238.00 / A 贡献 12 元券", Decimal("238.00"),
         ["A", "B", "C", "D", "E"], {}, {"A": Decimal("12.00")}),
        ("3 人 / 总价 100.00 / 0.01 尾差", Decimal("100.00"),
         ["甲", "乙", "丙"], {}, {}),
        ("7 人 / 总价 888.88 / 无额外", Decimal("888.88"),
         ["1", "2", "3", "4", "5", "6", "7"], {}, {}),
        ("4 人 / 总价 199.99 / 两人各有额外消费", Decimal("199.99"),
         ["W", "X", "Y", "Z"],
         {"X": Decimal("31.50"), "Z": Decimal("12.49")}, {}),
        ("20 人 / 大额团餐 2340.00", Decimal("2340.00"),
         [str(i) for i in range(1, 21)], {}, {}),
    ]

    ok = True
    for name, total, members, extras, discounts in cases:
        rows, check = split_bill(total, members, extras, discounts)
        passed = check == total.quantize(CENT)
        ok = ok and passed
        print(f"\n=== {name} ===")
        print(f"总价 {total} / 校验和 {check} / {'PASS' if passed else 'FAIL'}")
        print(format_table(rows))

    # 异常用例
    print("\n=== 异常处理 ===")
    for name, fn in [
        ("空名单", lambda: split_bill(Decimal("100"), [])),
        ("成员重名", lambda: split_bill(Decimal("100"), ["A", "A"])),
        ("总价负数", lambda: split_bill(Decimal("-1"), ["A"])),
        ("额外消费超总价", lambda: split_bill(
            Decimal("50"), ["A", "B"], {"A": Decimal("60")})),
        ("未知成员", lambda: split_bill(
            Decimal("100"), ["A", "B"], {"Z": Decimal("10")})),
    ]:
        try:
            fn()
            print(f"{name}:未拦截 FAIL")
            ok = False
        except ValueError as e:
            print(f"{name}: 已拦截 ({e})")

    print("\n" + ("全部用例通过" if ok else "存在失败用例"))
    sys.exit(0 if ok else 1)