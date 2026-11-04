// 금액 표시 (경영지원 화면 공용)
// won: 1,234,567원 / wonShort: 큰 금액을 억·만 원으로 줄여 카드에 (정확한 값은 툴팁·표에서)
export const won = (v) => (v === null || v === undefined ? '-' : `${v.toLocaleString('ko-KR')}원`)

export function wonShort(v) {
  if (v === null || v === undefined) return '-'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(abs >= 1e10 ? 0 : 1)}억 원`
  if (abs >= 1e4) return `${sign}${Math.round(abs / 1e4).toLocaleString('ko-KR')}만 원`
  return `${sign}${abs.toLocaleString('ko-KR')}원`
}

// 퍼센트 (서버가 소수 첫째 자리까지 계산해 보냄)
export const pctText = (v) => (v === null || v === undefined ? '-' : `${v.toFixed(1)}%`)
