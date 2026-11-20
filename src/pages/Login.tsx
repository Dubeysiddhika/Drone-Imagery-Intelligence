import { FormEvent, useRef, useState } from "react";
import { ArrowRight, Eye, EyeOff, Plane } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";
function validEmail(value: string): boolean {
  return /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i.test(value.trim());
}

export default function Login() {
  const { user, loading: authLoading, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const submittingRef = useRef(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const registered = Boolean((location.state as { registered?: boolean } | null)?.registered);
  const passwordReset = Boolean((location.state as { passwordReset?: boolean } | null)?.passwordReset);
  const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/dashboard";

  if (authLoading) return <div className="auth-page"><div className="auth-card" role="status">Checking your secure session…</div></div>;
  if (user) return <Navigate to="/dashboard" replace />;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submittingRef.current) return;
    const nextErrors: typeof errors = {};
    if (!email.trim()) nextErrors.email = "Email is required.";
    else if (!validEmail(email)) nextErrors.email = "Enter a valid email address.";
    if (!password) nextErrors.password = "Password is required.";
    setErrors(nextErrors);
    setFormError("");
    if (Object.keys(nextErrors).length) return;

    submittingRef.current = true;
    setSubmitting(true);
    try {
      await signIn(email.trim().toLowerCase(), password);
      navigate(destination, { replace: true });
    } catch {
      setFormError("Invalid email or password.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo"><div className="brand-icon"><Plane size={20} /></div><strong>AEROVISION</strong></div>
        <h1>Welcome back</h1>
        <p>Sign in to your intelligence workspace.</p>
        {registered && <div className="auth-alert auth-success" role="status">Your account is ready. Sign in to continue.</div>}
        {passwordReset && <div className="auth-alert auth-success" role="status">Password updated successfully. Sign in with your new password.</div>}
        {formError && <div className="auth-alert auth-error" role="alert">{formError}</div>}
        <form onSubmit={(event) => void submit(event)} noValidate>
          <label className="auth-field-label" htmlFor="login-email">Email address</label>
          <input id="login-email" className="auth-input" type="email" autoComplete="email" inputMode="email" required value={email} aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "login-email-error" : undefined} onChange={(event) => setEmail(event.currentTarget.value)} />
          {errors.email && <span className="auth-field-error" id="login-email-error">{errors.email}</span>}
          <label className="auth-field-label" htmlFor="login-password">Password</label>
          <div className="auth-password-wrap">
            <input id="login-password" className="auth-input" type={showPassword ? "text" : "password"} autoComplete="current-password" required value={password} aria-invalid={Boolean(errors.password)} aria-describedby={errors.password ? "login-password-error" : undefined} onChange={(event) => setPassword(event.currentTarget.value)} />
            <button className="auth-password-toggle" type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((shown) => !shown)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </div>
          {errors.password && <span className="auth-field-error" id="login-password-error">{errors.password}</span>}
          <div className="auth-forgot-row"><Link to="/forgot-password">Forgot password?</Link></div>
          <button type="submit" className="primary-button auth-button" disabled={submitting}>
            {submitting ? <><span className="auth-spinner" aria-hidden="true" /> Signing in…</> : <>Sign in <ArrowRight size={15} /> </>}
          </button>
        </form>
        <div className="auth-footer">Don&apos;t have an account? <Link to="/signup">Create one</Link></div>
      </div>
    </div>
  );
}
