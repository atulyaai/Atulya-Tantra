import React, { useState, useEffect } from 'react';
import { api, getUser, getToken } from '../api.js';

export function UserManagement({ toast }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const currentUser = getUser();
  
  const [form, setForm] = useState({
    username: '',
    password: '',
    role: 'user',
    displayName: ''
  });

  async function fetchUsers() {
    setLoading(true);
    try {
      const res = await api.get('/api/users');
      if (res.ok) {
        setUsers(res.users);
      }
    } catch (err) {
      toast('error', 'Failed to load users: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchUsers();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.username.trim() || !form.password.trim()) {
      toast('error', 'Username and Password are required');
      return;
    }
    try {
      const res = await api.post('/api/users', {
        username: form.username.trim(),
        password: form.password,
        role: form.role,
        display_name: form.displayName.trim()
      });
      if (res.ok) {
        toast('success', `User ${res.user.display_name} created`);
        setForm({ username: '', password: '', role: 'user', displayName: '' });
        fetchUsers();
      }
    } catch (err) {
      toast('error', err.message);
    }
  }

  async function handleCreate(e) {
    if (username.toLowerCase() === currentUser?.username?.toLowerCase()) {
      toast('error', 'Cannot delete your own account');
      return;
    }
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
      return;
    }
    try {
      const token = getToken();
      const response = await fetch(`/api/users/${encodeURIComponent(username)}`, {
        method: 'DELETE',
        headers: {
          'X-Atulya-Token': token,
          'Content-Type': 'application/json'
        }
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to delete user');
      }
      toast('success', `User "${username}" deleted`);
      fetchUsers();
    } catch (err) {
      toast('error', err.message);
    }
  }

  return (
    <section className="panel-grid">
      <div className="panel">
        <div className="panel-title">
          <h2>User Registry</h2>
          <button onClick={fetchUsers} disabled={loading}>{loading ? 'Refreshing...' : 'Refresh'}</button>
        </div>
        <div className="table user-table">
          <div className="row table-header" style={{ fontWeight: 'bold', borderBottom: '1px solid var(--border)' }}>
            <span>Display Name</span>
            <span>Username</span>
            <span>Role</span>
            <span>Actions</span>
          </div>
          {users.map((u) => (
            <div className="row" key={u.username} style={{ alignItems: 'center' }}>
              <span>{u.display_name}</span>
              <span className="muted">{u.username}</span>
              <span>
                <span className={`badge ${u.role === 'admin' ? 'warn' : 'good'}`}>
                  {u.role.toUpperCase()}
                </span>
              </span>
              <span>
                {u.username.toLowerCase() !== currentUser?.username?.toLowerCase() ? (
                  <button className="danger small" onClick={() => performDelete(u.username)}>Delete</button>
                ) : (
                  <span className="muted small">Current User</span>
                )}
              </span>
            </div>
          ))}
          {users.length === 0 && <p className="muted">No users found.</p>}
        </div>
      </div>

      <form className="panel form" onSubmit={handleCreate}>
        <div className="panel-title">
          <h2>Create User</h2>
        </div>
        <label>
          Username
          <input 
            type="text" 
            value={form.username} 
            onChange={(e) => setForm({ ...form, username: e.target.value })} 
            placeholder="e.g. atul" 
            required 
          />
        </label>
        <label>
          Display Name
          <input 
            type="text" 
            value={form.displayName} 
            onChange={(e) => setForm({ ...form, displayName: e.target.value })} 
            placeholder="e.g. Atul Sharma" 
          />
        </label>
        <label>
          Password
          <input 
            type="password" 
            value={form.password} 
            onChange={(e) => setForm({ ...form, password: e.target.value })} 
            placeholder="Choose password" 
            required 
          />
        </label>
        <label>
          Role
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="user">User (Standard Access)</option>
            <option value="admin">Admin (Full Control)</option>
          </select>
        </label>
        <button className="primary" type="submit">Create User</button>
      </form>
    </section>
  );
}
