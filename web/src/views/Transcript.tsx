import { useEffect, useState, useMemo } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { FileText, ArrowLeft, Sparkles, Search, Mic, User } from 'lucide-react'

interface TranscriptProps {
  onNavigate: (view: 'dashboard' | 'summary' | 'transcript', sessionId?: string) => void
  sessionId: string
}

interface TranscriptBlock {
  speaker: string
  text: string
}

function parseTranscript(raw: string): TranscriptBlock[] {
  if (!raw || raw === 'No transcript found.') return []

  const blocks: TranscriptBlock[] = []
  const lines = raw.split('\n')
  let currentSpeaker = ''
  let currentText: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    // Match "Speaker:" lines
    const speakerMatch = trimmed.match(/^(Sales Rep|Client|You|AI Assistant):$/i)
    if (speakerMatch) {
      // Flush previous
      if (currentSpeaker && currentText.length > 0) {
        blocks.push({ speaker: currentSpeaker, text: currentText.join(' ') })
      }
      currentSpeaker = speakerMatch[1]
      currentText = []
    } else {
      currentText.push(trimmed)
    }
  }
  // Flush final block
  if (currentSpeaker && currentText.length > 0) {
    blocks.push({ speaker: currentSpeaker, text: currentText.join(' ') })
  }

  // If parsing yielded nothing, treat the whole thing as one block
  if (blocks.length === 0 && raw.trim()) {
    blocks.push({ speaker: 'Transcript', text: raw.trim() })
  }

  return blocks
}

export default function Transcript({ onNavigate, sessionId }: TranscriptProps) {
  const [rawData, setRawData] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetch(`/api/sessions/${sessionId}`)
      .then(res => res.json())
      .then(json => {
        setRawData(json.transcript || 'No transcript found.')
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

  const blocks = useMemo(() => parseTranscript(rawData), [rawData])

  const filteredBlocks = useMemo(() => {
    if (!searchQuery.trim()) return blocks
    const q = searchQuery.toLowerCase()
    return blocks.filter(b => b.text.toLowerCase().includes(q) || b.speaker.toLowerCase().includes(q))
  }, [blocks, searchQuery])

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[var(--surface-0)]">
        <div className="flex flex-col items-center animate-fade-in-up">
          <div className="relative w-16 h-16 mb-5">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 blur-xl" />
            <div className="relative w-full h-full rounded-2xl bg-gradient-to-br from-blue-500/10 to-indigo-500/10 border border-blue-500/15 flex items-center justify-center">
              <Sparkles className="w-7 h-7 text-blue-400 animate-pulse" />
            </div>
          </div>
          <p className="text-sm text-slate-400 font-medium">Loading transcript...</p>
        </div>
      </div>
    )
  }

  const getSpeakerConfig = (speaker: string) => {
    const s = speaker.toLowerCase()
    if (s.includes('sales') || s === 'you') {
      return {
        label: 'YOU',
        icon: <Mic className="w-3 h-3" />,
        colors: 'text-blue-400 bg-blue-500/10 border-blue-500/15',
        tag: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        accent: 'border-l-blue-500/40',
      }
    }
    if (s.includes('client')) {
      return {
        label: 'CLIENT',
        icon: <User className="w-3 h-3" />,
        colors: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/15',
        tag: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        accent: 'border-l-emerald-500/40',
      }
    }
    return {
      label: speaker.toUpperCase(),
      icon: <FileText className="w-3 h-3" />,
      colors: 'text-slate-400 bg-white/[0.04] border-white/[0.08]',
      tag: 'bg-white/[0.04] text-slate-400 border-white/[0.08]',
      accent: 'border-l-slate-500/30',
    }
  }

  const highlightMatch = (text: string) => {
    if (!searchQuery.trim()) return text
    const parts = text.split(new RegExp(`(${searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))
    return parts.map((part, i) =>
      part.toLowerCase() === searchQuery.toLowerCase()
        ? <mark key={i} className="bg-amber-400/25 text-amber-200 rounded px-0.5">{part}</mark>
        : part
    )
  }

  return (
    <div className="flex flex-col h-screen bg-[var(--surface-0)] text-white overflow-hidden">
      <header className="flex items-center justify-between px-8 py-4 border-b border-white/[0.06] glass-strong shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => onNavigate('dashboard')}
            className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center hover:bg-white/[0.08] transition-colors"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400" />
          </button>
          <div>
            <h1 className="text-[17px] font-bold tracking-tight text-gradient-blue flex items-center gap-2">
              Session Transcript
            </h1>
            <p className="text-[11px] text-slate-500 font-mono-data">
              {sessionId.replace('Session_', '').replace(/_/g, ' · ')} · {filteredBlocks.length} blocks
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search transcript..."
            className="h-8 pl-9 pr-4 rounded-lg bg-white/[0.03] border border-white/[0.08] text-[12px] text-slate-300 placeholder:text-slate-600 focus:outline-none focus:border-blue-500/30 focus:bg-white/[0.05] w-56 transition-all"
          />
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="max-w-3xl mx-auto px-8 py-6 space-y-3 stagger-children">
          {filteredBlocks.length === 0 && (
            <div className="text-center py-16">
              <p className="text-[13px] text-slate-500">
                {searchQuery ? 'No matches found' : 'No transcript data available'}
              </p>
            </div>
          )}
          {filteredBlocks.map((block, i) => {
            const config = getSpeakerConfig(block.speaker)
            return (
              <div key={i} className={`flex gap-3 px-4 py-3.5 rounded-xl bg-white/[0.015] border border-white/[0.04] hover:bg-white/[0.03] transition-colors border-l-2 ${config.accent}`}>
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${config.colors}`}>
                  {config.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[9px] font-bold tracking-[0.15em] uppercase px-2 py-0.5 rounded border font-mono-data ${config.tag}`}>
                      {config.label}
                    </span>
                  </div>
                  <p className="text-[13px] text-slate-300 leading-[1.7]">
                    {highlightMatch(block.text)}
                  </p>
                </div>
              </div>
            )
          })}
          <div className="h-6" />
        </div>
      </ScrollArea>
    </div>
  )
}
