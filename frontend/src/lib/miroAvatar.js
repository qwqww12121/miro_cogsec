export const AVATAR_KEYS = ['female', 'male']

export const AVATAR_SRC = {
  female: '/avatars/mirofish-female.png',
  male: '/avatars/mirofish-male.png',
}

/** 新对话时抽一次：0 女，1 男。 */
export function pickAvatarKey() {
  return Math.random() < 0.5 ? 'female' : 'male'
}

export function avatarSrc(key) {
  return AVATAR_SRC[key] || AVATAR_SRC.female
}

export function avatarKeyForSession(session) {
  if (session?.avatarKey === 'male' || session?.avatarKey === 'female') return session.avatarKey
  const id = String(session?.id || '')
  if (!id) return 'female'
  let hash = 0
  for (let i = 0; i < id.length; i += 1) hash = (hash * 31 + id.charCodeAt(i)) >>> 0
  return hash % 2 === 0 ? 'female' : 'male'
}
