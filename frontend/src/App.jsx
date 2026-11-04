import { useEffect, useMemo, useState } from 'react'

const API = 'http://127.0.0.1:5001/api'
const post = (path, body) =>
  fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })

export default function App() {
  const [sets, setSets] = useState([])
  const [setId, setSetId] = useState('')
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(new Set())
  const [filter, setFilter] = useState('')
  const [watchlist, setWatchlist] = useState('')
  const [delay, setDelay] = useState(3)
  const [job, setJob] = useState({ status: 'idle', total: 0, index: 0, log: [] })

  useEffect(() => {
    fetch(`${API}/sets`).then(r => r.json()).then(setSets).catch(() => {})
  }, [])

  useEffect(() => {
    const t = setInterval(() => {
      fetch(`${API}/status`).then(r => r.json()).then(setJob).catch(() => {})
    }, 1000)
    return () => clearInterval(t)
  }, [])

  const loadSet = async id => {
    setSetId(id)
    setCards([])
    setSelected(new Set())
    if (!id) return
    setLoading(true)
    const data = await fetch(`${API}/sets/${id}/cards`).then(r => r.json())
    setCards(data)
    setLoading(false)
  }

  const shown = useMemo(() => {
    const f = filter.toLowerCase()
    return cards.filter(c => c.name.toLowerCase().includes(f) || c.number.includes(f))
  }, [cards, filter])

  const toggle = id =>
    setSelected(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  const selectShown = on =>
    setSelected(s => {
      const n = new Set(s)
      shown.filter(c => c.url).forEach(c => (on ? n.add(c.id) : n.delete(c.id)))
      return n
    })

  const busy = ['starting', 'waiting_login', 'running'].includes(job.status)
  const start = () =>
    post('/start', { cards: cards.filter(c => selected.has(c.id)), watchlist, delay })
  const pct = job.total ? Math.round((job.index / job.total) * 100) : 0

  return (
    <main>
      <h1>Cardmarket Bulk Watchlist</h1>

      <section className="controls">
        <select value={setId} onChange={e => loadSet(e.target.value)}>
          <option value="">Choose a set…</option>
          {sets.map(s => (
            <option key={s.id} value={s.id}>{s.name} ({s.id})</option>
          ))}
        </select>
        <input placeholder="Watchlist name" value={watchlist} onChange={e => setWatchlist(e.target.value)} />
        <label>
          Delay (s)
          <input type="number" min="1" value={delay} onChange={e => setDelay(e.target.value)} />
        </label>
      </section>

      <section className="controls">
        <input placeholder="Filter by name or number" value={filter} onChange={e => setFilter(e.target.value)} />
        <button onClick={() => selectShown(true)}>Select all</button>
        <button onClick={() => selectShown(false)}>Select none</button>
        <button className="primary" disabled={busy || !selected.size || !watchlist} onClick={start}>
          Add {selected.size} cards
        </button>
      </section>

      {loading && <p>Loading cards…</p>}

      <div className="grid">
        {shown.map(c => (
          <label key={c.id} className={`card ${selected.has(c.id) ? 'on' : ''} ${c.url ? '' : 'off'}`}>
            <input type="checkbox" disabled={!c.url} checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
            {c.image ? <img src={c.image} alt={c.name} loading="lazy" /> : <div className="noimg" />}
            <span>#{c.number} {c.name}</span>
          </label>
        ))}
      </div>

      {job.status !== 'idle' && (
        <section className="job">
          <strong>Status: {job.status}</strong>
          {job.status === 'waiting_login' && (
            <button className="primary" onClick={() => post('/logged-in')}>I'm logged in</button>
          )}
          {busy && <button onClick={() => post('/stop')}>Stop</button>}
          <progress value={job.index} max={job.total || 1} /> {pct}% ({job.index}/{job.total})
          <pre>{job.log.join('\n')}</pre>
        </section>
      )}
    </main>
  )
}
