import { useEffect, useState } from 'react'

const API = 'http://127.0.0.1:5001/api'
const MAX = 150
const post = (path, body) =>
  fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  }).then(r => r.json())

export default function App() {
  const [text, setText] = useState('')
  const [listName, setListName] = useState('')
  const [items, setItems] = useState(null)
  const [picks, setPicks] = useState({})
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState({ status: 'idle', result: null, error: null })

  useEffect(() => {
    const t = setInterval(() => {
      fetch(`${API}/status`).then(r => r.json()).then(setJob).catch(() => {})
    }, 1000)
    return () => clearInterval(t)
  }, [])

  const resolve = async () => {
    setBusy(true)
    setPicks({})
    setItems(await post('/resolve', { text }))
    setBusy(false)
  }

  const lineFor = (it, i) =>
    it.line ?? (picks[i] !== undefined && picks[i] !== '' ? `${it.qty} ${picks[i]}` : null)

  const lines = (items ?? []).map(lineFor).filter(Boolean)
  const skipped = (items ?? []).filter((it, i) => !lineFor(it, i))
  const running = ['starting', 'waiting_login', 'running'].includes(job.status)
  const tooMany = lines.length > MAX

  return (
    <main>
      <h1>Cardmarket Wants List Uploader</h1>

      <section className="panel">
        <h2>1. Paste card names</h2>
        <p className="hint">One per line. Optional amount: <code>2x Charizard ex</code>. Max {MAX} entries per run.</p>
        <textarea rows={10} value={text} onChange={e => setText(e.target.value)} placeholder={'Umbreon ex\n2x Scoop Up Net\nMunkidori'} />
        <button className="primary" disabled={busy || !text.trim()} onClick={resolve}>
          {busy ? 'Matching…' : 'Match cards'}
        </button>
      </section>

      {items && (
        <section className="panel">
          <h2>2. Review</h2>
          <table>
            <tbody>
              {items.map((it, i) => (
                <tr key={i} className={it.status}>
                  <td>{it.raw}</td>
                  <td>
                    {it.status === 'ok' && <code>{it.line}</code>}
                    {it.status === 'not_found' && <em>Not found — will be skipped</em>}
                    {it.status === 'ambiguous' && (
                      <select value={picks[i] ?? ''} onChange={e => setPicks({ ...picks, [i]: e.target.value })}>
                        <option value="">Choose a version…</option>
                        {it.options.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>{lines.length} ready, {skipped.length} will be skipped.{tooMany && <strong> Over the {MAX} limit.</strong>}</p>
        </section>
      )}

      {items && (
        <section className="panel">
          <h2>3. Send to Cardmarket</h2>
          <div className="row">
            <input placeholder="Wants list name (created if missing)" value={listName} onChange={e => setListName(e.target.value)} />
            <button className="primary" disabled={running || !lines.length || tooMany || !listName.trim()}
              onClick={() => post('/start', { lines, list: listName.trim() })}>
              Add {lines.length} cards
            </button>
          </div>
          {job.status === 'waiting_login' && (
            <p>
              Log in to Cardmarket in the browser window that opened, then{' '}
              <button className="primary" onClick={() => post('/logged-in')}>I'm logged in</button>
            </p>
          )}
          {running && job.status !== 'waiting_login' && <p>Working… ({job.status})</p>}
          {job.status === 'error' && <p className="bad">Error: {job.error}. Screenshots saved in <code>debug/</code>.</p>}
          {job.result && (
            <div>
              <h3>{job.result.added.length} added, {job.result.not_added.length} not added</h3>
              {job.result.not_added.length > 0 && <ul>{job.result.not_added.map(l => <li key={l}>{l}</li>)}</ul>}
              <pre>{job.result.messages.join('\n')}</pre>
            </div>
          )}
          {skipped.length > 0 && <p className="hint">Never sent: {skipped.map(s => s.raw).join(', ')}</p>}
        </section>
      )}
    </main>
  )
}
