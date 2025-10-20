import React, { useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import {
  People,
  Chat,
  Message,
  TrendingUp,
  Refresh,
} from '@mui/icons-material';
import { useDashboardStore } from '../stores/dashboardStore';

export default function Dashboard() {
  const {
    stats,
    systemMetrics,
    chatMetrics,
    agents,
    isLoading,
    error,
    lastUpdated,
    refreshAll,
    clearError,
  } = useDashboardStore();

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const handleRefresh = () => {
    clearError();
    refreshAll();
  };

  if (isLoading && !stats) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Dashboard
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {lastUpdated && (
            <Typography variant="body2" color="text.secondary">
              Last updated: {new Date(lastUpdated).toLocaleTimeString()}
            </Typography>
          )}
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={handleRefresh}
            disabled={isLoading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={clearError}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <People sx={{ color: 'primary.main', mr: 2 }} />
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Users
                  </Typography>
                  <Typography variant="h4">
                    {stats?.total_users || 0}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Chat sx={{ color: 'success.main', mr: 2 }} />
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Conversations
                  </Typography>
                  <Typography variant="h4">
                    {stats?.total_conversations || 0}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Message sx={{ color: 'warning.main', mr: 2 }} />
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Total Messages
                  </Typography>
                  <Typography variant="h4">
                    {stats?.total_messages || 0}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <TrendingUp sx={{ color: 'info.main', mr: 2 }} />
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    System Health
                  </Typography>
                  <Chip
                    label={stats?.system_health || 'Unknown'}
                    color={
                      stats?.system_health === 'healthy' ? 'success' :
                      stats?.system_health === 'warning' ? 'warning' : 'error'
                    }
                    size="small"
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* System Metrics */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Performance
              </Typography>
              {systemMetrics ? (
                <Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      CPU Usage: {systemMetrics.cpu_usage.toFixed(1)}%
                    </Typography>
                    <Box sx={{ width: '100%', bgcolor: 'grey.200', borderRadius: 1, height: 8, mt: 1 }}>
                      <Box
                        sx={{
                          width: `${systemMetrics.cpu_usage}%`,
                          bgcolor: 'primary.main',
                          borderRadius: 1,
                          height: 8,
                        }}
                      />
                    </Box>
                  </Box>
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Memory Usage: {systemMetrics.memory_usage.toFixed(1)}%
                    </Typography>
                    <Box sx={{ width: '100%', bgcolor: 'grey.200', borderRadius: 1, height: 8, mt: 1 }}>
                      <Box
                        sx={{
                          width: `${systemMetrics.memory_usage}%`,
                          bgcolor: 'secondary.main',
                          borderRadius: 1,
                          height: 8,
                        }}
                      />
                    </Box>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Active Connections: {systemMetrics.active_connections}
                  </Typography>
                </Box>
              ) : (
                <Typography color="text.secondary">No data available</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Chat Activity
              </Typography>
              {chatMetrics ? (
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Messages per Hour: {chatMetrics.messages_per_hour}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Avg Response Time: {chatMetrics.average_response_time.toFixed(2)}s
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    Active Conversations: {chatMetrics.active_conversations}
                  </Typography>
                </Box>
              ) : (
                <Typography color="text.secondary">No data available</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Agents Status */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Agent Status
          </Typography>
          {agents.length > 0 ? (
            <Grid container spacing={2}>
              {agents.map((agent) => (
                <Grid item xs={12} sm={6} md={4} key={agent.name}>
                  <Box sx={{ p: 2, border: 1, borderColor: 'grey.300', borderRadius: 1 }}>
                    <Typography variant="subtitle1" gutterBottom>
                      {agent.name}
                    </Typography>
                    <Chip
                      label={agent.status}
                      color={
                        agent.status === 'active' ? 'success' :
                        agent.status === 'inactive' ? 'default' : 'error'
                      }
                      size="small"
                      sx={{ mb: 1 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      Tasks: {agent.tasks_completed}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Last Activity: {new Date(agent.last_activity).toLocaleString()}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Typography color="text.secondary">No agents data available</Typography>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
