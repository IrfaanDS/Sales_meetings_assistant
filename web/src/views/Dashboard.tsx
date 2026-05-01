import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import {
  FileText, Clock, Upload, UserCircle, Trash2, Play,
  Database, Zap, Shield, ChevronDown, ChevronRight,
  Sparkles, Mic, BarChart3, ArrowRight
} from 'lucide-react'

interface DashboardProps {
  onNavigate: (view: 'dashboard' | 'summary' | 'transcript', sessionId?: string) => void
}

interface DocItem {
  name: string
  type: string
}

interface MeetingItem {
  id: string
  filename: string
  date: string
  hasSummary?: boolean
}

export default function Dashboard({ onNavigate }: DashboardProps) {
  const [documents, setDocuments] = useState<DocItem[]>([])
  const [meetings, setMeetings] = useState<MeetingItem[]>([])
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [docRes, meetRes] = await Promise.all([
        fetch('/api/documents'),
        fetch('/api/meetings')
      ])
      const docData = await docRes.json()
      const meetData = await meetRes.json()
      setDocuments(docData.documents || [])
      setMeetings(meetData.meetings || [])
    } catch {
      // Server booting up
    } finally {
      setLoading(false)
    }
  }

  const toggleDoc = (name: string) => {
    setSelectedDocs(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const dispatchAction = (action: any) => {
    (window as any).__qt_action = action
  }

  return (
    <div className="flex flex-col h-screen bg-[var(--surface-0)] text-white">
      {/* ─── Header ─── */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-white/[0.06] glass-strong shrink-0">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-[17px] font-bold tracking-tight text-white">
              AI Sales Meeting Assistant
            </h1>
            <p className="text-[11px] text-slate-500 font-medium tracking-wide">
              Real-time copilot for sales calls
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Status Badge */}
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/15 animate-glow-ring">
            <div className="w-[6px] h-[6px] rounded-full bg-emerald-400 animate-pulse-dot" />
            <span className="text-[10px] font-bold text-emerald-400 tracking-[0.12em] uppercase font-mono-data">
              System Ready
            </span>
          </div>
        </div>
      </header>

      {/* ─── 3-Column Main Content ─── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── LEFT: Knowledge Base ── */}
        <div className="w-[280px] min-w-[260px] flex flex-col panel-kb shrink-0">
          <div className="flex items-center justify-between px-5 py-3.5">
            <div className="flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-[10px] font-bold text-blue-400/80 tracking-[0.15em] uppercase">
                Knowledge Base
              </span>
            </div>
            <span className="text-[10px] text-slate-600 font-mono-data font-medium">
              {documents.length}
            </span>
          </div>

          <ScrollArea className="flex-1 px-3 pb-3">
            <div className="space-y-1.5">
              {documents.length === 0 && !loading && (
                <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                  <div className="w-12 h-12 rounded-2xl bg-blue-500/[0.06] border border-blue-500/10 flex items-center justify-center mb-4">
                    <Upload className="w-5 h-5 text-blue-500/40" />
                  </div>
                  <p className="text-[13px] text-slate-400 font-medium mb-1">No documents yet</p>
                  <p className="text-[11px] text-slate-600 leading-relaxed mb-4">
                    Upload product docs to enhance AI responses during calls
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-blue-500/20 text-blue-400 hover:bg-blue-500/10 text-xs"
                    onClick={() => dispatchAction({ type: 'upload_doc' })}
                  >
                    <Upload className="w-3 h-3 mr-1.5" />
                    Upload Document
                  </Button>
                </div>
              )}
              {documents.map((doc, i) => (
                <button
                  key={i}
                  onClick={() => toggleDoc(doc.name)}
                  className={`
                    w-full text-left px-3.5 py-2.5 rounded-lg border transition-all duration-200 group
                    ${selectedDocs.has(doc.name)
                      ? 'bg-blue-500/10 border-blue-500/25 shadow-md shadow-blue-500/5'
                      : 'bg-white/[0.01] border-transparent hover:bg-white/[0.03] hover:border-white/[0.06]'
                    }
                  `}
                >
                  <div className="flex items-center gap-2.5">
                    <div className={`
                      w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors
                      ${selectedDocs.has(doc.name) ? 'bg-blue-500/20' : 'bg-white/[0.04]'}
                    `}>
                      <FileText className={`w-3.5 h-3.5 ${selectedDocs.has(doc.name) ? 'text-blue-400' : 'text-slate-500'}`} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-slate-200 truncate">{doc.name}</p>
                      <p className="text-[10px] text-slate-600 font-mono-data">{doc.type || 'Knowledge Base'}</p>
                    </div>
                    {selectedDocs.has(doc.name) && (
                      <div className="shrink-0">
                        <div className="w-4.5 h-4.5 rounded-full bg-blue-500 flex items-center justify-center">
                          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </ScrollArea>

          {/* Doc Actions */}
          <div className="px-3 py-3 border-t border-white/[0.04] space-y-2">
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.05] hover:text-white text-[11px] h-8"
                onClick={() => dispatchAction({ type: 'upload_doc' })}
              >
                <Upload className="w-3 h-3 mr-1" />
                Product Doc
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1 border-white/[0.06] bg-white/[0.02] text-slate-400 hover:bg-white/[0.05] hover:text-white text-[11px] h-8"
                onClick={() => dispatchAction({ type: 'upload_bio' })}
              >
                <UserCircle className="w-3 h-3 mr-1" />
                Bio
              </Button>
            </div>
            {selectedDocs.size > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="w-full border-red-500/20 bg-red-500/5 text-red-400 hover:bg-red-500/10 text-[11px] h-8 animate-fade-in"
                onClick={() => dispatchAction({ type: 'delete', docs: Array.from(selectedDocs) })}
              >
                <Trash2 className="w-3 h-3 mr-1" />
                Delete Selected ({selectedDocs.size})
              </Button>
            )}
          </div>
        </div>

        {/* ── CENTER: Hero / Session Launch ── */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 flex flex-col items-center justify-center px-8">
            <div className="max-w-sm w-full text-center animate-fade-in-up">

              {/* Hero Icon */}
              <div className="relative mx-auto w-20 h-20 mb-6">
                <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-600/20 blur-xl" />
                <div className="relative w-full h-full rounded-2xl bg-gradient-to-br from-blue-500/10 to-indigo-600/10 border border-blue-500/15 flex items-center justify-center">
                  <Mic className="w-8 h-8 text-blue-400" />
                </div>
              </div>

              <h2 className="text-xl font-bold text-white mb-2 tracking-tight">
                Ready to Start a Session
              </h2>
              <p className="text-[13px] text-slate-500 leading-relaxed mb-8">
                {documents.length > 0
                  ? `${selectedDocs.size} of ${documents.length} docs selected. Your AI copilot will reference them during the call.`
                  : 'Upload product documents first, or start a session without context.'
                }
              </p>

              {/* Stealth Toggle */}
              <label className="inline-flex items-center gap-2.5 cursor-pointer mb-6 group">
                <div className="relative">
                  <input type="checkbox" id="stealth-checkbox" className="sr-only peer" />
                  <div className="w-9 h-5 rounded-full bg-white/[0.06] border border-white/[0.1] peer-checked:bg-blue-500/20 peer-checked:border-blue-500/30 transition-all" />
                  <div className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-slate-500 peer-checked:translate-x-4 peer-checked:bg-blue-400 transition-all shadow-sm" />
                </div>
                <div className="flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-slate-500 group-hover:text-slate-400 transition-colors" />
                  <span className="text-xs text-slate-500 group-hover:text-slate-400 transition-colors">Stealth Mode</span>
                </div>
              </label>

              {/* Primary CTA */}
              <div>
                <Button
                  id="start-session-btn"
                  className="w-full h-12 bg-gradient-to-r from-blue-600 via-blue-500 to-indigo-500 hover:from-blue-500 hover:via-blue-400 hover:to-indigo-400 text-white font-bold text-sm shadow-xl shadow-blue-500/25 animate-pulse-glow rounded-xl transition-all duration-300"
                  onClick={() => {
                    const stealth = (document.getElementById('stealth-checkbox') as HTMLInputElement)?.checked || false
                    dispatchAction({
                      type: 'start_session',
                      stealth,
                      docs: Array.from(selectedDocs)
                    })
                  }}
                >
                  <Play className="w-4 h-4 mr-2" />
                  Start Session
                </Button>
              </div>

              {/* Stats */}
              <div className="flex items-center justify-center gap-6 mt-8">
                <div className="text-center">
                  <p className="text-lg font-bold text-white font-mono-data">{documents.length}</p>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">Docs</p>
                </div>
                <div className="w-px h-8 bg-white/[0.06]" />
                <div className="text-center">
                  <p className="text-lg font-bold text-white font-mono-data">{meetings.length}</p>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">Sessions</p>
                </div>
                <div className="w-px h-8 bg-white/[0.06]" />
                <div className="text-center">
                  <p className="text-lg font-bold text-white font-mono-data">{selectedDocs.size}</p>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">Selected</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT: Meeting History ── */}
        <div className="w-[300px] min-w-[280px] flex flex-col panel-history shrink-0">
          <div className="flex items-center justify-between px-5 py-3.5">
            <div className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-[10px] font-bold text-amber-400/80 tracking-[0.15em] uppercase">
                Meeting History
              </span>
            </div>
            <span className="text-[10px] text-slate-600 font-mono-data font-medium">
              {meetings.length}
            </span>
          </div>

          <ScrollArea className="flex-1 px-3 pb-3">
            <div className="space-y-1.5 stagger-children">
              {meetings.length === 0 && !loading && (
                <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                  <div className="w-12 h-12 rounded-2xl bg-amber-500/[0.06] border border-amber-500/10 flex items-center justify-center mb-4">
                    <BarChart3 className="w-5 h-5 text-amber-500/40" />
                  </div>
                  <p className="text-[13px] text-slate-400 font-medium mb-1">No sessions yet</p>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Start a session to begin recording and analyzing your meetings
                  </p>
                </div>
              )}
              {meetings.map((m) => (
                <div key={m.id} className="rounded-lg overflow-hidden transition-all duration-200">
                  <button
                    className={`
                      w-full text-left px-3.5 py-3 flex items-center gap-3 group transition-all duration-200
                      ${expandedSessionId === m.id
                        ? 'bg-white/[0.04] border border-white/[0.08] rounded-t-lg'
                        : 'bg-white/[0.01] hover:bg-white/[0.03] border border-transparent rounded-lg'
                      }
                    `}
                    onClick={() => setExpandedSessionId(expandedSessionId === m.id ? null : m.id)}
                  >
                    <div className={`
                      w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors
                      ${m.hasSummary ? 'bg-emerald-500/10' : 'bg-amber-500/10'}
                    `}>
                      {m.hasSummary
                        ? <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
                        : <Clock className="w-3.5 h-3.5 text-amber-400" />
                      }
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-slate-200 truncate">{m.filename}</p>
                      <p className="text-[10px] text-slate-600 font-mono-data">{m.date}</p>
                    </div>
                    <div className="shrink-0 text-slate-600 group-hover:text-slate-400 transition-colors">
                      {expandedSessionId === m.id
                        ? <ChevronDown className="w-3.5 h-3.5" />
                        : <ChevronRight className="w-3.5 h-3.5" />
                      }
                    </div>
                  </button>

                  {/* Smooth grid-row expand */}
                  <div className={`grid-expand ${expandedSessionId === m.id ? 'open' : ''}`}>
                    <div className="grid-expand-inner">
                      <div className="px-3.5 py-3 bg-white/[0.02] border border-t-0 border-white/[0.08] rounded-b-lg space-y-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="w-full justify-start text-[12px] text-slate-300 hover:text-white hover:bg-white/[0.05] h-8 rounded-md"
                          onClick={() => onNavigate('transcript', m.id)}
                        >
                          <FileText className="w-3.5 h-3.5 mr-2 text-slate-500" />
                          View Transcript
                          <ArrowRight className="w-3 h-3 ml-auto text-slate-600" />
                        </Button>

                        {m.hasSummary ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="w-full justify-start text-[12px] text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 h-8 rounded-md"
                            onClick={() => onNavigate('summary', m.id)}
                          >
                            <Sparkles className="w-3.5 h-3.5 mr-2" />
                            View Summary
                            <ArrowRight className="w-3 h-3 ml-auto text-blue-500/50" />
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="w-full justify-start text-[12px] text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 h-8 rounded-md"
                            onClick={() => dispatchAction({ type: 'generate_summary', session_id: m.id })}
                          >
                            <Zap className="w-3.5 h-3.5 mr-2" />
                            Generate Summary
                            <ArrowRight className="w-3 h-3 ml-auto text-amber-500/50" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}
