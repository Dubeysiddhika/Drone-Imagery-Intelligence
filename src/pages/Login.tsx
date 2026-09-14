import { Plane, ArrowRight } from "lucide-react";

export default function Login() {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="brand-icon">
            <Plane size={20} />
          </div>

          <strong>AEROVISION</strong>
        </div>

        <h1>Welcome back</h1>

        <p>Sign in to your intelligence workspace.</p>

        <input className="auth-input" placeholder="Email address" />

        <input
          className="auth-input"
          type="password"
          placeholder="Password"
        />

        <a href="/dashboard" className="primary-button auth-button">
          Sign in
          <ArrowRight size={15} />
        </a>

        <div className="auth-footer">
          Don't have an account?
          <a href="/signup"> Create one</a>
        </div>
      </div>
    </div>
  );
}