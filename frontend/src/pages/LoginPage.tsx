import { useState, type FormEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { Icon } from "../components/Icon";

const accounts = [
  { role: "Staff", email: "staff@enterprise.local" },
  { role: "Manager", email: "manager@enterprise.local" },
  { role: "Executive", email: "executive@enterprise.local" },
];

export function LoginPage() {
  const { signIn } = useAuth();
  const [username, setUsername] = useState("manager@enterprise.local");
  const [password, setPassword] = useState("demo123");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn(username, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-symbol">
            <Icon name="sparkles" size={26} />
          </span>
          <span>
            Enterprise RAG<small>KNOWLEDGE ASSISTANT</small>
          </span>
        </div>
        <div className="login-story-content">
          <span className="story-kicker">YOUR KNOWLEDGE. CONNECTED.</span>
          <h1>
            Clear answers.
            <br />
            Trusted sources.
          </h1>
          <p>
            Find what matters in your enterprise documents, with answers you can
            trace back to the source.
          </p>
          <div className="story-preview">
            <div className="story-question">
              <Icon name="chat" size={18} />
              What is our remote work policy?
            </div>
            <div className="story-answer">
              <Icon name="sparkles" size={22} />
              <div>
                Work remotely up to three days a week with your manager’s
                approval.
                <span>
                  <Icon name="file" size={14} />
                  Remote_Work_Policy.md · Hybrid schedule
                </span>
              </div>
            </div>
          </div>
          <div className="story-features">
            <span>
              <Icon name="shield" size={17} />
              Role-aware access
            </span>
            <span>
              <Icon name="file" size={17} />
              Verifiable citations
            </span>
          </div>
        </div>
        <div className="story-footer">
          Built for better knowledge discovery.
        </div>
      </section>
      <section className="login-form-area">
        <div className="login-form-wrap">
          <header className="login-form-header">
            <div className="login-brand">
              <span className="login-logo" aria-hidden="true">
                <Icon name="sparkles" size={34} />
              </span>
              <span className="login-brand-text">
                Enterprise <span className="login-brand-accent">RAG</span>
                <small>KNOWLEDGE ASSISTANT</small>
              </span>
            </div>
            <h2>Welcome to your workspace</h2>
            <p className="muted">Sign in to explore your team’s knowledge.</p>
          </header>
          <form onSubmit={submit} className="login-form">
            <label htmlFor="username">Email address</label>
            <input
              id="username"
              type="email"
              autoComplete="username"
              placeholder="Enter your work email"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              disabled={busy}
            />
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={busy}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword((value) => !value)}
              >
                <Icon name={showPassword ? "eyeOff" : "eye"} size={18} />
              </button>
            </div>
            {error && (
              <div className="notice error" role="alert">
                <Icon name="alert" size={18} />
                {error}
              </div>
            )}
            <button className="button primary login-submit" disabled={busy}>
              {busy ? (
                <>
                  <span className="spinner" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <Icon name="chevron" size={18} />
                </>
              )}
            </button>
          </form>
          <div className="quick-signin">
            <div className="quick-signin-title">
              Quick sign-in
              <span>
                Password: <strong>demo123</strong>
              </span>
            </div>
            <div className="role-options">
              {accounts.map((account) => (
                <button
                  key={account.role}
                  type="button"
                  disabled={busy}
                  className={username === account.email ? "selected" : ""}
                  aria-pressed={username === account.email}
                  onClick={() => {
                    setUsername(account.email);
                    setPassword("demo123");
                    setError("");
                  }}
                >
                  {account.role}
                </button>
              ))}
            </div>
          </div>
          <div className="login-footer">
            Enterprise RAG Knowledge Assistant
          </div>
        </div>
      </section>
    </main>
  );
}
