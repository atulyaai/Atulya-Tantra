import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

function renderMarkdown(text) {
  const parts = String(text || '').split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, idx) => {
    if (part.startsWith('`') && part.endsWith('`')) return <code key={idx}>{part.slice(1, -1)}</code>;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={idx}>{part.slice(2, -2)}</strong>;
    return part.split('\n').map((line, lineIdx) => (
      <React.Fragment key={`${idx}-${lineIdx}`}>
        {lineIdx > 0 && <br />}
        {line}
      </React.Fragment>
    ));
  });
}

export function Chat({ bootstrap }) {
  const checkpoints = bootstrap?.checkpoints || [];
  const [model, setModel] = useState('latest');
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState([]);
  const [toolSteps, setToolSteps] = useState([]);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages]);

  function historyPayload(items = messages) {
    return items
      .filter((msg) => msg.text)
      .slice(-10)
      .map((msg) => ({ role: msg.role, content: msg.text }));
  }

  function send(event) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    const id = Date.now();
    const text = prompt;
    const nextMessages = [...messages, { role: 'user', text }, { role: 'assistant', text: '', id }];
    setPrompt('');
    setBusy(true);
    setToolSteps([]);
    setMessages(nextMessages);
    api.streamChat(
      { prompt: text, model_id: model, max_tokens: 256, temperature: 0.7, history: historyPayload(messages) },
      (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
      (done) => {
        if (done?.steps) setToolSteps(done.steps);
        if (done?.needs_approval) {
          setPendingApproval({
            prompt: text,
            tool: done.tool,
            tool_args: done.tool_args,
            pending_tool: done.pending_tool || { tool: done.tool, arguments: done.tool_args || {} },
          });
        }
        setBusy(false);
      },
      (err) => {
        setBusy(false);
        setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
      },
      (tool) => setToolSteps((prev) => [...prev, tool]),
    );
  }

  return (
    <section className="panel chat">
      <div className="panel-title">
        <h2>Neural Playground</h2>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          {checkpoints.map((item) => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
        </select>
      </div>
      <div className="messages">
        {toolSteps.map((step, idx) => (
          <div className="message assistant tool-step" key={`${step.tool}-${idx}`}>
            <strong>{step.tool}</strong>: {step.success ? 'done' : step.error || 'failed'}
          </div>
        ))}
        {messages.map((msg, idx) => <div className={`message ${msg.role}`} key={msg.id || idx}>{renderMarkdown(msg.text)}</div>)}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={send}>
        <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Send a prompt..." />
        <button className="primary" disabled={busy}>{busy ? 'Streaming...' : 'Send'}</button>
      </form>
      {pendingApproval && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Approve action">
          <div className="modal-card">
            <h2>Approve Action</h2>
            <p className="muted">Review this tool call before Atulya runs it.</p>
            <pre className="terminal">{JSON.stringify({ tool: pendingApproval.tool, args: pendingApproval.tool_args }, null, 2)}</pre>
            <div className="terminal-actions">
              <button type="button" onClick={() => setPendingApproval(null)}>Cancel</button>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  const approved = pendingApproval.prompt;
                  const id = Date.now();
                  setPendingApproval(null);
                  setBusy(true);
                  setMessages((prev) => [...prev, { role: 'assistant', text: '', id }]);
                  api.streamChat(
                    {
                      prompt: approved,
                      model_id: model,
                      history: historyPayload(),
                      approved_tool: pendingApproval.pending_tool,
                    },
                    (token) => setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: msg.text + token } : msg)),
                    (done) => {
                      if (done?.steps) setToolSteps(done.steps);
                      setBusy(false);
                    },
                    (err) => {
                      setBusy(false);
                      setMessages((prev) => prev.map((msg) => msg.id === id ? { ...msg, text: `Error: ${err.message}` } : msg));
                    },
                    (tool) => setToolSteps((prev) => [...prev, tool]),
                  );
                }}
              >
                Approve and run
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
