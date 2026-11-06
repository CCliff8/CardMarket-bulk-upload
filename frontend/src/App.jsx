import { useEffect, useRef, useState } from 'react'

const API = 'http://127.0.0.1:5001/api'
const MAX = 150
const post = (path, body) =>
  fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }).then(r => r.json())

export default function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [items, setItems] = useState([]) // {id, label, image, qty, status, options, pick}
  const [listName, setListName] = useState('')
  const [busy, setBusy] = useState(false)
  const [addError, setAddError] = useState('')
  const [job, setJob] = useState({ status: 'idle', result: null, error: null })
  const boxRef = useRef(null)

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
      setQuery('')
      setText('')
    }
    prevStatus.current = job.status
  }, [job.status])

  // debounced autocomplete
  useEffect(() => {
    if (query.trim().length < 2) { setResults([]); return }
    const t = setTimeout(() => {
      fetch(`${API}/search?q=${encodeURIComponent(query.trim())}`)
        .then(r => r.json()).then(r => { setResults(r); setOpen(true) }).catch(() => {})
    }, 250)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    const close = e => { if (!boxRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const startNewBatchIfDone = () => {
    if (job.status === 'finished' || job.status === 'error') {
      post('/reset')
      setJob({ status: 'idle', result: null, error: null })
    }
  }

  const addCard = async c => {
    startNewBatchIfDone()
    const key = `card:${c.id}`
    setOpen(false)
    setQuery('')
    if (items.some(i => i.id === key)) {
      setItems(items.map(i => (i.id === key ? { ...i, qty: i.qty + 1 } : i)))
      return
    }
    let line
    try {
      const r = await fetch(`${API}/card-line/${c.id}`)
      if (!r.ok) throw new Error(`server error ${r.status}`)
      line = (await r.json()).text
    } catch (e) {
      setAddError(`Could not add ${c.name} (${c.setName} #${c.number}): ${e.message}`)
      return
    }
    setAddError('')
    setItems(cur => [...cur, {
      id: key, label: `${c.name} — ${c.setName} #${c.number}`, image: c.image,
      qty: 1, status: 'ok', options: [line], pick: line,
    }])
  }

  const matchPasted = async () => {
    startNewBatchIfDone()
    setBusy(true)
    const res = await post('/resolve', { text })
    setItems(cur => [...cur, ...res.map((r, i) => ({
      id: `paste:${Date.now()}:${i}`, label: r.raw, image: null, qty: r.qty,
      status: r.status, options: r.options, pick: r.status === 'ok' ? r.options[0] : '',
    }))])
    setText('')
    setBusy(false)
  }

  const update = (id, patch) => setItems(items.map(i => (i.id === id ? { ...i, ...patch } : i)))
  const remove = id => setItems(items.filter(i => i.id !== id))

  const ready = items.filter(i => i.pick)
  const lines = ready.map(i => `${i.qty} ${i.pick}`)
  const skipped = items.filter(i => !i.pick)
  const running = ['starting', 'waiting_login', 'running'].includes(job.status)
  const tooMany = lines.length > MAX

  return (
    <main>
      {job.status === 'waiting_login' && (
        <div className="banner">
          <span>Log in to Cardmarket in the Chrome window that opened (pass the Cloudflare check). When you see you are logged in, click:</span>
          <button className="primary" onClick={() => post('/logged-in')}>I'm logged in — continue</button>
        </div>
      )}
      <h1>Cardmarket Wants List Uploader</h1>

      <section className="panel">
        <h2>1. Search a card</h2>
        <div className="search" ref={boxRef}>
          <input
            placeholder="Type a name, e.g. “charizard 151” or “gengar fossil”"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={() => results.length && setOpen(true)}
          />
          {open && results.length > 0 && (
            <ul className="dropdown">
              {results.map(c => (
                <li key={c.id} onClick={() => addCard(c)}>
                  {c.image ? <img src={c.image} alt="" /> : <div className="thumb" />}
                  <span><strong>{c.name}</strong><br /><small>{c.setName} · #{c.number}</small></span>
                </li>
              ))}
            </ul>
          )}
          {open && query.trim().length >= 2 && results.length === 0 && <div className="dropdown empty">No cards found</div>}
        </div>
        {addError && <p className="bad">{addError}</p>}
        <details>
          <summary>Or paste a list of names</summary>
          <textarea rows={6} value={text} onChange={e => setText(e.target.value)} placeholder={'Umbreon ex\n2x Scoop Up Net\nMunkidori'} />
          <button className="primary" disabled={busy || !text.trim()} onClick={matchPasted}>
            {busy ? 'Matching…' : 'Add pasted names'}
          </button>
        </details>
      </section>

      <section className="panel">
        <h2>2. Your cards ({lines.length}/{MAX})</h2>
        {items.length === 0 && <p className="hint">Nothing yet. Search above and click a card to add it.</p>}
        <table>
          <tbody>
            {items.map(i => (
              <tr key={i.id} className={i.status}>
                <td className="img">{i.image && <img src={i.image} alt="" />}</td>
                <td>
                  <div>{i.label}</div>
                  {i.status === 'ok' && <small><code>{i.pick}</code></small>}
                  {i.status === 'not_found' && <em>Not found — will be skipped</em>}
                  {i.status === 'ambiguous' && (
                    <select value={i.pick} onChange={e => update(i.id, { pick: e.target.value })}>
                      <option value="">Choose a version…</option>
                      {i.options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  )}
                </td>
                <td className="qty">
                  <input type="number" min="1" value={i.qty} onChange={e => update(i.id, { qty: Math.max(1, +e.target.value || 1) })} />
                </td>
                <td><button onClick={() => remove(i.id)} aria-label="Remove">✕</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {tooMany && <p className="bad">Over the {MAX} limit.</p>}
      </section>

      <section className="panel">
        <h2>3. Send to Cardmarket</h2>
        <div className="row">
          <input placeholder="Wants list name (created if missing)" value={listName} onChange={e => setListName(e.target.value)} />
          <button className="primary" disabled={running || !lines.length || tooMany || !listName.trim()}
            onClick={() => post('/start', { lines, list: listName.trim() })}>
            Add {lines.length} cards
          </button>
        </div>
        {running && job.status !== 'waiting_login' && <p>Working… ({job.status})</p>}
        {job.status === 'error' && <p className="bad">Error: {job.error}. Screenshots saved in <code>debug/</code>.</p>}
        {job.result && (
          <div>
            <h3>{job.result.added.length} added, {job.result.not_added.length} not added{' '}
              <button onClick={startNewBatchIfDone}>Clear result</button></h3>
            {job.result.not_added.length > 0 && <ul>{job.result.not_added.map(l => <li key={l}>{l}</li>)}</ul>}
            <pre>{job.result.messages.join('\n')}</pre>
          </div>
        )}
        {skipped.length > 0 && <p className="hint">Not sent (no version chosen / not found): {skipped.map(s => s.label).join(', ')}</p>}
      </section>
    </main>
  )
}
