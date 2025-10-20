import { create } from 'zustand';
import { DashboardStats, SystemMetrics, ChatMetrics, AgentStatus } from '../types';
import { apiService } from '../services/api';

interface DashboardStore {
  // State
  stats: DashboardStats | null;
  systemMetrics: SystemMetrics | null;
  chatMetrics: ChatMetrics | null;
  agents: AgentStatus[];
  isLoading: boolean;
  error: string | null;
  lastUpdated: string | null;

  // Actions
  fetchDashboardStats: () => Promise<void>;
  fetchSystemMetrics: () => Promise<void>;
  fetchChatMetrics: () => Promise<void>;
  fetchAgents: () => Promise<void>;
  refreshAll: () => Promise<void>;
  toggleAgent: (agentName: string, enabled: boolean) => Promise<void>;
  restartAgent: (agentName: string) => Promise<void>;
  clearError: () => void;
}

export const useDashboardStore = create<DashboardStore>((set, get) => ({
  // Initial state
  stats: null,
  systemMetrics: null,
  chatMetrics: null,
  agents: [],
  isLoading: false,
  error: null,
  lastUpdated: null,

  // Actions
  fetchDashboardStats: async () => {
    try {
      const stats = await apiService.getDashboardStats();
      set({ stats, error: null });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to fetch dashboard stats' });
    }
  },

  fetchSystemMetrics: async () => {
    try {
      const systemMetrics = await apiService.getSystemMetrics();
      set({ systemMetrics, error: null });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to fetch system metrics' });
    }
  },

  fetchChatMetrics: async () => {
    try {
      const chatMetrics = await apiService.getChatMetrics();
      set({ chatMetrics, error: null });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to fetch chat metrics' });
    }
  },

  fetchAgents: async () => {
    try {
      const agents = await apiService.getAgentStatus();
      set({ agents, error: null });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to fetch agents' });
    }
  },

  refreshAll: async () => {
    set({ isLoading: true });
    try {
      await Promise.all([
        get().fetchDashboardStats(),
        get().fetchSystemMetrics(),
        get().fetchChatMetrics(),
        get().fetchAgents(),
      ]);
      set({ lastUpdated: new Date().toISOString(), isLoading: false });
    } catch (error) {
      set({ 
        error: error instanceof Error ? error.message : 'Failed to refresh data',
        isLoading: false 
      });
    }
  },

  toggleAgent: async (agentName: string, enabled: boolean) => {
    try {
      await apiService.toggleAgent(agentName, enabled);
      // Update local state
      const agents = get().agents.map(agent => 
        agent.name === agentName 
          ? { ...agent, status: enabled ? 'active' : 'inactive' }
          : agent
      );
      set({ agents });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to toggle agent' });
    }
  },

  restartAgent: async (agentName: string) => {
    try {
      await apiService.restartAgent(agentName);
      // Refresh agents to get updated status
      await get().fetchAgents();
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Failed to restart agent' });
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));
