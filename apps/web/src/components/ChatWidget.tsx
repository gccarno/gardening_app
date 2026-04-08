import { useState, useRef, useEffect } from 'react';
import { sendChat } from '../api/gardens';

type Msg = { id: string; role: 'user' | 'bot'; text: string };

export default function ChatWidget({
  gardenId,
  gardenName,
  zone,
}: {
  gardenId?: number;
  gardenName?: string;
  zone?: string;
}) {
  const [open, setOpen]       = useState(true);
  const [msgs, setMsgs]       = useState<Msg[]>([
    { id: 'init', role: 'bot', text: "Hi! I'm your garden assistant. Ask me about planting, pests, companions, schedules — or say \"add [plant] to my garden\"!" },
  ]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const [chipsHidden, setChipsHidden] = useState(false);
  const historyRef  = useRef<Array<{ role: string; content: string }>>([]);
  const sessionRef  = useRef(crypto.randomUUID());
  const messagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [msgs]);

  async function send(override?: string) {
    const text = (override ?? input).trim();
    if (!text || loading) return;
    setInput('');
    setChipsHidden(true);

    const userMsg: Msg = { id: crypto.randomUUID(), role: 'user', text };
    setMsgs(prev => [...prev, userMsg]);
    historyRef.current.push({ role: 'user', content: text });
    setLoading(true);

    try {
      const data = await sendChat({
        message:              text,
        garden_id:            gardenId ?? null,
        conversation_history: historyRef.current.slice(0, -1),
        session_id:           sessionRef.current,
      });

      const reply = data.reply ?? 'No response.';
      setMsgs(prev => [...prev, { id: crypto.randomUUID(), role: 'bot', text: reply }]);
      if (data.conversation_history) historyRef.current = data.conversation_history;
      if (data.session_id) sessionRef.current = data.session_id;
      historyRef.current.push({ role: 'assistant', content: reply });
    } catch {
      setMsgs(prev => [...prev, {
        id: crypto.randomUUID(), role: 'bot',
        text: 'Could not reach the assistant. Check your connection and try again.',
      }]);
      historyRef.current.pop();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat-widget" id="chat-widget">
      <div className="chat-widget__header" onClick={() => setOpen(o => !o)} style={{ cursor: 'pointer' }}>
        <span className="chat-widget__icon">🤖</span>
        <div>
          <strong>Garden Assistant</strong>
          {gardenName && (
            <span className="chat-context-badge">
              {gardenName}{zone ? ` · Zone ${zone}` : ''}
            </span>
          )}
        </div>
        <button className="chat-widget__toggle" aria-label="Toggle chat">{open ? '▾' : '▸'}</button>
      </div>

      {open && (
        <div className="chat-widget__body">
          <div className="chat-messages" ref={messagesRef}>
            {msgs.map(m => (
              <div key={m.id} className={`chat-msg chat-msg--${m.role === 'user' ? 'user' : 'bot'}`}>
                <span>{m.text}</span>
              </div>
            ))}
            {loading && (
              <div className="chat-msg chat-msg--bot chat-msg--typing">
                <span /><span /><span />
              </div>
            )}
          </div>

          {!chipsHidden && (
            <div className="chat-prompt-chips">
              {[
                'What should I plant this month?',
                'Check companion planting for my beds',
                'What tasks are coming up?',
                'What is ready to harvest?',
              ].map(chip => (
                <button key={chip} className="chat-prompt-chip" onClick={() => send(chip)}>{chip}</button>
              ))}
            </div>
          )}

          <div className="chat-input-row">
            <input
              type="text"
              className="chat-input"
              placeholder="Ask about planting, companions, tasks…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
            />
            <button className="btn btn--sm" onClick={() => send()}>Send</button>
          </div>
        </div>
      )}
    </div>
  );
}
