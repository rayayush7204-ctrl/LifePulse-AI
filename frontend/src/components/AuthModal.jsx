import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Lock, Mail, Phone, User, LogIn, UserPlus, CheckCircle2, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from './NotificationToast';

export default function AuthModal({ isOpen, onClose }) {
  const { login, signup } = useAuth();
  const { addToast } = useToast();
  
  const [tab, setTab] = useState('login'); // 'login' | 'signup'
  const [emailOrMobile, setEmailOrMobile] = useState('');
  const [password, setPassword] = useState('');
  
  const [fullName, setFullName] = useState('');
  const [signupEmail, setSignupEmail] = useState('');
  const [signupMobile, setSignupMobile] = useState('');
  const [signupPassword, setSignupPassword] = useState('');
  const [consent, setConsent] = useState(true);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  
  const isMounted = React.useRef(true);
  
  React.useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);
    try {
      let identifier = emailOrMobile.trim();
      if (!identifier.includes('@')) {
        identifier = identifier.replace(/[\s\-\(\)]/g, '');
      }
      await login({ email_or_mobile: identifier, password });
      if (isMounted.current) {
        addToast({ title: 'Welcome Back!', message: 'Login successful.', type: 'success' });
        onClose();
      }
    } catch (err) {
      if (isMounted.current) setErrorMsg(err.message || 'Invalid email/mobile or password.');
    } finally {
      if (isMounted.current) setIsSubmitting(false);
    }
  };

  const handleSignupSubmit = async (e) => {
    e.preventDefault();
    if (!consent) {
      setErrorMsg('Please accept the terms to create an account.');
      return;
    }
    const cleanMobile = signupMobile.replace(/[\s\-\(\)]/g, '');
    const phoneRegex = /^\+?[1-9]\d{1,14}$/;
    if (!phoneRegex.test(cleanMobile)) {
      setErrorMsg('Please enter a valid international mobile number (e.g., +14155550123).');
      return;
    }
    setErrorMsg(null);
    setIsSubmitting(true);
    try {
      await signup({
        full_name: fullName,
        email: signupEmail.trim(),
        mobile_number: cleanMobile,
        password: signupPassword
      });
      if (isMounted.current) {
        addToast({ title: 'Account Created!', message: 'Welcome to LifePulse AI.', type: 'success' });
        onClose();
      }
    } catch (err) {
      if (isMounted.current) setErrorMsg(err.message || 'Registration failed.');
    } finally {
      if (isMounted.current) setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <motion.div 
        initial={{ opacity: 0 }} 
        animate={{ opacity: 1 }} 
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-[#050505]/90 backdrop-blur-xl" 
      />

      <motion.div
        initial={{ scale: 0.95, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 20 }}
        className="relative z-10 w-full max-w-md bg-[#0A0A0C] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-[0_0_80px_rgba(229,9,20,0.2)] overflow-hidden"
      >
        <button 
          onClick={onClose} 
          className="absolute top-6 right-6 text-[#86868B] hover:text-white p-1 rounded-full transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Tab Switcher */}
        <div className="flex bg-[#111111] p-1 rounded-full border border-white/5 mb-8">
          <button
            onClick={() => { setTab('login'); setErrorMsg(null); }}
            className={`flex-1 py-2.5 rounded-full text-xs font-bold transition-all ${
              tab === 'login' ? 'bg-white text-black shadow' : 'text-[#86868B] hover:text-white'
            }`}
          >
            Log In
          </button>
          <button
            onClick={() => { setTab('signup'); setErrorMsg(null); }}
            className={`flex-1 py-2.5 rounded-full text-xs font-bold transition-all ${
              tab === 'signup' ? 'bg-white text-black shadow' : 'text-[#86868B] hover:text-white'
            }`}
          >
            Create Account
          </button>
        </div>

        {errorMsg && (
          <div className="mb-6 p-3 rounded-2xl bg-blood-500/10 border border-blood-500/20 text-blood-400 text-xs font-bold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {errorMsg}
          </div>
        )}

        <AnimatePresence mode="wait">
          {tab === 'login' ? (
            <motion.form 
              key="login-form" 
              initial={{ opacity: 0, x: -10 }} 
              animate={{ opacity: 1, x: 0 }} 
              exit={{ opacity: 0, x: 10 }}
              onSubmit={handleLoginSubmit} 
              className="space-y-5"
            >
              <div>
                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-widest mb-2">Email or Mobile Number</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
                  <input
                    type="text"
                    required
                    value={emailOrMobile}
                    onChange={(e) => setEmailOrMobile(e.target.value)}
                    placeholder="user@example.com or +14155550123"
                    className="w-full bg-[#111111] text-sm text-white font-medium pl-11 pr-4 py-3.5 rounded-2xl border border-white/10 focus:border-blood-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-widest mb-2">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-[#111111] text-sm text-white font-medium pl-11 pr-4 py-3.5 rounded-2xl border border-white/10 focus:border-blood-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-4 rounded-full bg-blood-500 hover:bg-blood-600 text-white font-black text-sm tracking-widest transition-all shadow-[0_0_30px_rgba(229,9,20,0.4)] disabled:opacity-50 flex justify-center items-center gap-2 hover-lift mt-6"
              >
                {isSubmitting ? 'LOGGING IN...' : <><LogIn className="w-4 h-4" /> LOG IN</>}
              </button>
            </motion.form>
          ) : (
            <motion.form 
              key="signup-form" 
              initial={{ opacity: 0, x: 10 }} 
              animate={{ opacity: 1, x: 0 }} 
              exit={{ opacity: 0, x: -10 }}
              onSubmit={handleSignupSubmit} 
              className="space-y-4"
            >
              <div>
                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-widest mb-1.5">Full Name</label>
                <div className="relative">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Johnson"
                    className="w-full bg-[#111111] text-sm text-white font-medium pl-11 pr-4 py-3 rounded-2xl border border-white/10 focus:border-blood-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-widest mb-1.5">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
                  <input
                    type="email"
                    required
                    value={signupEmail}
                    onChange={(e) => setSignupEmail(e.target.value)}
                    placeholder="alex@example.com"
                    className="w-full bg-[#111111] text-sm text-white font-medium pl-11 pr-4 py-3 rounded-2xl border border-white/10 focus:border-blood-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-widest mb-1.5">Mobile Number</label>
                <div className="relative">
                  <Phone className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
                  <input
                    type="tel"
                    required
                    value={signupMobile}
                    onChange={(e) => setSignupMobile(e.target.value)}
                    placeholder="+1 415 555 0123"
                    className="w-full bg-[#111111] text-sm text-white font-medium pl-11 pr-4 py-3 rounded-2xl border border-white/10 focus:border-blood-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-[#86868B] uppercase tracking-widest mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
                  <input
                    type="password"
                    required
                    value={signupPassword}
                    onChange={(e) => setSignupPassword(e.target.value)}
                    placeholder="At least 6 characters"
                    className="w-full bg-[#111111] text-sm text-white font-medium pl-11 pr-4 py-3 rounded-2xl border border-white/10 focus:border-blood-500 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="consent"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="rounded bg-[#111111] border-white/20 text-blood-500 focus:ring-0"
                />
                <label htmlFor="consent" className="text-[10px] text-[#86868B]">
                  I agree to Emergency Matching Terms & Privacy Policy
                </label>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-4 rounded-full bg-white text-black font-black text-sm tracking-widest transition-all hover:bg-gray-200 disabled:opacity-50 flex justify-center items-center gap-2 hover-lift mt-4"
              >
                {isSubmitting ? 'CREATING ACCOUNT...' : <><UserPlus className="w-4 h-4" /> CREATE ACCOUNT</>}
              </button>
            </motion.form>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
