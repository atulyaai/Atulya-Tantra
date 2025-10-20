// Core types for Atulya Tantra Admin Dashboard

export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_io: {
    bytes_sent: number;
    bytes_received: number;
  };
  active_connections: number;
  timestamp: string;
}

export interface ChatMetrics {
  total_messages: number;
  active_conversations: number;
  messages_per_hour: number;
  average_response_time: number;
  model_usage: Record<string, number>;
  timestamp: string;
}

export interface AgentStatus {
  name: string;
  status: 'active' | 'inactive' | 'error';
  last_activity: string;
  tasks_completed: number;
  error_count: number;
}

export interface Conversation {
  id: string;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: 'success' | 'error';
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface DashboardStats {
  total_users: number;
  total_conversations: number;
  total_messages: number;
  system_health: 'healthy' | 'warning' | 'error';
  uptime: string;
  version: string;
}
