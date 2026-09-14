import { Plane } from "lucide-react";

export default function Signup() {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="brand-icon">
            <Plane size={20} />
          </div>

          <strong>AEROVISION</strong>
        </div>

        <h1>Create your workspace</h1>

        <p>Start turning aerial imagery into intelligence.</p>

        <input className="auth-input" placeholder="Full name" />
        <input className="auth-input" placeholder="Email address" />

        <input
          className="auth-input"
          type="password"
          placeholder="Password"
        />

        <a href="/dashboard" className="primary-button auth-button">
          Create Account
        </a>

        <div className="auth-footer">
          Already have an account?
          <a href="/login"> Sign in</a>
        </div>
      </div>
    </div>
  );
}