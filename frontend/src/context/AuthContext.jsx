import React, { createContext, useContext, useState, useEffect } from 'react';
import { signupUser, loginUser, getCurrentUser, logoutUser } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [hasDonorProfile, setHasDonorProfile] = useState(false);
  const [donorProfile, setDonorProfile] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token') || null);
  const [isLoading, setIsLoading] = useState(true);
  const [showAuthModal, setShowAuthModal] = useState(false);

  useEffect(() => {
    if (token) {
      getCurrentUser()
        .then(data => {
          if (data?.user) {
            setUser(data.user);
            setHasDonorProfile(data.has_donor_profile || false);
            setDonorProfile(data.donor_profile || null);
          } else {
            // Token expired or invalid
            handleLogout();
          }
        })
        .catch(() => handleLogout())
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [token]);

  const handleSignup = async (payload) => {
    const res = await signupUser(payload);
    if (res.token) {
      localStorage.setItem('token', res.token);
      setToken(res.token);
      setUser(res.user);
      setHasDonorProfile(res.has_donor_profile || false);
      setShowAuthModal(false);
    }
    return res;
  };

  const handleLogin = async (payload) => {
    const res = await loginUser(payload);
    if (res.token) {
      localStorage.setItem('token', res.token);
      setToken(res.token);
      setUser(res.user);
      setHasDonorProfile(res.has_donor_profile || false);
      setDonorProfile(res.donor_profile || null);
      setShowAuthModal(false);
    }
    return res;
  };

  const handleLogout = () => {
    logoutUser();
    setToken(null);
    setUser(null);
    setHasDonorProfile(false);
    setDonorProfile(null);
  };

  const refreshUserData = async () => {
    if (token) {
      try {
        const data = await getCurrentUser();
        if (data?.user) {
          setUser(data.user);
          setHasDonorProfile(data.has_donor_profile || false);
          setDonorProfile(data.donor_profile || null);
        }
      } catch (e) {
        console.error(e);
      }
    }
  };

  return (
    <AuthContext.Provider value={{
      user,
      token,
      hasDonorProfile,
      donorProfile,
      isLoading,
      showAuthModal,
      setShowAuthModal,
      login: handleLogin,
      signup: handleSignup,
      logout: handleLogout,
      refreshUserData
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
