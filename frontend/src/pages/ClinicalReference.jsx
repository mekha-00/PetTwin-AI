/**
 * Clinical Reference — ask a question against the indexed veterinary documents.
 *
 * This page never shows or sends a pet's records. It answers from a fixed corpus
 * of published veterinary literature and lists the passages the answer was
 * allowed to use, so the reader can check it rather than trust it. The answer is
 * a literature summary, not a diagnosis, and the disclaimer says so on every
 * result.
 *
 * The request is fired on submit rather than on mount: it costs an LLM call, and
 * a page that spends one every time it opens would be both slow and wasteful.
 */
import { useState } from 'react'
import { BookOpenText, Search, Sparkles, TriangleAlert } from 'lucide-react'

import { askRag, fetchRagStatus } from '../lib/endpoints'
import { describeError } from '../lib/api'
import { useAsyncData } from '../hooks/useAsyncData'
import { Badge, ErrorMessage, SectionCard, Spinner } from '../components/ui'

const EXAMPLE_QUESTIONS = [
  'How often should puppies be vaccinated?',
  'What are the symptoms of canine parvovirus?',
  'How is feline leukemia virus transmitted?',
  'What is the core vaccination schedule for adult dogs?',
]

function SourceList({ sources }) {
  if (!sources || sources.length === 0) return null
  return (
    <div>
      <h3 className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
        Passages used
      </h3>
      <ol className="mt-2 flex flex-col gap-2">
        {sources.map((source) => (
          <li
            key={`${source.index}-${source.source}-${source.page}`}
            className="rounded-lg border border-line px-3 py-2"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">[{source.index}]</Badge>
              <span className="text-sm font-medium">{source.source}</span>
              <span className="text-xs text-ink-soft">page {source.page}</span>
              <span className="ml-auto text-xs text-ink-soft">
                similarity {source.score.toFixed(2)}
              </span>
            </div>
            <p className="mt-1 text-sm text-ink-soft">{source.excerpt}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function ClinicalReference() {
  const { data: status } = useAsyncData(() => fetchRagStatus(), [])

  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isAsking, setIsAsking] = useState(false)

  const trimmed = question.trim()
  const canAsk = trimmed.length >= 3 && !isAsking

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canAsk) return
    setIsAsking(true)
    setError(null)
    setResult(null)
    try {
      const answer = await askRag({ question: trimmed })
      setResult(answer)
    } catch (err) {
      setError(describeError(err))
    } finally {
      setIsAsking(false)
    }
  }

  function applyExample(text) {
    setQuestion(text)
    setResult(null)
    setError(null)
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <BookOpenText className="h-6 w-6 text-brand" aria-hidden="true" />
          Clinical Reference
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Ask a question and get an answer drawn only from the indexed veterinary
          documents, with the passages it used listed below it.
        </p>
      </header>

      <SectionCard
        title="Ask a question"
        description={
          status?.ready
            ? `${status.documents_indexed} passages indexed from the veterinary corpus.`
            : 'The document index is not ready yet.'
        }
      >
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="field-label" htmlFor="rag-question">
              Your question
            </label>
            <textarea
              id="rag-question"
              className="field-input min-h-24 resize-y"
              placeholder="e.g. How often should puppies be vaccinated?"
              value={question}
              maxLength={500}
              onChange={(event) => setQuestion(event.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" className="btn btn-primary" disabled={!canAsk}>
              <Search className="h-4 w-4" aria-hidden="true" />
              {isAsking ? 'Searching the corpus…' : 'Search documents'}
            </button>
            <span className="text-xs text-ink-soft">{trimmed.length}/500</span>
          </div>
        </form>

        <div className="mt-4">
          <p className="text-xs font-semibold tracking-wide text-ink-soft uppercase">
            Try one of these
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.map((text) => (
              <button
                key={text}
                type="button"
                className="btn btn-secondary text-xs"
                onClick={() => applyExample(text)}
              >
                {text}
              </button>
            ))}
          </div>
        </div>
      </SectionCard>

      <ErrorMessage>{error}</ErrorMessage>

      {isAsking ? (
        <SectionCard title="Answer">
          <Spinner label="Reading the corpus and drafting an answer" />
        </SectionCard>
      ) : null}

      {result ? (
        <SectionCard
          title="Answer"
          description={
            result.grounded
              ? 'Generated from the passages below.'
              : 'The indexed documents do not appear to cover this question.'
          }
        >
          <div className="flex items-start gap-2">
            {result.grounded ? (
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            ) : (
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden="true" />
            )}
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.answer}</p>
          </div>

          {result.model ? (
            <p className="mt-3 text-xs text-ink-soft">
              Answered by <span className="font-medium">{result.model}</span>.
            </p>
          ) : null}

          <div className="mt-4">
            <SourceList sources={result.sources} />
          </div>
        </SectionCard>
      ) : null}
    </div>
  )
}
