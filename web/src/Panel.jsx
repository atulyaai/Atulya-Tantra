import React, { useEffect } from 'react';

// A pop-up that slides over the orb. Esc or a tap outside closes it, and the orb keeps running underneath.
export function Panel({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className={`panel-scrim${wide ? ' center' : ''}`} onClick={onClose}>
      <aside className={`panel${wide ? ' wide' : ''}`} role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <header className="panel-head">
          <strong>{title}</strong>
          <button type="button" className="panel-close" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <section className="panel-body content">{children}</section>
      </aside>
    </div>
  );
}

// The small launcher that opens from the ☰ button.
export function MenuPopover({ items, user, onPick, onClose, onSignOut }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="panel-scrim clear" onClick={onClose}>
      <nav className="menu-pop" aria-label="Menu" onClick={(e) => e.stopPropagation()}>
        {items.map((item) => (
          <button type="button" key={item.id} onClick={() => onPick(item.id)}>
            <span aria-hidden="true">{item.icon}</span>{item.label}
          </button>
        ))}
        <div className="menu-foot">
          <small>{user?.display_name || user?.username || 'You'}</small>
          <button type="button" onClick={onSignOut}>Sign out</button>
        </div>
      </nav>
    </div>
  );
}
