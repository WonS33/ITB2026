// 월간 입력 [경영지원 관리에서 불러오기] 계산 (조원 저장소 entry/from-ledger.ts 를 옮김)
// - 경영지원 관리 총액 = 월간 입력과 같은 숫자: 외상매입금 = 당월 매입, 미지급비용-직원 = 당월 경비,
//   미지급비용-업체 = 당월 그 외 지출 (자동이체 포함 — 그 달에 실제로 나간 돈)
// - 경영지원 관리는 부가세 포함 금액 → 블록별 "÷1.1 공급가액으로 환산" 체크 (외상매입금·업체 기본 체크, 직원 기본 해제)
// - 결과는 입력란에만 채운다. 저장은 사람이 [임시저장]·[확정]으로

export const BLOCKS = [
  { kind: 'ap', label: '외상매입금', vat: true },
  { kind: 'accrued_staff', label: '미지급비용-직원', vat: false },
  { kind: 'accrued_vendor', label: '미지급비용-업체', vat: true },
]
export const VENDOR_KEYS = ['advertising', 'entertainment', 'other']
// 외상매입금 매입유형 → 월간 입력 칸
export const PURCHASE_FIELD = { goods: 'merchandise_purchase', raw_material: 'material_purchase' }

const zero = () => ({ amount: 0, count: 0 })
const add = (s, amount) => {
  s.amount += amount
  s.count += 1
}

export function sumLedgerRows(rows) {
  const s = {
    purchase: { goods: zero(), raw_material: zero() },
    unclassifiedPurchase: zero(), // 매입유형이 빈 외상매입금
    staff: zero(),
    vendor: { advertising: zero(), entertainment: zero(), other: zero() },
    vendorAuto: zero(), // 업체 중 자동이체 (vendor 합계에 이미 포함)
    blockTotal: { ap: zero(), accrued_staff: zero(), accrued_vendor: zero() },
    rowCount: rows.length,
  }
  for (const r of rows) {
    add(s.blockTotal[r.kind], r.amount)
    if (r.kind === 'ap') add(r.purchase_type ? s.purchase[r.purchase_type] : s.unclassifiedPurchase, r.amount)
    else if (r.kind === 'accrued_staff') add(s.staff, r.amount)
    else {
      add(s.vendor[r.expense_type ?? 'other'], r.amount) // 비용유형이 비어 있으면 "기타"
      if (r.auto_transfer) add(s.vendorAuto, r.amount)
    }
  }
  return s
}

// 부가세 포함 → 공급가액: ÷1.1, 원 단위 반올림
export function toSupplyAmount(amount) {
  const abs = Math.abs(amount)
  const result = Math.floor((abs * 10 + 5) / 11)
  return amount < 0 ? -result : result
}

// choice: { vat: {ap, accrued_staff, accrued_vendor}, unclassifiedPurchase: 칸 이름|null, vendorCategory: {advertising: 항목 id|null, ...} }
// → 칸마다 [{ target: {type:'field', field} | {type:'category', categoryId}, block, source, value, count }]
export function planFill(sums, choice) {
  const lines = new Map()
  const put = (target, block, s) => {
    if (s.count === 0) return
    const key = target.type === 'field' ? `f:${target.field}` : `c:${target.categoryId}`
    const line = lines.get(key) ?? { target, block, source: 0, value: 0, count: 0 }
    line.source += s.amount
    line.count += s.count
    lines.set(key, line)
  }
  put({ type: 'field', field: 'merchandise_purchase' }, 'ap', sums.purchase.goods)
  put({ type: 'field', field: 'material_purchase' }, 'ap', sums.purchase.raw_material)
  if (choice.unclassifiedPurchase) put({ type: 'field', field: choice.unclassifiedPurchase }, 'ap', sums.unclassifiedPurchase)
  put({ type: 'field', field: 'expense' }, 'accrued_staff', sums.staff)
  for (const key of VENDOR_KEYS) {
    const categoryId = choice.vendorCategory[key]
    if (categoryId) put({ type: 'category', categoryId }, 'accrued_vendor', sums.vendor[key])
  }
  // 칸 단위로 환산·반올림 (입력란 값과 같은 숫자)
  return [...lines.values()].map((l) => ({ ...l, value: choice.vat[l.block] ? toSupplyAmount(l.source) : l.source }))
}

// 업체 비용유형 이름 → 같은 이름의 그 외 지출 항목 ("기타"는 "기타…"로 시작하는 항목도)
export function defaultVendorCategory(categories, labels) {
  const active = categories.filter((c) => c.is_active)
  const find = (key) => {
    const exact = active.find((c) => c.name === labels[key])
    if (exact) return exact.category_id
    if (key === 'other') return active.find((c) => c.name.startsWith(labels[key]))?.category_id ?? null
    return null
  }
  return Object.fromEntries(VENDOR_KEYS.map((k) => [k, find(k)]))
}

// 채우지 않는 금액 안내 (원본 금액 기준)
export function skippedNotes(sums, choice, labels, won) {
  const notes = []
  if (sums.unclassifiedPurchase.count > 0 && !choice.unclassifiedPurchase) {
    notes.push(`매입유형이 빈 외상매입금 ${sums.unclassifiedPurchase.count}행(${won(sums.unclassifiedPurchase.amount)})은 채우지 않습니다. 넣을 칸을 고르세요.`)
  }
  for (const key of VENDOR_KEYS) {
    const s = sums.vendor[key]
    if (s.count > 0 && !choice.vendorCategory[key]) {
      notes.push(`미지급비용-업체 "${labels[key]}" ${s.count}행(${won(s.amount)})은 넣을 그 외 지출 항목을 고르지 않아 채우지 않습니다.`)
    }
  }
  return notes
}
