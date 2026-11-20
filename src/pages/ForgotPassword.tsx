import { FormEvent, useRef, useState } from "react";
import { Plane } from "lucide-react";
import { Link } from "react-router-dom";

import { requestPasswordReset } from "../services/api";

const emailPattern = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;

export default function ForgotPassword() {
  const submittingRef = useRef(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current) return;
    if (!email.trim()) { setError("Email is required."); return; }
    if (!emailPattern.test(email.trim())) { setError("Enter a valid email address with a complete domain."); return; }
    setError("");
    setMessage("");
    submittingRef.current = true;
    setSubmitting(true);
    try {
      const result = await requestPasswordReset(email.trim().toLowerCase());
      setMessage(result.email_delivery_configured
        ? result.message
        : `${result.message} SMTP is not configured, so no email was sent. Contact your administrator.`);
    } catch {
      setMessage("If an account matches, the request will be processed. This response does not confirm account existence or email delivery.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return <div className="auth-page"><div className="auth-card">
    <div className="auth-logo"><div className="brand-icon"><Plane size={20} /></div><strong>AEROVISION</strong></div>
    <h1>Reset your password</h1><p>Enter the email address associated with your account.</p>
    {message && <div className="auth-alert auth-success" role="status">{message}</div>}
    <form onSubmit={(event) => void submit(event)} noValidate>
      <label className="auth-field-label" htmlFor="reset-request-email">Email address</label>
      <input id="reset-request-email" className="auth-input" type="email" autoComplete="email" inputMode="email" required value={email} aria-invalid={Boolean(error)} aria-describedby={error ? "reset-request-error" : undefined} onChange={(event) => setEmail(event.currentTarget.value)} />
      {error && <span className="auth-field-error" id="reset-request-error">{error}</span>}
      <button type="submit" className="primary-button auth-button" disabled={submitting}>{submitting ? <><span className="auth-spinner" aria-hidden="true" /> Sending…</> : "Send reset instructions"}</button>
    </form>
    <div className="auth-footer"><Link to="/login">Back to sign in</Link></div>
  </div></div>;
}
