import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { AuthProvider } from "../src/contexts/AuthContext";
import Login from "../src/pages/Login";
import Signup from "../src/pages/Signup";
import ForgotPassword from "../src/pages/ForgotPassword";
import ResetPassword from "../src/pages/ResetPassword";
import { confirmPasswordReset, getCurrentUser, registerAccount, requestPasswordReset, signIn } from "../src/services/api";

vi.mock("../src/services/api", () => ({
  API_BASE_URL: "http://127.0.0.1:8000",
  getCurrentUser: vi.fn(),
  registerAccount: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
  confirmPasswordReset: vi.fn(),
  requestPasswordReset: vi.fn(),
}));

const account = { id: 4, full_name: "Siddhika Rao", email: "siddhika@gmail.com" };

function renderAuth(path: string, routes?: ReactNode) {
  return render(<MemoryRouter initialEntries={[path]}><AuthProvider><Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/signup" element={<Signup />} />
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/dashboard" element={<div>Authenticated dashboard</div>} />
    {routes}
  </Routes></AuthProvider></MemoryRouter>);
}

describe("authentication pages", () => {
  beforeEach(() => {
    vi.mocked(getCurrentUser).mockRejectedValue(new Error("not signed in"));
    vi.mocked(registerAccount).mockResolvedValue({ user: account, message: "Account created" });
    vi.mocked(signIn).mockResolvedValue({ user: account, expires_in: 1800 });
    vi.mocked(requestPasswordReset).mockResolvedValue({ message: "Request processed", email_delivery_configured: false });
    vi.mocked(confirmPasswordReset).mockResolvedValue({ message: "Password updated" });
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("validates required fields, strict email format, password policy, and matching confirmation", async () => {
    renderAuth("/signup");
    await screen.findByLabelText("Full name");
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Siddhika" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "siddhikagmail.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Enter a valid email address with a complete domain.")).toBeTruthy();
    expect(screen.getByText("Meet every password requirement below.")).toBeTruthy();
    expect(screen.getByText("Passwords do not match.")).toBeTruthy();
    expect(registerAccount).not.toHaveBeenCalled();
  });

  it("updates password requirements and shows a strength category", async () => {
    renderAuth("/signup");
    const password = await screen.findByLabelText("Password");
    fireEvent.change(password, { target: { value: "SecurePassword9!" } });
    expect(screen.getByText("Strong")).toBeTruthy();
    expect(screen.getAllByText("One uppercase letter").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Password requirements").textContent).toContain("No spaces or whitespace");
  });

  it("registers a normalized account and redirects to sign in with a success notice", async () => {
    renderAuth("/signup");
    fireEvent.change(await screen.findByLabelText("Full name"), { target: { value: "  Siddhika Rao " } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: " SIDDHIKA@GMAIL.COM " } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "SecurePassword9!" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "SecurePassword9!" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Your account is ready. Sign in to continue.")).toBeTruthy();
    expect(registerAccount).toHaveBeenCalledWith({ full_name: "Siddhika Rao", email: "siddhika@gmail.com", password: "SecurePassword9!" });
  });

  it("shows a generic sign-in failure and supports password visibility", async () => {
    vi.mocked(signIn).mockRejectedValueOnce(new Error("private internal details"));
    renderAuth("/login");
    const password = await screen.findByLabelText("Password");
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "siddhika@gmail.com" } });
    fireEvent.change(password, { target: { value: "legacy password" } });
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect((password as HTMLInputElement).type).toBe("text");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Invalid email or password.")).toBeTruthy();
    expect(screen.queryByText("private internal details")).toBeNull();
  });

  it("redirects an authenticated user to the dashboard after login", async () => {
    renderAuth("/login");
    fireEvent.change(await screen.findByLabelText("Email address"), { target: { value: "siddhika@gmail.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "existing legacy password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Authenticated dashboard")).toBeTruthy();
    expect(signIn).toHaveBeenCalledWith("siddhika@gmail.com", "existing legacy password");
  });

  it("explains when SMTP reset delivery is unavailable", async () => {
    renderAuth("/forgot-password");
    fireEvent.change(await screen.findByLabelText("Email address"), { target: { value: "siddhika@gmail.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset instructions" }));
    expect(await screen.findByText(/SMTP is not configured, so no email was sent/)).toBeTruthy();
  });

  it("validates a reset password before consuming a token", async () => {
    render(<MemoryRouter initialEntries={["/reset-password?token=abcdefabcdefabcdefabcdefabcdefabcdef"]}><ResetPassword /></MemoryRouter>);
    fireEvent.change(await screen.findByLabelText("New password"), { target: { value: "weak" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "weak" } });
    fireEvent.click(screen.getByRole("button", { name: "Update password" }));
    await waitFor(() => expect(confirmPasswordReset).not.toHaveBeenCalled());
    expect(screen.getByText("Meet every password requirement below.")).toBeTruthy();
  });
});
