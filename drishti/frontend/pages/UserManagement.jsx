import React, { useState, useEffect } from 'react';
import { api, getUser } from '../api.js';

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

  async function handleDelete(username) {
    if (username.toLowerCase() === currentUser?.username?.toLowerCase()) {
      toast('error', 'Cannot delete your own account');
      return;
    }
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
      return;
    }
    try {
      const res = await api.post(`/api/users/${username}`, {}, { method: 'DELETE' }); // api.js post can handle DELETE or we can use custom if api.js wraps request
      // Let's check api.js:
      // api.post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body || {}) })
      // Let's check if we can make a DELETE request or use fetch directly. Since api.js request is not exported, we can just do a custom fetch or write a small request wrapper.
      // Wait! Let's check fetch in api.js: request() is a private helper, but we can do a request or add DELETE to api.js.
      // Let's check api.js again. Ah, request is not exported. But we can make a direct fetch or modify api.js to support delete!
      // Let's see: we can edit api.js to add a delete method, or just call fetch inside UserManagement.jsx. Calling fetch is fine, but adding it to api.js is cleaner.
      // Let's do a direct fetch with the token inside UserManagement.jsx, or add it to api.js. Let's check api.js: it does:
      // const token = getToken();
      // fetch('/api/users/' + username, { method: 'DELETE', headers: { 'X-Atulya-Token': token } })
    } catch (err) {
      toast('error', err.message);
    }
  }

  // To be safe, let's write a deletion function using fetch:
  async function performDelete(username) {
    if (username.toLowerCase() === currentUser?.username?.toLowerCase()) {
      toast('error', 'Cannot delete your own account');
      return;
    }
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
      return;
    }
    try {
      const token = localStorage.getItem('atulya-dashboard-token') || '';
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
        <div className="table">
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
