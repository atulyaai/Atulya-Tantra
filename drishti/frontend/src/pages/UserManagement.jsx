import React, { useState } from 'react';
import { api } from '../../api.js';

export function UserManagement({ toast }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  React.useEffect(() => {
    api.get('/api/admin/users')
      .then(data => { setUsers(data.users || []); setLoading(false); })
      .catch(err => { toast('error', 'Failed to load users: ' + err.message); setLoading(false); });
  }, []);

  return (
    <div className="page-container">
      <h2>User Management</h2>
      <p className="muted">Admin panel to manage operator accounts.</p>
      {loading ? <p>Loading...</p> : (
        <table className="data-table">
          <thead>
            <tr><th>Username</th><th>Role</th><th>Status</th></tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.username}>
                <td>{u.username}</td>
                <td>{u.role}</td>
                <td style={{ color: u.disabled ? '#ff6644' : '#44ff88' }}>{u.disabled ? 'Disabled' : 'Active'}</td>
              </tr>
            ))}
            {users.length === 0 && <tr><td colSpan={3} className="muted">No users found.</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}
