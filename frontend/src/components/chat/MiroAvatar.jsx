import { avatarSrc } from '../../lib/miroAvatar'

export default function MiroAvatar({ avatarKey, size = 'sm', className = '' }) {
  const box = size === 'lg' ? 'w-12 h-12 rounded-2xl' : 'w-8 h-8 rounded-xl'
  return (
    <img
      src={avatarSrc(avatarKey)}
      alt="MiroCogSec"
      className={`${box} object-cover object-top shrink-0 bg-[#07111f] ring-1 ring-brand-100 ${className}`}
    />
  )
}
