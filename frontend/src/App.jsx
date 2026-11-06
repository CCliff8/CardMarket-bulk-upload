import { useEffect, useId, useRef, useState } from 'react'

const API = 'http://127.0.0.1:5001/api'
const MAX_ENTRIES = 150
const MAX_QTY = 999
const LIST_NAME_RE = /^[A-Za-z0-9 -]{1,30}$/

const post = (path, body) =>
  fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }).then(r => r.json())

const qtyOf = i => Math.min(MAX_QTY, Math.max(1, parseInt(i.qty, 10) || 1))

function Spinner() {
  return <span className="spinner" role="status" aria-label="Loading" />
}

function QtyStepper({ value, onChange }) {
  const n = parseInt(value, 10) || 1
  return (
    <div className="stepper">
      <button type="button" aria-label="Decrease amount" onClick={() => onChange(Math.max(1, n - 1))} disabled={n <= 1}>−</button>
      <input
        type="text"
        inputMode="numeric"
        aria-label="Amount"
        value={value}
        onChange={e => {
          const digits = e.target.value.replace(/\D/g, '').slice(0, 3)
          onChange(digits === '' ? '' : Math.min(MAX_QTY, parseInt(digits, 10)))
        }}
        onBlur={() => { if (!parseInt(value, 10)) onChange(1) }}
        onFocus={e => e.target.select()}
      />
      <button type="button" aria-label="Increase amount" onClick={() => onChange(Math.min(MAX_QTY, n + 1))}>+</button>
    </div>
  )
}

function CardSearch({ onPick, error }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const boxRef = useRef(null)
  const listId = useId()
  const q = query.trim()

  useEffect(() => {
    if (q.length < 2) return
    const ctrl = new AbortController()
    const t = setTimeout(() => {
      setLoading(true)
      fetch(`${API}/search?q=${encodeURIComponent(q)}`, { signal: ctrl.signal })
        .then(r => r.json())
        .then(r => { setResults(r); setActive(-1); setOpen(true); setLoading(false) })
        .catch(e => { if (e.name !== 'AbortError') setLoading(false) })
    }, 250)
    return () => { clearTimeout(t); ctrl.abort() }
  }, [q])

  useEffect(() => {
    const close = e => { if (!boxRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const shown = q.length >= 2 ? results : []

  const choose = c => {
    onPick(c)
    setQuery('')
    setResults([])
    setOpen(false)
  }

  const onKeyDown = e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive(a => Math.min(shown.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(0, a - 1)) }
    else if (e.key === 'Enter' && open && active >= 0) { e.preventDefault(); choose(shown[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div className="combo" ref={boxRef}>
      <div className="search-field">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <input
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          placeholder="Search a card, e.g. “charizard 151” or “gengar fossil”"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => shown.length && setOpen(true)}
        />
        {loading && <Spinner />}
      </div>
      {open && q.length >= 2 && (
        <ul className="dropdown" role="listbox" id={listId}>
          {shown.length === 0 && !loading && <li className="dropdown-empty">No cards found. Try adding a set name.</li>}
          {shown.map((c, idx) => (
            <li
              key={c.id}
              id={`${listId}-${idx}`}
              role="option"
              aria-selected={idx === active}
              className={idx === active ? 'active' : ''}
              onMouseEnter={() => setActive(idx)}
              onClick={() => choose(c)}
            >
              {c.image ? <img src={c.image} alt="" loading="lazy" /> : <div className="thumb" />}
              <div className="opt-text">
                <strong>{c.name}</strong>
                <span><span className="chip">{c.setName}</span> #{c.number}</span>
              </div>
              <span className="opt-add" aria-hidden="true">+ Add</span>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="msg error" role="alert">{error}</p>}
    </div>
  )
}

const STEPS = [
  ['starting', 'Opening Chrome'],
  ['waiting_login', 'Log in'],
  ['running', 'Adding cards'],
  ['finished', 'Done'],
]

function Progress({ status }) {
  if (status === 'idle') return null
  const idx = status === 'error' ? -1 : STEPS.findIndex(([k]) => k === status)
  return (
    <ol className="progress" aria-label="Progress">
      {STEPS.map(([k, label], i) => (
        <li key={k} className={i < idx ? 'done' : i === idx ? 'current' : ''}>
          <span className="dot">{i < idx || status === 'finished' ? '✓' : i + 1}</span>{label}
        </li>
      ))}
    </ol>
  )
}

export default function App() {
  const [items, setItems] = useState([]) // {id, label, image, setName, qty, status, options, pick}
  const [text, setText] = useState('')
  const [pasteBusy, setPasteBusy] = useState(false)
  const [addError, setAddError] = useState('')
  const [listName, setListName] = useState('')
  const [job, setJob] = useState({ status: 'idle', result: null, error: null })

  useEffect(() => {
    const t = setInterval(() => {
      fetch(`${API}/status`).then(r => r.json()).then(setJob).catch(() => {})
    }, 1000)
    return () => clearInterval(t)
  }, [])

  // when a run finishes, clear the card list (the result summary stays visible)
  const prevStatus = useRef(job.status)
  useEffect(() => {
    if (prevStatus.current !== 'finished' && job.status === 'finished') {
      setItems([])
      setText('')
    }
    prevStatus.current = job.status
  }, [job.status])

  const startNewBatchIfDone = () => {
    if (job.status === 'finished' || job.status === 'error') {
      post('/reset')
      setJob({ status: 'idle', result: null, error: null })
    }
  }

  const addCard = async c => {
    startNewBatchIfDone()
    const key = `card:${c.id}`
    if (items.some(i => i.id === key)) {
      setItems(cur => cur.map(i => (i.id === key ? { ...i, qty: Math.min(MAX_QTY, qtyOf(i) + 1) } : i)))
      return
    }
    try {
      const r = await fetch(`${API}/card-line/${c.id}`)
      if (!r.ok) throw new Error(`server error ${r.status}`)
      const { text: line } = await r.json()
      setAddError('')
      setItems(cur => [...cur, {
        id: key, label: c.name, setName: c.setName, number: c.number, image: c.image,
        qty: 1, status: 'ok', options: [line], pick: line,
      }])
    } catch (e) {
      setAddError(`Could not add ${c.name} (${c.setName} #${c.number}): ${e.message}`)
    }
  }

  const matchPasted = async () => {
    startNewBatchIfDone()
    setPasteBusy(true)
    try {
      const res = await post('/resolve', { text })
      setItems(cur => [...cur, ...res.map((r, i) => ({
        id: `paste:${Date.now()}:${i}`, label: r.raw, image: null, qty: r.qty,
        status: r.status, options: r.options, pick: r.status === 'ok' ? r.options[0] : '',
      }))])
      setText('')
    } finally {
      setPasteBusy(false)
    }
  }

  const update = (id, patch) => setItems(cur => cur.map(i => (i.id === id ? { ...i, ...patch } : i)))
  const remove = id => setItems(cur => cur.filter(i => i.id !== id))

  const ready = items.filter(i => i.pick)
  const lines = ready.map(i => `${qtyOf(i)} ${i.pick}`)
  const totalCopies = ready.reduce((s, i) => s + qtyOf(i), 0)
  const skipped = items.filter(i => !i.pick)
  const running = ['starting', 'waiting_login', 'running'].includes(job.status)
  const tooMany = lines.length > MAX_ENTRIES
  const nameOk = LIST_NAME_RE.test(listName.trim())
  const nameTouched = listName.length > 0

  let blocker = ''
  if (!lines.length) blocker = 'Add at least one card.'
  else if (tooMany) blocker = `Maximum ${MAX_ENTRIES} different cards per run.`
  else if (!nameOk) blocker = 'Enter a list name.'
  const canSend = !running && !blocker

  return (
    <>
      {job.status === 'waiting_login' && (
        <div className="banner" role="alert">
          <div>
            <strong>Log in to Cardmarket</strong>
            <span>Use the Chrome window that just opened and pass the Cloudflare check. Then continue here.</span>
          </div>
          <button className="btn primary" onClick={() => post('/logged-in')}>I'm logged in — continue</button>
        </div>
      )}

      <main>
        <header className="hero">
          <h1>Wants List Uploader</h1>
          <p>Find cards, pick the exact printing, and add them all to a Cardmarket wants list in one go.</p>
        </header>

        <section className="card-panel">
          <h2><span className="step">1</span>Find cards</h2>
          <CardSearch onPick={addCard} error={addError} />
          <details className="paste">
            <summary>Paste a list of names instead</summary>
            <textarea
              rows={5}
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder={'Umbreon ex\n2x Scoop Up Net\nGengar Fossil'}
              aria-label="Card names, one per line"
            />
            <div className="paste-actions">
              <span className="hint">One per line. Start with an amount like <code>2x</code> if you need more than one.</span>
              <button className="btn" disabled={pasteBusy || !text.trim()} onClick={matchPasted}>
                {pasteBusy ? <><Spinner /> Matching…</> : 'Add names'}
              </button>
            </div>
          </details>
        </section>

        <section className="card-panel">
          <h2>
            <span className="step">2</span>Your cards
            <span className="counter" aria-live="polite">{lines.length} cards · {totalCopies} copies</span>
          </h2>
          {items.length === 0 ? (
            <div className="empty">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 8h6M9 12h6" /></svg>
              <p>No cards yet</p>
              <span>Search above and click a result to add it.</span>
            </div>
          ) : (
            <ul className="cards">
              {items.map(i => (
                <li key={i.id} className={`row ${i.status !== 'ok' && !i.pick ? 'attention' : ''}`}>
                  {i.image ? <img src={i.image} alt="" loading="lazy" /> : <div className="thumb" />}
                  <div className="row-main">
                    <div className="row-title">
                      <strong>{i.label}</strong>
                      {i.setName && <span className="chip">{i.setName} #{i.number}</span>}
                    </div>
                    {i.status === 'not_found' && <span className="msg error">Not found — it will be skipped</span>}
                    {i.status === 'ambiguous' && (
                      <select value={i.pick} onChange={e => update(i.id, { pick: e.target.value })} aria-label={`Version of ${i.label}`}>
                        <option value="">Choose a version…</option>
                        {i.options.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    )}
                    {i.pick && <code className="line">{i.pick}</code>}
                  </div>
                  <QtyStepper value={i.qty} onChange={v => update(i.id, { qty: v })} />
                  <button className="icon-btn" onClick={() => remove(i.id)} aria-label={`Remove ${i.label}`}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {tooMany && <p className="msg error">Over the limit of {MAX_ENTRIES} different cards.</p>}
        </section>

        <section className="card-panel">
          <h2><span className="step">3</span>Send to Cardmarket</h2>
          <div className="send">
            <div className="field">
              <label htmlFor="listname">Wants list name</label>
              <input
                id="listname"
                value={listName}
                maxLength={30}
                onChange={e => setListName(e.target.value)}
                placeholder="e.g. 151 Collection"
                aria-invalid={nameTouched && !nameOk}
                disabled={running}
              />
              <span className={`hint ${nameTouched && !nameOk ? 'error' : ''}`}>
                Created if it doesn't exist. Letters, numbers, spaces and hyphens only · {listName.length}/30
              </span>
            </div>
            <button
              className="btn primary big"
              disabled={!canSend}
              onClick={() => { startNewBatchIfDone(); post('/start', { lines, list: listName.trim() }) }}
            >
              {running ? <><Spinner /> Working…</> : `Add ${lines.length} ${lines.length === 1 ? 'card' : 'cards'}`}
            </button>
          </div>
          {blocker && !running && <p className="hint">{blocker}</p>}
          {skipped.length > 0 && (
            <p className="msg warn">Won't be sent (no version chosen or not found): {skipped.map(s => s.label).join(', ')}</p>
          )}

          <Progress status={job.status} />
          {job.status === 'error' && (
            <p className="msg error" role="alert">
              Something went wrong: {job.error}. A screenshot was saved in the <code>debug</code> folder.
            </p>
          )}

          {job.result && (
            <div className="result">
              <div className="stats">
                <div className="stat ok"><b>{job.result.added.length}</b><span>added</span></div>
                <div className={`stat ${job.result.not_added.length ? 'bad' : ''}`}><b>{job.result.not_added.length}</b><span>not added</span></div>
                <button className="btn" onClick={startNewBatchIfDone}>Clear result</button>
              </div>
              {job.result.not_added.length > 0 && (
                <>
                  <h3>Not added</h3>
                  <ul className="plain">{job.result.not_added.map(l => <li key={l}><code>{l}</code></li>)}</ul>
                </>
              )}
              <details>
                <summary>What Cardmarket said</summary>
                <pre>{job.result.messages.join('\n\n')}</pre>
              </details>
            </div>
          )}
        </section>
      </main>
    </>
  )
}
