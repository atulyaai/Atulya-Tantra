import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthState, User, LoginRequest } from '../types';
import { apiService } from '../services/api';

interface AuthStore extends AuthState {
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist((set, get) => ({
    token: null,
    user: null,
    isAuthenticated: false,
    isLoading: false,

    login: async (credentials: LoginRequest) => {
      set({ isLoading: true });
      try {
        const response = await apiService.login(credentials);
        set({
          token: response.access_token,
          user: response.user,
          isAuthenticated: true,
          isLoading: false,
        });
        localStorage.setItem('admin_token', response.access_token);
      } catch (error) {
        set({ isLoading: false });
        throw error;
      }
    },

    logout: () => {
      apiService.logout();
      set({
        token: null,
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    },

    setToken: (token: string) => {
      set({ token, isAuthenticated: true });
      localStorage.setItem('admin_token', token);
    },

    setUser: (user: User) => {
      set({ user });
    },

    clearAuth: () => {
      localStorage.removeItem('admin_token');
      set({
        token: null,
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
    },
  }), {
    name: 'auth-storage',
    partialize: (state) => ({
      token: state.token,
      user: state.user,
      isAuthenticated: state.isAuthenticated,
    }),
  })
);
