// 비밀번호 규칙 안내 (실제 검사는 백엔드 accounts/validators.py + settings.AUTH_PASSWORD_VALIDATORS)
// 화면에서는 입력하는 동안 어떤 규칙을 지켰는지 미리 보여주기만 한다.
export const MIN_LENGTH = 8
export const SPECIAL_CHARS = '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~' // 백엔드 SPECIAL_CHARS와 같아야 함

const isLetter = (c) => /[A-Za-z]/.test(c)
const isDigit = (c) => /[0-9]/.test(c)
const isSpecial = (c) => SPECIAL_CHARS.includes(c)

export function checkPassword(pw) {
  const chars = [...pw]
  return [
    { label: `${MIN_LENGTH}자 이상`, ok: chars.length >= MIN_LENGTH },
    { label: '영문자 1개 이상', ok: chars.some(isLetter) },
    { label: '숫자 1개 이상', ok: chars.some(isDigit) },
    { label: '특수기호 1개 이상', ok: chars.some(isSpecial) },
    {
      label: '공백·한글 등 다른 글자 없음',
      ok: pw.length > 0 && chars.every((c) => isLetter(c) || isDigit(c) || isSpecial(c)),
    },
  ]
}
