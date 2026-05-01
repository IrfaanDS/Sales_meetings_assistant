import { useEffect, useState } from 'react'
import './index.css'
import Dashboard from './views/Dashboard'
import Summary from './views/Summary'
import Transcript from './views/Transcript'

type View = 'dashboard' | 'summary' | 'transcript'

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const [sessionId, setSessionId] = useState<string>('')

  const handleNavigate = (newView: View, sid?: string) => {
    setView(newView)
    if (sid) setSessionId(sid)
    
    // Tell the backend so polling doesn't override our local navigation
    fetch('/api/navigate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ view: newView })
    }).catch(console.error)
  }

  // Poll the backend for the current view state
  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const res = await fetch('/api/state')
        const data = await res.json()
        if (data.current_view && data.current_view !== view) {
          setView(data.current_view as View)
        }
      } catch {
        // Server not ready yet
      }
    }, 500)
    return () => clearInterval(poll)
  }, [view])

  return (
    <div className="h-screen w-full overflow-hidden bg-[#08090c]">
      {view === 'dashboard' && <Dashboard onNavigate={handleNavigate} />}
      {view === 'summary' && <Summary onNavigate={handleNavigate} sessionId={sessionId} />}
      {view === 'transcript' && <Transcript onNavigate={handleNavigate} sessionId={sessionId} />}
    </div>
  )
}
