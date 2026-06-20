import { useState } from 'react'
import { clearProfile, isValidChinaPhone, loadProfile, saveProfile, type UserProfile } from '../lib/profile'

function formatDateTime(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const GRADE_OPTIONS = ['IGCSE', 'AS (Year 12)', 'A2 (Year 13)', '其他']

export function ProfileTab() {
  const [profile, setProfile] = useState<UserProfile | null>(() => loadProfile())
  const [phone, setPhone] = useState(profile?.phone ?? '')
  const [name, setName] = useState(profile?.name ?? '')
  const [grade, setGrade] = useState(profile?.grade ?? GRADE_OPTIONS[1])
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(profile === null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmedPhone = phone.trim()
    const trimmedName = name.trim()
    if (!isValidChinaPhone(trimmedPhone)) {
      setError('请输入有效的 11 位手机号')
      return
    }
    if (!trimmedName) {
      setError('请填写姓名')
      return
    }
    setError(null)
    const saved = saveProfile({ phone: trimmedPhone, name: trimmedName, grade })
    setProfile(saved)
    setEditing(false)
  }

  const handleLogout = () => {
    if (!confirm('确定要退出并清除本地个人信息吗？历史记录不会被删除。')) return
    clearProfile()
    setProfile(null)
    setPhone('')
    setName('')
    setGrade(GRADE_OPTIONS[1])
    setEditing(true)
  }

  if (profile && !editing) {
    return (
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900">我的</h2>

        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xl font-semibold text-gray-900">{profile.name}</p>
              <p className="mt-1 text-sm text-gray-500">{profile.grade}</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="rounded border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"
              >
                编辑
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded border border-red-200 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
              >
                退出
              </button>
            </div>
          </div>

          <dl className="mt-4 space-y-2 border-t border-gray-100 pt-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">手机号</dt>
              <dd className="text-gray-900">{profile.phone}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">注册时间</dt>
              <dd className="text-gray-900">{formatDateTime(profile.registeredAt)}</dd>
            </div>
          </dl>
        </div>

        <p className="text-xs text-gray-400">
          账号信息保存在本浏览器本地；当你提交反馈时，会随反馈一起上传，便于我们回复你。
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-900">{profile ? '编辑资料' : '注册'}</h2>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-lg border border-gray-200 bg-white p-6"
      >
        <div>
          <label className="block text-sm font-medium text-gray-700">手机号</label>
          <input
            type="tel"
            inputMode="numeric"
            maxLength={11}
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
            placeholder="请输入 11 位手机号"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">姓名</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="如：张三"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">年级</label>
          <select
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {GRADE_OPTIONS.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </div>

        {error ? <p className="text-xs text-red-600">{error}</p> : null}

        <div className="flex gap-2">
          <button
            type="submit"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {profile ? '保存修改' : '完成注册'}
          </button>
          {profile ? (
            <button
              type="button"
              onClick={() => {
                setPhone(profile.phone)
                setName(profile.name)
                setGrade(profile.grade)
                setError(null)
                setEditing(false)
              }}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              取消
            </button>
          ) : null}
        </div>

        <p className="text-xs text-gray-400">
          信息保存在本浏览器本地；当你提交反馈时，会随反馈一起上传，便于我们回复你。
        </p>
      </form>
    </div>
  )
}
