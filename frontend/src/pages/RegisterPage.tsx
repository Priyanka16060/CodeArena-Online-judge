import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(username, email, password);
      navigate("/problems");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Could not register. Try a different username or email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <h1>Open a Case File</h1>
      <p className="sub">Register to start submitting solutions.</p>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <div className="hint" style={{ marginTop: "0.35rem" }}>
            At least 8 characters.
          </div>
        </div>
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Registering…" : "Register"}
        </button>
      </form>
      <p className="hint">
        Already have a file? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
