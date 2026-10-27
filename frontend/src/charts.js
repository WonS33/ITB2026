// Chart.js 설정: 쓰는 부품만 등록하고, 그래프 색은 여기 한곳에서 정한다
import { ArcElement, BarElement, CategoryScale, Chart, LinearScale, LineElement, PointElement, Tooltip } from 'chart.js'

Chart.register(ArcElement, BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip)
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily
Chart.defaults.color = '#52514e' // 축 글자: 보조 글자색

// 색약 사용자도 구분되는지 검증한 순서 (dataviz 기본 팔레트, 순서를 바꾸지 말 것)
export const SERIES_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
export const OTHER_COLOR = '#a3a29c' // "기타"는 회색
export const GRID_COLOR = '#ecebe8' // 눈금선은 흐리게

// 산업 분야별 고정 색: 기간이 바뀌어 순위가 달라져도 같은 분야는 같은 색
// (분야 목록은 backend/production/industry_map.py 의 INDUSTRIES 와 같아야 함)
export const INDUSTRIES = ['상하수도', '발전소', '가스', '오일', '석유', '민간 플랜트', '기타']
export function industryColor(name) {
  const i = INDUSTRIES.indexOf(name)
  return i === -1 || name === '기타' ? OTHER_COLOR : SERIES_COLORS[i]
}

export const percent = (part, total) => (total ? Math.round((part / total) * 1000) / 10 : 0)

// 유상·무상 고정 색: 눈에 덜 띄는 차분한 파랑·모래색 (2026-10-27, 검증 도구로 두 색 구분 확인 — 색약 포함)
// 모래색은 흰 바탕 대비가 낮아 항상 숫자·표를 함께 보여준다
export const PAID_COLORS = { 유상: '#4a7fc1', 무상: '#d9a066' }
export const paidColor = (name) => PAID_COLORS[name] ?? OTHER_COLOR
