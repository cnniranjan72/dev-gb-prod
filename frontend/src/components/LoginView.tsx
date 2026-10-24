import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'

const DEMO_HINT = [
  { role: 'analyst', email: 'analyst@windlens.demo', password: 'windlens-analyst' },
  { role: 'admin', email: 'admin@windlens.demo', password: 'windlens-admin' },
]

export function LoginView({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState(DEMO_HINT[0].email)
  const [password, setPassword] = useState(DEMO_HINT[0].password)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await onLogin(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <div className="w-full max-w-sm space-y-6 rounded-2xl border border-ink-800 bg-ink-900/80 p-8 shadow-2xl shadow-black/40">
        <div>
          <p className="font-mono text-[11px] tracking-[0.3em] text-ink-500 uppercase">WindLens</p>
          <h1 className="mt-1 text-xl text-ink-100">Sign in to the analytics workspace</h1>
          <p className="mt-2 text-sm text-ink-400">
            Elexon FUELHH actuals vs WINDFOR forecast vintages for January 2026. Access is role-gated: viewers see
            dashboards, analysts also get the vintage explorer, admins manage accounts.
          </p>
        </div>
        <form className="space-y-3" onSubmit={submit}>
          <label className="block text-xs text-ink-400">
            Email
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-ink-700 bg-ink-850 px-3 py-2 text-sm text-ink-200"
            />
          </label>
          <label className="block text-xs text-ink-400">
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-ink-700 bg-ink-850 px-3 py-2 text-sm text-ink-200"
            />
          </label>
          {error && <p className="rounded-md border border-underrose-400/40 bg-underrose-400/10 px-3 py-2 text-xs text-underrose-400">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-astral-500 px-3 py-2 text-sm text-ink-950 hover:bg-astral-400 disabled:opacity-60"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <div className="rounded-md border border-ink-800 bg-ink-850/60 px-3 py-2 text-[11px] text-ink-500">
          <p className="text-ink-400">Demo accounts (seeded, documented in the README):</p>
          <ul className="mt-1 space-y-0.5 font-mono">
            {DEMO_HINT.map((account) => (
              <li key={account.email}>
                <button
                  type="button"
                  className="underline decoration-dotted hover:text-astral-400"
                  onClick={() => {
                    setEmail(account.email)
                    setPassword(account.password)
                  }}
                >
                  {account.role}: {account.email}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function SessionBadge({ identity, onLogout }: { identity: { email: string; role: string } | null; onLogout: () => void }) {
  const [user, setUser] = useState(identity)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (identity) return
    api
      .me()
      .then((me) => {
        if (!cancelled) setUser({ email: me.email, role: me.role })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [identity])

  if (!user) {
    return (
      <button
        onClick={onLogout}
        className="rounded-md border border-ink-700 px-3 py-1 text-xs text-ink-300 hover:border-ink-500"
        title={failed ? 'session could not be verified' : 'sign out'}
      >
        {failed ? 'session — sign in' : '…'}
      </button>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-[11px] text-ink-400 sm:inline">{user.email}</span>
      <span className="rounded border border-astral-500/60 bg-astral-500/15 px-1.5 py-0.5 font-mono text-[10px] tracking-wide text-astral-400 uppercase">
        {user.role}
      </span>
      <button
        onClick={onLogout}
        className="rounded-md border border-ink-700 px-2.5 py-1 text-xs text-ink-300 hover:border-ink-500 hover:text-ink-100"
      >
        Sign out
      </button>
    </div>
  )
}
