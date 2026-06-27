"use client";

import React, { useState } from "react";
import { Mail, Lock, Eye, EyeOff, Loader2 } from "lucide-react";
import Image from "next/image";
import { useAppDispatch, useAppSelector } from "@/redux/hooks";
import { loginUser, clearError } from "@/redux/slices/authSlice";

interface LoginFormProps {
  onLoginSuccess: () => void;
}

export function LoginForm({ onLoginSuccess }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [validationError, setValidationError] = useState("");

  const dispatch = useAppDispatch();
  const { isLoading, error } = useAppSelector((state) => state.auth);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError("");
    dispatch(clearError());

    if (!email.includes("@")) {
      setValidationError("Please enter a valid email address.");
      return;
    }
    if (password.length < 4) {
      setValidationError("Password must be at least 4 characters.");
      return;
    }

    const resultAction = await dispatch(loginUser({ email, password }));
    if (loginUser.fulfilled.match(resultAction)) {
      onLoginSuccess();
    }
  };

  const displayedError = validationError || (
    typeof error === "object" && error !== null
      ? (error as any).message || (error as any).error || JSON.stringify(error)
      : error
  );

  return (
    <section className="bg-[#020918]">
      <div className="flex min-h-screen max-w-[1440px] mx-auto bg-[#020918] text-white font-sans overflow-hidden">

      {/* ── Left Panel ─────────────────────────────────────────────────────── */}
      <div className="relative hidden lg:flex w-[50%] flex-col justify-between p-12 bg-[#030c1a] border-r border-slate-900/60 overflow-hidden">

        <div className="absolute inset-0 z-0 opacity-40">
          <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <radialGradient id="mesh-glow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#030914" stopOpacity="0" />
              </radialGradient>
            </defs>
            {/* Soft background glow */}
            <circle cx="30%" cy="60%" r="350" fill="url(#mesh-glow)" />
            
            {/* Connecting lines */}
            <line x1="5%" y1="15%" x2="15%" y2="30%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="15%" y1="30%" x2="10%" y2="50%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="10%" y1="50%" x2="25%" y2="45%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="25%" y1="45%" x2="20%" y2="65%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="20%" y1="65%" x2="35%" y2="70%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="35%" y1="70%" x2="50%" y2="60%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="50%" y1="60%" x2="60%" y2="40%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="60%" y1="40%" x2="70%" y2="30%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="70%" y1="30%" x2="55%" y2="20%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="55%" y1="20%" x2="40%" y2="15%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="40%" y1="15%" x2="25%" y2="25%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="25%" y1="25%" x2="15%" y2="30%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            
            {/* Cross-connections */}
            <line x1="15%" y1="30%" x2="35%" y2="70%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1.2" />
            <line x1="40%" y1="15%" x2="50%" y2="60%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1.2" />
            <line x1="20%" y1="65%" x2="40%" y2="15%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1.2" />
            <line x1="5%" y1="15%" x2="40%" y2="15%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1.2" />
            
            {/* Additional nodes & lines bottom area */}
            <line x1="20%" y1="65%" x2="15%" y2="85%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="15%" y1="85%" x2="30%" y2="88%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="30%" y1="88%" x2="35%" y2="70%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="30%" y1="88%" x2="50%" y2="85%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="50%" y1="85%" x2="50%" y2="60%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="50%" y1="85%" x2="70%" y2="80%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            <line x1="70%" y1="80%" x2="60%" y2="40%" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" />
            
            {/* New connecting lines - top area */}
            <line x1="5%" y1="15%" x2="55%" y2="20%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="5%" y1="15%" x2="70%" y2="30%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="15%" y1="30%" x2="50%" y2="60%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="25%" y1="25%" x2="60%" y2="40%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            
            {/* Middle dense network */}
            <line x1="10%" y1="50%" x2="50%" y2="60%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="10%" y1="50%" x2="30%" y2="88%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="25%" y1="45%" x2="50%" y2="85%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="35%" y1="70%" x2="15%" y2="85%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="50%" y1="60%" x2="30%" y2="88%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="55%" y1="20%" x2="70%" y2="80%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            
            {/* Bottom web connections */}
            <line x1="15%" y1="85%" x2="50%" y2="60%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="15%" y1="85%" x2="40%" y2="15%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="30%" y1="88%" x2="20%" y2="65%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="50%" y1="85%" x2="70%" y2="30%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            <line x1="70%" y1="80%" x2="35%" y2="70%" stroke="#10b981" strokeOpacity="0.35" strokeWidth="1.2" />
            
            {/* Extra cross links */}
            <line x1="40%" y1="15%" x2="35%" y2="70%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="60%" y1="40%" x2="35%" y2="70%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="5%" y1="15%" x2="20%" y2="65%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="5%" y1="15%" x2="15%" y2="85%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="25%" y1="45%" x2="15%" y2="85%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="10%" y1="50%" x2="55%" y2="20%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="70%" y1="30%" x2="30%" y2="88%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            <line x1="50%" y1="60%" x2="70%" y2="80%" stroke="#10b981" strokeOpacity="0.3" strokeWidth="1" />
            
            {/* Glowing nodes (Circles) - Original + New */}
            <circle cx="5%" cy="15%" r="3" fill="#10b981" />
            <circle cx="15%" cy="30%" r="4" fill="#10b981" />
            <circle cx="10%" cy="50%" r="3.5" fill="#10b981" />
            <circle cx="25%" cy="45%" r="3" fill="#10b981" />
            <circle cx="20%" cy="65%" r="4" fill="#10b981" />
            <circle cx="40%" cy="15%" r="3.5" fill="#10b981" />
            <circle cx="55%" cy="20%" r="3" fill="#10b981" />
            <circle cx="70%" cy="30%" r="4" fill="#10b981" />
            <circle cx="60%" cy="40%" r="3.5" fill="#10b981" />
            <circle cx="50%" cy="60%" r="4" fill="#10b981" />
            <circle cx="35%" cy="70%" r="4.5" fill="#10b981" />
            <circle cx="25%" cy="25%" r="3" fill="#10b981" />
            <circle cx="15%" cy="85%" r="3.5" fill="#10b981" />
            <circle cx="30%" cy="88%" r="3" fill="#10b981" />
            <circle cx="50%" cy="85%" r="4" fill="#10b981" />
            <circle cx="70%" cy="80%" r="3.5" fill="#10b981" />
          </svg>
        </div>

        {/* ── Logo ── */}
        <div className="relative z-10">
          {/* <div className="flex items-center gap-1 leading-none select-none">
            <span className="text-2xl font-extrabold tracking-tight">
              <span className="text-[#facc15]">Q</span>
              <span className="text-[#00bcd4]">2</span>
            </span>
            <span className="text-xl font-semibold text-slate-200 tracking-tight ml-0.5">LABS</span>
          </div> */}
          <img src="./Q2image.svg" alt="Q2labs" className="h-24" />
          {/* <p className="mt-1 text-[11px] font-medium text-slate-500 tracking-widest uppercase ml-0.5">AI Research Platform</p> */}
        </div>

        {/* ── Main headline ── */}
        <div className="relative z-10 my-auto max-w-xl">
          <h1 className="text-[40px] font-medium tracking-tight leading-[1.15] text-white">
            AI-Powered Research{" "}
            <br /> 
            Workspace for{" "}
            <span className="text-yellow-400 italic font-semibold">Modern Pharma Teams</span>
          </h1>

          <p className="mt-5 text-slate-400 text-[15px] leading-relaxed max-w-[440px]">
            Analyse datasets, run experiments, collaborate with researchers, and generate scientific insights — all from one secure platform.
          </p>

          {/* Checklist */}
          <div className="mt-10 flex flex-col gap-4">
            {[
              "Clinical Data Analysis",
              "AI-Powered Experimentation",
              "Research Notebook Workspace",
              "Team Collaboration",
              "Enterprise Security",
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3.5">
                <div className="h-5 w-5 rounded-full bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center flex-shrink-0">
                  <svg className="h-3 w-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="text-slate-200 text-[14.5px] font-medium">{item}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Bottom stats ── */}
        <div className="relative z-10 grid grid-cols-3 gap-6 pt-8 border-t border-slate-900/50 max-w-lg">
          {[
            { num: "500+", label: "Research Projects" },
            { num: "50+", label: "Organizations" },
            { num: "99.9%", label: "Availability" },
          ].map(({ num, label }) => (
            <div key={label}>
              <div className="text-2xl font-bold text-white tracking-tight">{num}</div>
              <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mt-1">{label}</div>
            </div>
          ))}
        </div>
      </div>
      {/* ── Right Panel: Sign-in form ──────────────────────────────────────── */}
      <div className="relative flex flex-1 flex-col justify-center px-8 py-12 lg:px-16 xl:px-20 bg-[#020918] min-h-screen">
        {/* Background Image */}
        <Image 
          src="/Q2bg.svg" 
          alt="Background" 
          width={500}
          height={500} 
          className="absolute inset-0 w-full h-full object-cover pointer-events-none z-0"
        /> 
        {/* Soft glow */}
        {/* <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-blue-500/[0.04] rounded-full blur-[90px] pointer-events-none" /> */}
 
        <div className="relative z-10 mx-auto w-full max-w-[380px] flex flex-col gap-7">

          {/* Mobile logo */}
          {/* <div className="lg:hidden">
            <span className="text-2xl font-extrabold">
              <span className="text-[#facc15]">Q</span>
              <span className="text-[#00bcd4]">2</span>
            </span>
            <span className="text-xl font-semibold text-slate-200 ml-1">LABS</span>
          </div> */}

          {/* Header */}
          <div>
            <h2 className="text-[28px] font-bold tracking-tight text-white">Welcome back</h2>
            <p className="mt-1.5 text-sm text-slate-400">Sign in to access your research workspace.</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Error */}
            {displayedError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p className="text-red-400 text-sm font-medium">{displayedError}</p>
              </div>
            )}

            {/* Email */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="text-[12px] font-medium text-slate-400">Email Address</label>
              <div className={`relative flex items-center bg-[#060d1c] border rounded-xl transition-all ${
                email ? "border-slate-700" : "border-slate-800"
              } focus-within:border-[#00B686] focus-within:shadow-[0_0_0_3px_rgba(0,182,134,0.08)]`}>
                <Mail className="absolute left-3.5 h-[17px] w-[17px] text-slate-500 pointer-events-none" />
                <input
                  id="email"
                  type="email"
                  required
                  placeholder="Enter your work email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  className="w-full bg-transparent py-3 pl-10 pr-4 text-[13.5px] text-white placeholder:text-slate-600 outline-none"
                />
              </div>
            </div>

            {/* Password */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="text-[12px] font-medium text-slate-400">Password</label>
                {/* <button type="button" className="text-[11px] font-semibold text-yellow-500 hover:text-yellow-400 transition-colors">
                  Forgot Password?
                </button> */}
              </div>
              <div className={`relative flex items-center bg-[#060d1c] border rounded-xl transition-all ${
                password ? "border-slate-700" : "border-slate-800"
              } focus-within:border-[#00B686] focus-within:shadow-[0_0_0_3px_rgba(0,182,134,0.08)]`}>
                <Lock className="absolute left-3.5 h-[17px] w-[17px] text-slate-500 pointer-events-none" />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  className="w-full bg-transparent py-3 pl-10 pr-10 text-[13.5px] text-white placeholder:text-slate-600 outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isLoading}
                  className="absolute right-3.5 text-slate-500 hover:text-slate-300 transition-colors outline-none"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-[17px] w-[17px]" /> : <Eye className="h-[17px] w-[17px]" />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-1 py-3 rounded-xl bg-[#00B686] hover:bg-[#00a377] active:bg-[#00956b] text-white font-semibold text-[14px] tracking-wide transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/20 cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : "Sign In"}
            </button>
          </form>

          {/* Divider */}
           {/* <div className="flex items-center gap-4">
            <div className="flex-1 h-px bg-slate-900" />
            <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-widest">or</span>
            <div className="flex-1 h-px bg-slate-900" />
          </div>  */}

          {/* Google */}
          {/* <button
            type="button"
            className="w-full flex items-center justify-center gap-2.5 py-3 rounded-xl border border-slate-800 bg-[#040d1c] hover:bg-slate-900/60 hover:border-slate-700 text-[13.5px] font-medium text-white transition-all cursor-pointer"
            onClick={() => alert("Google login clicked!")}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="17" height="17" aria-hidden>
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button> */}

          {/* Sign up link */}
          {/* <p className="text-center text-[12.5px] text-slate-500">
            Don&apos;t have an account?{" "}
            <button type="button" className="text-[#00B686] font-semibold hover:text-emerald-400 transition-colors cursor-pointer">
              Sign Up
            </button>
          </p> */}

        </div>
      </div>
    </div>
    </section>
    
  );
}

export default LoginForm;
