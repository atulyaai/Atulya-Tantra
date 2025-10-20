import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { 
  LoginRequest, 
  LoginResponse, 
  DashboardStats, 
  SystemMetrics, 
  ChatMetrics, 
  AgentStatus,
  Conversation,
  User,
  ApiResponse 
} from '../types';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: '/api',
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('admin_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('admin_token');
          window.location.href = '/admin/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Authentication
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response: AxiosResponse<LoginResponse> = await this.api.post('/auth/login', credentials);
    return response.data;
  }

  async logout(): Promise<void> {
    localStorage.removeItem('admin_token');
  }

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    const response: AxiosResponse<DashboardStats> = await this.api.get('/admin/stats');
    return response.data;
  }

  async getSystemMetrics(): Promise<SystemMetrics> {
    const response: AxiosResponse<SystemMetrics> = await this.api.get('/admin/metrics');
    return response.data;
  }

  async getChatMetrics(): Promise<ChatMetrics> {
    const response: AxiosResponse<ChatMetrics> = await this.api.get('/admin/chat-metrics');
    return response.data;
  }

  // Agents
  async getAgentStatus(): Promise<AgentStatus[]> {
    const response: AxiosResponse<AgentStatus[]> = await this.api.get('/admin/agents');
    return response.data;
  }

  async toggleAgent(agentName: string, enabled: boolean): Promise<void> {
    await this.api.post(`/admin/agents/${agentName}/toggle`, { enabled });
  }

  async restartAgent(agentName: string): Promise<void> {
    await this.api.post(`/admin/agents/${agentName}/restart`);
  }

  // Conversations
  async getConversations(page = 1, limit = 20): Promise<{ data: Conversation[]; total: number }> {
    const response: AxiosResponse<{ data: Conversation[]; total: number }> = await this.api.get(
      `/admin/conversations?page=${page}&limit=${limit}`
    );
    return response.data;
  }

  async getConversation(conversationId: string): Promise<Conversation> {
    const response: AxiosResponse<Conversation> = await this.api.get(`/admin/conversations/${conversationId}`);
    return response.data;
  }

  async deleteConversation(conversationId: string): Promise<void> {
    await this.api.delete(`/admin/conversations/${conversationId}`);
  }

  // Users
  async getUsers(page = 1, limit = 20): Promise<{ data: User[]; total: number }> {
    const response: AxiosResponse<{ data: User[]; total: number }> = await this.api.get(
      `/admin/users?page=${page}&limit=${limit}`
    );
    return response.data;
  }

  async toggleUser(userId: number, active: boolean): Promise<void> {
    await this.api.post(`/admin/users/${userId}/toggle`, { active });
  }

  // System
  async getSystemStatus(): Promise<any> {
    const response: AxiosResponse<any> = await this.api.get('/admin/status');
    return response.data;
  }

  async restartSystem(): Promise<void> {
    await this.api.post('/admin/restart');
  }

  async getHealthCheck(): Promise<any> {
    const response: AxiosResponse<any> = await this.api.get('/health/');
    return response.data;
  }
}

export const apiService = new ApiService();
