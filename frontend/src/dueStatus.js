// 납기 처리 상태 표시 (백엔드 production/due_calendar.py 기준: 출고일로 판단)
// 색만으로 구분하지 않도록 기호와 글자를 함께 붙인다
import '@/assets/due-status.css'

export const DUE_STATUS = {
  overdue: { label: '납기 지남', icon: '!', cls: 'due-overdue' },
  pending: { label: '출고 전', icon: '○', cls: 'due-pending' },
  partial: { label: '일부 출고', icon: '◐', cls: 'due-partial' },
  done: { label: '출고 완료', icon: '✓', cls: 'due-done' },
}
export const DUE_STATUS_ORDER = ['overdue', 'pending', 'partial', 'done']

// 수주 묶음 → 표시할 상태 키 (납기 지남이 가장 먼저)
export const statusKey = (order) => (order.overdue ? 'overdue' : order.status)

// D-day 글자: 0 → D-day, 앞으로 3일 → D-3, 지남 2일 → D+2
export const dDayText = (d) => (d === 0 ? 'D-day' : d > 0 ? `D-${d}` : `D+${-d}`)
