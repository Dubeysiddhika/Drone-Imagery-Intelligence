import { FormEvent, useMemo, useRef, useState } from "react";
import { Check, Eye, EyeOff, Plane, X } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { confirmPasswordReset } from "../services/api";

const rules = [
  { label: "At least 12 characters", test: (value: string) => value.length >= 12 },
  { label: "One uppercase letter", test: (value: string) => /[A-Z]/.test(value) },
  { label: "One lowercase letter", test: (value: string) => /[a-z]/.test(value) },
  { label: "One number", test: (value: string) => /[0-9]/.test(value) },
  { label: "One special character", test: (value: string) => /[^A-Za-z0-9\s]/.test(value) },
  { label: "No spaces or whitespace", test: (value: string) => !/\s/.test(value) },
];

export default function ResetPassword() {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const token = search.get("token") ?? "";
  const submittingRef = useRef(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const satisfied = useMemo(() => rules.map((rule) => rule.test(password)), [password]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current) return;
    if (token.length < 32) { setError("This password reset link is invalid or incomplete."); return; }
    if (satisfied.some((value) => !value)) { setError("Meet every password requirement below."); return; }
    if (password !== confirmPassword) { setError("Passwords do not match."); return; }
    submittingRef.current = true;
    setSubmitting(true);
    setError("");
    try {
      await confirmPasswordReset(token, password);
      navigate("/login", { replace: true, state: { passwordReset: true } });
    } catch {
      setError("This password reset link is invalid or expired. Request a new one.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  const count = satisfied.filter(Boolean).length;
  const strength = !password ? "Not set" : count <= 2 ? "Weak" : count < rules.length ? "Medium" : "Strong";

  return <div className="auth-page"><div className="auth-card auth-card-wide">
    <div className="auth-logo"><div className="brand-icon"><Plane size={20} /></div><strong>AEROVISION</strong></div>
    <h1>Choose a new password</h1><p>Your reset link expires after 30 minutes and can be used once.</p>
    {error && <div className="auth-alert auth-error" role="alert">{error}</div>}
    <form onSubmit={(event) => void submit(event)} noValidate>
      <label className="auth-field-label" htmlFor="new-password">New password</label>
      <div className="auth-password-wrap"><input id="new-password" className="auth-input" type={showPassword ? "text" : "password"} autoComplete="new-password" maxLength={256} required value={password} onChange={(event) => setPassword(event.currentTarget.value)} /><button className="auth-password-toggle" type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((shown) => !shown)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
      <div className="password-strength-row" aria-live="polite">Password strength: <strong className={`strength-${strength.toLowerCase().replaceAll(" ", "-")}`}>{strength}</strong></div>
      <ul className="password-requirements" aria-label="Password requirements">{rules.map((rule, index) => <li key={rule.label} className={satisfied[index] ? "requirement-met" : "requirement-unmet"}>{satisfied[index] ? <Check size={14} aria-hidden="true" /> : <X size={14} aria-hidden="true" />}<span>{rule.label}</span></li>)}</ul>
      <label className="auth-field-label" htmlFor="confirm-new-password">Confirm new password</label>
      <input id="confirm-new-password" className="auth-input" type={showPassword ? "text" : "password"} autoComplete="new-password" maxLength={256} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.currentTarget.value)} />
      <button type="submit" className="primary-button auth-button" disabled={submitting}>{submitting ? <><span className="auth-spinner" aria-hidden="true" /> Updating…</> : "Update password"}</button>
    </form>
    <div className="auth-footer"><Link to="/login">Back to sign in</Link></div>
  </div></div>;
}
