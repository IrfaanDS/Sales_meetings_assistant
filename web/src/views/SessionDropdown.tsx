import { useEffect, useState } from 'react'

interface Session {
  id: string;
  label: string;
  transcript?: any;
  summary?: any;
}

interface SessionDropdownProps {
  onSelect?: (id: string) => void;
}

export default function SessionDropdown({ onSelect }: SessionDropdownProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selected, setSelected] = useState<string>('')

  useEffect(() => {
    fetch('/api/sessions')
      .then(res => res.json())
      .then(data => setSessions(data.sessions || []))
      .catch(console.error)
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    setSelected(id)
    if (onSelect) onSelect(id)
    if (!id) return
    fetch(`/api/session/${id}`)
      .then(res => res.json())
      .then(data => {
        const socket = new WebSocket(`ws://${window.location.host}/ws/live`)
        socket.onopen = () => {
          socket.send(JSON.stringify({ type: 'session_load', transcript: data.transcript, summary: data.summary }))
          socket.close()
        }
      })
      .catch(console.error)
  }

  return (
    <div className="glass-strong rounded-xl p-3 mb-4">
      <label className="block text-sm font-medium text-slate-300 mb-1">Session History</label>
      <select
        value={selected}
        onChange={handleChange}
        className="w-full bg-white/5 text-slate-200 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Select a session…</option>
        {sessions.map(s => (
          <option key={s.id} value={s.id}>{s.label}</option>
        ))}
      </select>
    </div>
  )
}
