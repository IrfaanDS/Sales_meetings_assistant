import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Button } from '@/components/ui/button.tsx'
import { ScrollArea } from '@/components/ui/scroll-area.tsx'
import {
  Brain, Download, Mail, CheckCircle2, AlertCircle,
  ArrowRightCircle, FileText, ArrowLeft, Sparkles
} from 'lucide-react'

interface SummaryProps {
  onNavigate: (view: 'dashboard' | 'summary' | 'transcript', sessionId?: string) => void
  sessionId: string
}

// Static lookup for sentiment — avoids Tailwind purge issues with dynamic class names
const SENTIMENT_STYLES = {
  emerald: { bar: 'sentiment-emerald', dot: 'sentiment-dot-emerald', text: 'text-emerald-400', label: 'Positive' },
  amber:   { bar: 'sentiment-amber',   dot: 'sentiment-dot-amber',   text: 'text-amber-400',   label: 'Neutral' },
  rose:    { bar: 'sentiment-rose',     dot: 'sentiment-dot-rose',    text: 'text-rose-400',    label: 'Negative' },
} as const

export default function Summary({ onNavigate, sessionId }: SummaryProps) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionId) return
    fetch(`/api/sessions/${sessionId}`)
      .then(res => res.json())
      .then(json => {
        setData(json.summary)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

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
          <p className="text-sm text-slate-400 font-medium">Analyzing meeting data...</p>
          <div className="mt-4 w-48 h-1 bg-white/[0.06] rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full animate-shimmer" style={{ width: '60%' }} />
          </div>
        </div>
      </div>
    )
  }

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[var(--surface-0)]">
        <div className="flex flex-col items-center animate-fade-in-up">
          <p className="text-slate-500">No summary data available</p>
          <Button variant="outline" className="mt-4 border-white/[0.1] text-slate-400" onClick={() => onNavigate('dashboard')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </div>
      </div>
    )
  }

  const sentimentText = data.sentiment_analysis || 'Neutral'
  let sentimentScore = 50
  const lower = sentimentText.toLowerCase()
  if (lower.includes('positive') || lower.includes('great') || lower.includes('optimistic')) sentimentScore = 80
  else if (lower.includes('negative') || lower.includes('skeptical') || lower.includes('challenging')) sentimentScore = 20

  const sentimentKey: keyof typeof SENTIMENT_STYLES =
    sentimentScore > 60 ? 'emerald' : sentimentScore < 40 ? 'rose' : 'amber'
  const sentiment = SENTIMENT_STYLES[sentimentKey]

  return (
    <div className="flex flex-col h-screen w-full bg-[var(--surface-0)] text-white overflow-hidden">
      {/* ─── Header ─── */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-white/[0.06] glass-strong shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => onNavigate('dashboard')}
            className="w-9 h-9 rounded-lg bg-white/[0.04] border border-white/[0.08] flex items-center justify-center hover:bg-white/[0.08] transition-colors"
          >
            <ArrowLeft className="w-4 h-4 text-slate-400" />
          </button>
          <div>
            <h1 className="text-[17px] font-bold tracking-tight text-gradient-blue">
              Post-Meeting Summary
            </h1>
            <p className="text-[11px] text-slate-500 font-mono-data">
              {sessionId.replace('Session_', '').replace(/_/g, ' · ')}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-white/[0.08] text-slate-400 hover:bg-white/[0.06] text-[11px] h-8"
          >
            <Download className="w-3 h-3 mr-1.5" />
            Export PDF
          </Button>
          <Button
            size="sm"
            className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-[11px] h-8 shadow-lg shadow-emerald-500/15"
          >
            <Mail className="w-3 h-3 mr-1.5" />
            Email
          </Button>
        </div>
      </header>

      {/* ─── Content ─── */}
      <ScrollArea className="flex-1">
        <div className="max-w-3xl mx-auto px-8 py-8 space-y-5 stagger-children">

          {/* Executive Summary */}
          <Card className="bg-white/[0.02] border-white/[0.06] shadow-2xl shadow-black/20 overflow-hidden rounded-xl">
            <CardHeader className="bg-white/[0.01] border-b border-white/[0.04] pb-3 pt-4 px-5">
              <CardTitle className="flex items-center text-blue-400 text-[11px] font-bold tracking-[0.12em] uppercase">
                <FileText className="w-3.5 h-3.5 mr-2" />
                Executive Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 pb-5 px-5">
              <p className="text-[14px] text-slate-300 leading-[1.7]">
                {data.executive_summary || 'N/A'}
              </p>
            </CardContent>
          </Card>

          {/* Sentiment */}
          <Card className="bg-white/[0.02] border-white/[0.06] shadow-2xl shadow-black/20 overflow-hidden rounded-xl">
            <CardHeader className="bg-white/[0.01] border-b border-white/[0.04] pb-3 pt-4 px-5">
              <CardTitle className="flex items-center text-amber-400 text-[11px] font-bold tracking-[0.12em] uppercase">
                <Brain className="w-3.5 h-3.5 mr-2" />
                Sentiment Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-5 pb-5 px-5">
              <div className="mb-5">
                <div className="flex justify-between text-[9px] font-mono-data text-slate-500 mb-3 tracking-[0.15em]">
                  <span>SKEPTICAL</span>
                  <span>NEUTRAL</span>
                  <span>OPTIMISTIC</span>
                </div>
                <div className="relative h-2 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className={`absolute left-0 top-0 h-full rounded-full transition-all duration-1000 ease-out ${sentiment.bar}`}
                    style={{ width: `${sentimentScore}%` }}
                  />
                </div>
                {/* Indicator dot */}
                <div className="relative h-0">
                  <div
                    className={`absolute -top-[13px] w-4 h-4 rounded-full border-2 border-[var(--surface-0)] ${sentiment.dot} transition-all duration-1000 shadow-lg`}
                    style={{ left: `calc(${sentimentScore}% - 8px)` }}
                  />
                </div>
              </div>
              <p className={`text-sm mt-6 ${sentiment.text}`}>{sentimentText}</p>
            </CardContent>
          </Card>

          {/* Action Items */}
          <Card className="bg-white/[0.02] border-white/[0.06] shadow-2xl shadow-black/20 overflow-hidden rounded-xl">
            <CardHeader className="bg-emerald-500/[0.03] border-b border-emerald-500/10 pb-3 pt-4 px-5">
              <CardTitle className="flex items-center text-emerald-400 text-[11px] font-bold tracking-[0.12em] uppercase">
                <CheckCircle2 className="w-3.5 h-3.5 mr-2" />
                Action Items
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 pb-5 px-5">
              {data.action_items?.length > 0 ? (
                <ul className="space-y-3">
                  {data.action_items.map((item: string, i: number) => (
                    <li key={i} className="flex items-start group">
                      <div className="min-w-5 mt-0.5 mr-3 w-5 h-5 rounded-md border border-emerald-500/25 flex items-center justify-center bg-emerald-500/5 group-hover:bg-emerald-500/15 transition-colors cursor-pointer">
                        <CheckCircle2 className="w-3 h-3 text-emerald-500/40" />
                      </div>
                      <span className="text-[13px] text-slate-300 leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] text-slate-600 italic">No specific action items identified.</p>
              )}
            </CardContent>
          </Card>

          {/* Objections + Next Steps */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <Card className="bg-white/[0.02] border-white/[0.06] shadow-2xl shadow-black/20 overflow-hidden rounded-xl">
              <CardHeader className="bg-rose-500/[0.03] border-b border-rose-500/10 pb-3 pt-4 px-5">
                <CardTitle className="flex items-center text-rose-400 text-[11px] font-bold tracking-[0.12em] uppercase">
                  <AlertCircle className="w-3.5 h-3.5 mr-2" />
                  Objections
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 pb-5 px-5">
                {data.client_objections?.length > 0 ? (
                  <ul className="space-y-2.5">
                    {data.client_objections.map((item: string, i: number) => (
                      <li key={i} className="flex items-start">
                        <span className="text-rose-400/50 mr-2.5 mt-0.5 text-[8px]">●</span>
                        <span className="text-[13px] text-slate-300 leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[13px] text-slate-600 italic">No objections raised.</p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-white/[0.02] border-white/[0.06] shadow-2xl shadow-black/20 overflow-hidden rounded-xl">
              <CardHeader className="bg-blue-500/[0.03] border-b border-blue-500/10 pb-3 pt-4 px-5">
                <CardTitle className="flex items-center text-blue-400 text-[11px] font-bold tracking-[0.12em] uppercase">
                  <ArrowRightCircle className="w-3.5 h-3.5 mr-2" />
                  Next Steps
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 pb-5 px-5">
                {data.next_steps?.length > 0 ? (
                  <ul className="space-y-2.5">
                    {data.next_steps.map((item: string, i: number) => (
                      <li key={i} className="flex items-start">
                        <span className="text-blue-400/50 mr-2.5 mt-0.5 text-[8px]">●</span>
                        <span className="text-[13px] text-slate-300 leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[13px] text-slate-600 italic">No next steps defined.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="h-6" />
        </div>
      </ScrollArea>
    </div>
  )
}
