"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

type Identity = { user_id: string; patient_id: string; email: string; role: "patient" };
type Disclosure = { version: "history-v1"; text: string };
type ChatResponse = { text: string; status: string };
type History = { id: string; expires_at: string; truncated: boolean; turns: { id: string; user_text: string; response: ChatResponse }[] };
const POINTER = "careflow.conversation";

class ApiError extends Error {
  constructor(readonly status: number, readonly code: string) { super(code); }
}

async function request<T>(path: string, method = "GET", body?: unknown, csrf?: string): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method, credentials: "same-origin", cache: "no-store", redirect: "error",
    headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(response.status, error.code ?? "API_UNAVAILABLE");
  }
  return response.status === 204 ? undefined as T : response.json();
}

function pointer(value?: string | null) {
  try {
    if (value === null) localStorage.removeItem(POINTER);
    else if (value !== undefined) localStorage.setItem(POINTER, value);
    else return localStorage.getItem(POINTER);
  } catch { /* Storage may be disabled; the current chat remains memory-only. */ }
  return null;
}

export default function PatientWorkspace() {
  const epoch = useRef(0);
  const csrf = useRef("");
  const [phase, setPhase] = useState<"loading" | "signed-out" | "authenticated">("loading");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [logoutPending, setLogoutPending] = useState(false);
  const [message, setMessage] = useState("");
  const [pendingTurn, setPendingTurn] = useState<{ turn_id: string; message: string } | null>(null);

  const clear = useCallback((message: string) => {
    epoch.current += 1;
    csrf.current = "";
    setIdentity(null); setHistory(null); setDisclosure(null); setAccepted(false);
    setMessage(""); setPendingTurn(null);
    setBusy(false); setNotice(message); setPhase("signed-out");
  }, []);

  function report(error: unknown, generation: number) {
    if (epoch.current !== generation) return;
    if (error instanceof ApiError && error.code === "INVALID_CREDENTIALS") {
      setNotice("Email or password was not accepted.");
    } else if (error instanceof ApiError && error.status === 401) {
      clear("Your session has ended. Sign in to continue.");
    } else {
      setNotice(error instanceof ApiError && error.status === 429
          ? "Too many attempts. Please wait five minutes before trying again."
          : "This request could not be completed. Please try again.");
    }
  }

  const recover = useCallback(async () => {
    const generation = ++epoch.current;
    setPhase("loading"); setIdentity(null); setHistory(null);
    setDisclosure(null); setAccepted(false); setMessage(""); setPendingTurn(null);
    setBusy(false); setNotice("");
    try {
      const token = await request<{ csrf_token: string }>("/auth/csrf");
      // Bootstrap can replace an expired cookie with a pre-login session.
      // Resolve patient authority only after that cookie-setting response.
      const patient = await request<Identity>("/auth/me");
      if (epoch.current !== generation) return;
      csrf.current = token.csrf_token;
      setIdentity(patient);
      const stored = pointer();
      if (stored) {
        try {
          const saved = await request<History>(`/conversations/${encodeURIComponent(stored)}`);
          if (epoch.current !== generation) return;
          setHistory(saved);
          setPhase("authenticated");
          return;
        } catch (error) {
          if (epoch.current !== generation) return;
          if (!(error instanceof ApiError) || ![404, 422].includes(error.status)) throw error;
          pointer(null);
          setNotice("Your saved chat is no longer available. You can create a new one below.");
        }
      }
      const information = await request<Disclosure>("/chat/disclosure");
      if (epoch.current === generation) {
        setDisclosure(information); setPhase("authenticated");
      }
    } catch (error) {
      if (epoch.current !== generation) return;
      if (error instanceof ApiError && error.status === 401) clear("");
      else clear("The service is unavailable. Try checking your session again.");
    }
  }, [clear]);

  useEffect(() => {
    const timer = window.setTimeout(() => void recover(), 0);
    return () => { window.clearTimeout(timer); epoch.current += 1; };
  }, [recover]);

  useEffect(() => {
    if (phase !== "authenticated" || !identity) return;
    const check = async () => {
      const generation = epoch.current;
      try {
        const current = await request<Identity>("/auth/me");
        if (epoch.current === generation && (current.user_id !== identity.user_id || current.patient_id !== identity.patient_id)) {
          clear("The signed-in account changed. Check your session to continue.");
        }
      }
      catch (error) {
        if (epoch.current === generation && error instanceof ApiError && error.status === 401) clear("Your session has ended. Sign in to continue.");
      }
    };
    const visible = () => { if (!document.hidden) void check(); };
    const timer = window.setInterval(() => void check(), 30000);
    window.addEventListener("focus", visible);
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("pageshow", visible);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", visible);
      document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("pageshow", visible);
    };
  }, [phase, identity, clear]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const generation = epoch.current;
    setBusy(true); setNotice("");
    try {
      const token = await request<{ csrf_token: string }>("/auth/csrf");
      if (epoch.current !== generation) return;
      await request("/auth/login", "POST", { email: fields.get("email"), password: fields.get("password") }, token.csrf_token);
      form.reset();
      if (epoch.current === generation) await recover();
    } catch (error) { report(error, generation); }
    finally { if (epoch.current === generation || phase === "signed-out") setBusy(false); }
  }

  async function createChat() {
    if (!accepted || !disclosure || busy) return;
    const generation = epoch.current;
    setBusy(true); setNotice("");
    try {
      const created = await request<{ id: string; expires_at: string }>("/conversations", "POST", { disclosure_version: disclosure.version }, csrf.current);
      if (epoch.current !== generation) return;
      pointer(created.id);
      setHistory({ ...created, turns: [], truncated: false });
    } catch (error) { report(error, generation); }
    finally { if (epoch.current === generation) setBusy(false); }
  }

  async function signOut() {
    const token = csrf.current;
    clear("");
    setBusy(true); setLogoutPending(true);
    try {
      const fresh = token || (await request<{ csrf_token: string }>("/auth/csrf")).csrf_token;
      await request("/auth/logout", "POST", undefined, fresh);
      setLogoutPending(false); setNotice("You are signed out.");
    } catch { setNotice("Sign-out could not be confirmed. Please retry sign out."); }
    finally { setBusy(false); }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!history || busy || !message.trim()) return;
    const generation = epoch.current;
    const turn = pendingTurn?.message === message
      ? pendingTurn : { turn_id: crypto.randomUUID(), message };
    setPendingTurn(turn);
    setBusy(true); setNotice("");
    try {
      const result = await request<{ historical: boolean; response: ChatResponse }>(`/conversations/${history.id}/turns`, "POST", turn, csrf.current);
      if (epoch.current !== generation) return;
      // Keep only display text/status; protected action proofs have no UI here.
      const response = { text: result.response.text, status: result.response.status };
      setHistory((current) => current && { ...current, turns: [...current.turns, { id: turn.turn_id, user_text: turn.message, response }] });
      setPendingTurn(null); setMessage("");
    } catch (error) {
      if (epoch.current !== generation) return;
      if (error instanceof ApiError && error.status === 404) {
        await recover();
      } else if (error instanceof ApiError && error.status === 401) {
        report(error, generation);
      } else {
        setNotice("Chat is unavailable. Retry your message or reload to check saved history.");
      }
    } finally { if (epoch.current === generation) setBusy(false); }
  }

  return <div className="workspace">
    <header className="topbar"><div className="brand"><span className="brand-mark">+</span>CareFlow <span className="ai">AI</span></div><span className="demo-label">Synthetic data · Development only</span></header>
    <div className="layout">
      <aside className="sidebar"><p className="eyebrow">PATIENT WORKSPACE</p><div className="nav-item active">Chat</div><div className="nav-item muted">My Appointments <span>Soon</span></div><p className="sidebar-note">Clinic operations assistance.<br />For synthetic patients only.</p></aside>
      <main id="main">
        <div className="page-heading"><div><p className="eyebrow">YOUR PATIENT WORKSPACE</p><h1>A little help with the next step.</h1></div>{identity && <button className="secondary" onClick={() => void signOut()} disabled={logoutPending}>Sign out</button>}</div>
        <p className="intro">Sign in to securely access your saved conversation.</p>
        {notice && <p role="status" className="notice">{notice}</p>}
        {phase === "loading" && <p role="status">Checking your session…</p>}
        {phase === "signed-out" && <section className="card auth-card"><p className="eyebrow">WELCOME BACK</p><h2>Sign in</h2><p>Use your provisioned synthetic patient account.</p>{logoutPending ? <button onClick={() => void signOut()} disabled={busy}>Retry sign out</button> : <form onSubmit={(event) => void signIn(event)}><label htmlFor="email">Email</label><input id="email" name="email" type="email" autoComplete="username" maxLength={160} required disabled={busy} /><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={128} required disabled={busy} /><button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button></form>}<button className="text-button" onClick={() => void recover()} disabled={busy || logoutPending}>Check session again</button><p className="small">Accounts are provisioned by the demo operator. Registration and password recovery are unavailable.</p></section>}
        {phase === "authenticated" && !history && <section className="card disclosure"><p className="eyebrow">SAVED CONVERSATIONS</p><h2>Before you save a chat</h2>{disclosure ? <><p className="disclosure-text">{disclosure.text}</p><label className="check"><input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} disabled={busy} />I accept the storage disclosure</label><button disabled={!accepted || busy} onClick={() => void createChat()}>{busy ? "Creating…" : "Create saved chat"}</button></> : <p role="status">Loading storage disclosure…</p>}<div className="supplement"><strong>Additional processing disclosure</strong><p>Voyage integration is pending. No embedding feature is enabled in this interface; its terms have not been verified.</p></div></section>}
        {phase === "authenticated" && history && <section className="card"><h2>Your saved chat</h2><p className="small">Saved until {new Date(history.expires_at).toLocaleDateString("en-GB")}. Historical responses do not establish current clinic state.</p>{history.truncated && <p className="small">Showing the most recent saved turns.</p>}<div className="transcript" role="log" aria-label="Saved conversation">{history.turns.length === 0 && <p className="empty-chat">Your conversation starts here. Ask about clinic operations using synthetic information only.</p>}{history.turns.map((turn) => <div key={turn.id}><div className="message patient"><span>You</span><p>{turn.user_text}</p></div><div className="message assistant"><span>CareFlow</span><p>{turn.response.text}</p></div></div>)}</div><form onSubmit={(event) => void sendMessage(event)}><label htmlFor="message">Message</label><textarea id="message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={2000} required disabled={busy} placeholder="Ask a clinic operations question…" /><div className="compose-footer"><p className="small">Synthetic information only · {message.length}/2000</p><button type="submit" disabled={busy || !message.trim()}>{busy ? "Sending…" : pendingTurn?.message === message ? "Retry message" : "Send message"}</button></div></form></section>}
        <footer>Healthcare operations only. This demo does not diagnose, prescribe or provide definitive triage.</footer>
      </main>
    </div>
  </div>;
}
