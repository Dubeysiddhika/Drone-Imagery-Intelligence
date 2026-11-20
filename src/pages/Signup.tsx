import { FormEvent, useMemo, useRef, useState } from "react";
import { Check, Eye, EyeOff, Plane, X } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

const passwordRules = [
  { label: "At least 12 characters", test: (value: string) => value.length >= 12 },
  { label: "One uppercase letter", test: (value: string) => /[A-Z]/.test(value) },
  { label: "One lowercase letter", test: (value: string) => /[a-z]/.test(value) },
  { label: "One number", test: (value: string) => /[0-9]/.test(value) },
  { label: "One special character", test: (value: string) => /[^A-Za-z0-9\s]/.test(value) },
  { label: "No spaces or whitespace", test: (value: string) => !/\s/.test(value) },
];
const emailPattern = /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;

export default function Signup() {
  const { user, loading: authLoading, register } = useAuth();
  const navigate = useNavigate();
  const submittingRef = useRef(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPasswords, setShowPasswords] = useState(false);
  const [errors, setErrors] = useState<{ fullName?: string; email?: string; password?: string; confirmPassword?: string }>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const satisfiedRules = useMemo(() => passwordRules.map((rule) => rule.test(password)), [password]);
  const strengthCount = satisfiedRules.filter(Boolean).length;
  const strength = !password ? "" : strengthCount <= 2 ? "Weak" : strengthCount < passwordRules.length ? "Medium" : "Strong";

  if (authLoading) return <div className="auth-page"><div className="auth-card" role="status">Checking your secure session…</div></div>;
  if (user) return <Navigate to="/dashboard" replace />;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current) return;
    const nextErrors: typeof errors = {};
    if (!fullName.trim()) nextErrors.fullName = "Full name is required.";
    if (!email.trim()) nextErrors.email = "Email is required.";
    else if (!emailPattern.test(email.trim())) nextErrors.email = "Enter a valid email address with a complete domain.";
    if (!password) nextErrors.password = "Password is required.";
    else if (satisfiedRules.some((satisfied) => !satisfied)) nextErrors.password = "Meet every password requirement below.";
    if (!confirmPassword) nextErrors.confirmPassword = "Please confirm your password.";
    else if (confirmPassword !== password) nextErrors.confirmPassword = "Passwords do not match.";
    setErrors(nextErrors);
    setFormError("");
    if (Object.keys(nextErrors).length) return;

    submittingRef.current = true;
    setSubmitting(true);
    try {
      await register({ full_name: fullName.trim(), email: email.trim().toLowerCase(), password });
      navigate("/login", { replace: true, state: { registered: true } });
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      if (status === 409) setErrors({ email: "An account with this email already exists." });
      else setFormError("We couldn’t create your account. Check your details and try again.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card auth-card-wide">
        <div className="auth-logo"><div className="brand-icon"><Plane size={20} /></div><strong>AEROVISION</strong></div>
        <h1>Create your workspace</h1>
        <p>Start turning aerial imagery into intelligence.</p>
        {formError && <div className="auth-alert auth-error" role="alert">{formError}</div>}
        <form onSubmit={(event) => void submit(event)} noValidate>
          <label className="auth-field-label" htmlFor="signup-name">Full name</label>
          <input id="signup-name" className="auth-input" autoComplete="name" required maxLength={120} value={fullName} aria-invalid={Boolean(errors.fullName)} aria-describedby={errors.fullName ? "signup-name-error" : undefined} onChange={(event) => setFullName(event.currentTarget.value)} />
          {errors.fullName && <span className="auth-field-error" id="signup-name-error">{errors.fullName}</span>}

          <label className="auth-field-label" htmlFor="signup-email">Email address</label>
          <input id="signup-email" className="auth-input" type="email" autoComplete="email" inputMode="email" required value={email} aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "signup-email-error" : undefined} onChange={(event) => setEmail(event.currentTarget.value)} />
          {errors.email && <span className="auth-field-error" id="signup-email-error">{errors.email}</span>}

          <label className="auth-field-label" htmlFor="signup-password">Password</label>
          <div className="auth-password-wrap">
            <input id="signup-password" className="auth-input" type={showPasswords ? "text" : "password"} autoComplete="new-password" required maxLength={256} value={password} aria-invalid={Boolean(errors.password)} aria-describedby="password-requirements" onChange={(event) => setPassword(event.currentTarget.value)} />
            <button className="auth-password-toggle" type="button" aria-label={showPasswords ? "Hide passwords" : "Show passwords"} onClick={() => setShowPasswords((shown) => !shown)}>{showPasswords ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </div>
          <div className="password-strength-row" aria-live="polite">Password strength: <strong className={`strength-${strength.toLowerCase() || "empty"}`}>{strength || "Not set"}</strong></div>
          <ul className="password-requirements" id="password-requirements" aria-label="Password requirements">
            {passwordRules.map((rule, index) => <li key={rule.label} className={satisfiedRules[index] ? "requirement-met" : "requirement-unmet"}>{satisfiedRules[index] ? <Check size={14} aria-hidden="true" /> : <X size={14} aria-hidden="true" />}<span>{rule.label}</span></li>)}
          </ul>
          {errors.password && <span className="auth-field-error">{errors.password}</span>}

          <label className="auth-field-label" htmlFor="signup-confirm">Confirm password</label>
          <input id="signup-confirm" className="auth-input" type={showPasswords ? "text" : "password"} autoComplete="new-password" required maxLength={256} value={confirmPassword} aria-invalid={Boolean(errors.confirmPassword)} aria-describedby={errors.confirmPassword ? "signup-confirm-error" : undefined} onChange={(event) => setConfirmPassword(event.currentTarget.value)} />
          {errors.confirmPassword && <span className="auth-field-error" id="signup-confirm-error">{errors.confirmPassword}</span>}

          <button type="submit" className="primary-button auth-button" disabled={submitting}>
            {submitting ? <><span className="auth-spinner" aria-hidden="true" /> Creating account…</> : "Create account"}
          </button>
        </form>
        <div className="auth-footer">Already have an account? <Link to="/login">Sign in</Link></div>
      </div>
    </div>
  );
}
