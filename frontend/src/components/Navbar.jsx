import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Droplet, Activity, ShieldCheck, HeartHandshake, Building2, Smartphone, Heart, Sparkles, Wifi, WifiOff, Bell, LogIn, LogOut, User, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { requestFirebaseNotificationPermission } from '../firebase';
import { registerDeviceToken } from '../services/api';

const isSimulatorEnabled = import.meta.env.VITE_APP_ENV !== 'production';

export default function Navbar({ activeTab, setActiveTab, activeRequest, onOpenDonorPortal }) {
  const { user, hasDonorProfile, logout, setShowAuthModal } = useAuth();
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [notifications, setNotifications] = useState(0);
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);

  useEffect(() => {
    if (activeRequest) setNotifications(prev => prev + 1);
  }, [activeRequest]);

  useEffect(() => {
    if (!user) return;

  }, [user]);

  const handleEnableNotifications = async () => {
    try {
      const token = await requestFirebaseNotificationPermission();
      if (token) {
        await registerDeviceToken(token);
        console.log('[Navbar] Push notifications enabled successfully');
      } else {
        console.warn('[Navbar] Notification permission denied or not supported on this device.');
      }
    } catch (err) {
      console.error('[Navbar] Failed to enable notifications:', err);
    } finally {
      setShowUserMenu(false);
    }
  };

  // Close user menu on outside click
  useEffect(() => {
    if (!showUserMenu) return;
    const handleClick = () => setShowUserMenu(false);
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [showUserMenu]);

  const desktopTabs = [
    { id: 'home', label: 'Action Hub', icon: <Sparkles className="w-3.5 h-3.5" /> },
    { id: 'request', label: 'Emergency', icon: <Activity className="w-3.5 h-3.5" /> },
    { id: 'tracker', label: 'Live Dashboard', icon: <HeartHandshake className="w-3.5 h-3.5" />, badge: !!activeRequest },
    { id: 'donor-portal', label: 'Donor Hub', icon: <Heart className="w-3.5 h-3.5" /> },
    { id: 'banks', label: 'Blood Banks', icon: <Building2 className="w-3.5 h-3.5" /> },
    { id: 'audit', label: 'Audit Log', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
  ];

  const userInitials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : '??';

  return (
    <>
      {/* Donor Registration Banner */}
      {user && !hasDonorProfile && (
        <div className="bg-gradient-to-r from-blood-600/20 via-blood-500/10 to-transparent border-b border-blood-500/20 px-4 py-2.5">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 text-xs">
              <span className="px-2 py-0.5 rounded-md bg-blood-500/20 text-blood-400 font-bold text-[10px] tracking-wider animate-pulse">ACTION NEEDED</span>
              <span className="text-[#A1A1A6]">Complete your <strong className="text-white">Donor Registration</strong> to be matched with nearby emergency requests.</span>
            </div>
            <button
              onClick={() => setActiveTab('donor-portal')}
              className="shrink-0 px-4 py-1.5 text-[10px] font-bold rounded-full bg-blood-500 text-white hover:bg-blood-600 transition-colors tracking-wider"
            >
              REGISTER NOW
            </button>
          </div>
        </div>
      )}

      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="sticky top-0 z-50 bg-[#050505]/60 backdrop-blur-2xl border-b border-white/5"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-4">

            {/* Logo & Title */}
            <div
              className="flex items-center gap-3 cursor-pointer shrink-0 group"
              onClick={() => setActiveTab('home')}
            >
              <div className="w-8 h-8 rounded-full bg-blood-500/10 flex items-center justify-center border border-blood-500/20 group-hover:bg-blood-500/20 transition-colors">
                <Droplet className="w-4 h-4 text-blood-500" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-base text-[#F5F5F7] tracking-tight">
                    LifePulse
                  </span>
                  <span className="hidden sm:inline-block px-1.5 py-0.5 text-[9px] font-bold rounded-sm bg-blood-500/10 text-blood-500 tracking-wider">
                    LIVE
                  </span>
                </div>
              </div>
            </div>

            {/* Desktop Navigation Tabs */}
            <nav className="hidden lg:flex items-center gap-1 bg-[#111111]/50 p-1 rounded-full border border-white/5">
              {desktopTabs.map((tab) => {
                const toPath = tab.id === 'home' ? '/' : `/${tab.id}`;
                return (
                  <Link
                    key={tab.id}
                    to={toPath}
                    className={`relative flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold transition-all duration-300 ${
                      activeTab === tab.id
                        ? 'bg-white/10 text-white'
                        : 'text-[#86868B] hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {activeTab === tab.id && (
                      <motion.div
                        layoutId="activeTabIndicator"
                        className="absolute inset-0 bg-white/10 rounded-full"
                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                      />
                    )}
                    <span className="relative z-10 flex items-center gap-2">
                      <span className={activeTab === tab.id ? 'text-blood-500' : 'opacity-70'}>{tab.icon}</span>
                      {tab.label}
                    </span>
                    {tab.badge && (
                      <span className="w-1.5 h-1.5 rounded-full bg-blood-500 absolute top-2 right-2 shadow-[0_0_8px_rgba(229,9,20,0.8)] animate-pulse" />
                    )}
                  </Link>
                );
              })}
            </nav>

            {/* Right Action Buttons */}
            <div className="flex items-center gap-3 shrink-0">
              {/* Connection Status */}
              <div className="hidden xl:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-bold bg-[#111111] border border-white/5">
                {isOnline ? (
                  <><Wifi className="w-3 h-3 text-emerald-500" /><span className="text-[#86868B]">Connected</span></>
                ) : (
                  <><WifiOff className="w-3 h-3 text-blood-500" /><span className="text-blood-500">Offline</span></>
                )}
              </div>

              {/* Notification Bell */}
              <button
                onClick={() => { setNotifications(0); setActiveTab('tracker'); }}
                className="relative p-2 rounded-full text-[#86868B] hover:text-white hover:bg-white/5 transition-colors"
              >
                <Bell className="w-4 h-4" />
                {notifications > 0 && (
                  <span className="absolute top-1 right-1 w-2 h-2 bg-blood-500 rounded-full animate-bounce" />
                )}
              </button>

              {/* Simulate Donor Button */}
              {isSimulatorEnabled && (
                <button
                  onClick={onOpenDonorPortal}
                  className="hidden sm:flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-full bg-blood-500 text-white hover:bg-blood-600 transition-colors hover-lift"
                >
                  <Smartphone className="w-3.5 h-3.5" />
                  <span>Simulate Donor</span>
                </button>
              )}

              {/* Auth: User Profile or Login Button */}
              {user ? (
                <div className="relative">
                  <button
                    onClick={(e) => { e.stopPropagation(); setShowUserMenu(!showUserMenu); }}
                    className="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full bg-[#111111] border border-white/10 hover:border-white/20 transition-colors"
                  >
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blood-500 to-blood-700 flex items-center justify-center text-[10px] font-bold text-white">
                      {userInitials}
                    </div>
                    <span className="hidden sm:inline text-xs text-[#A1A1A6] font-medium max-w-[100px] truncate">
                      {user.full_name?.split(' ')[0]}
                    </span>
                    <ChevronDown className="w-3 h-3 text-[#86868B]" />
                  </button>

                  <AnimatePresence>
                    {showUserMenu && (
                      <motion.div
                        initial={{ opacity: 0, y: 8, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 8, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-12 w-56 rounded-xl bg-[#1C1C1E] border border-white/10 shadow-2xl overflow-hidden z-50"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="px-4 py-3 border-b border-white/5">
                          <p className="text-xs font-bold text-white truncate">{user.full_name}</p>
                          <p className="text-[10px] text-[#86868B] truncate">{user.email}</p>
                        </div>
                        <div className="px-2 py-2 space-y-0.5">
                          <button
                            onClick={() => { setActiveTab('donor-portal'); setShowUserMenu(false); }}
                            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs text-[#A1A1A6] hover:text-white hover:bg-white/5 transition-colors"
                          >
                            <Heart className="w-3.5 h-3.5" />
                            {hasDonorProfile ? 'My Donor Profile' : 'Register as Donor'}
                          </button>
                          <button
                            onClick={handleEnableNotifications}
                            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs text-[#A1A1A6] hover:text-white hover:bg-white/5 transition-colors"
                          >
                            <Bell className="w-3.5 h-3.5" />
                            Enable Notifications
                          </button>
                          <button
                            onClick={() => { logout(); setShowUserMenu(false); }}
                            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs text-blood-400 hover:text-blood-300 hover:bg-blood-500/10 transition-colors"
                          >
                            <LogOut className="w-3.5 h-3.5" />
                            Sign Out
                          </button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              ) : (
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-full bg-white/5 text-[#A1A1A6] border border-white/10 hover:bg-white/10 hover:text-white transition-colors"
                >
                  <LogIn className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Login</span>
                </button>
              )}
            </div>

          </div>
        </div>
      </motion.header>
    </>
  );
}
