import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API = 'http://127.0.0.1:8000';

const QUICK_QUESTIONS = [
  "What is the engagement rate of each video?",
  "Compare the hooks in the first 5 seconds",
  "Why did Video A get more engagement than Video B?",
  "Who is the creator of Video B and what's their follower count?",
  "Suggest improvements for B based on what worked in A"
];

function formatNumber(num) {
  if (!num) return '0';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toString();
}

function VideoCard({ data, label, badgeClass }) {
  if (!data) return (
    <div className="video-card">
      <span className={`badge ${badgeClass}`}>Video {label}</span>
      <p style={{ color: '#555', fontSize: '14px' }}>
        Enter a URL above and click Analyze
      </p>
    </div>
  );

  return (
    <div className="video-card">
      <span className={`badge ${badgeClass}`}>Video {label}</span>
      <h3>{data.title || 'No title'}</h3>
      <p className="creator">by {data.creator || 'Unknown'}</p>

      <div className="stats-grid">
        <div className="stat">
          <div className="label">Views</div>
          <div className="value">{formatNumber(data.views)}</div>
        </div>
        <div className="stat">
          <div className="label">Likes</div>
          <div className="value">{formatNumber(data.likes)}</div>
        </div>
        <div className="stat">
          <div className="label">Comments</div>
          <div className="value">{formatNumber(data.comments)}</div>
        </div>
        <div className="stat">
          <div className="label">Followers</div>
          <div className="value">{formatNumber(data.followers)}</div>
        </div>
      </div>

      <div className="engagement">
        <div className="label">Engagement Rate</div>
        <div className="value">{data.engagement_rate}%</div>
      </div>

      {data.hashtags && data.hashtags.length > 0 && (
        <div className="hashtags">
          {data.hashtags.map((tag, i) => (
            <span key={i} className="hashtag">#{tag}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [instagramUrl, setInstagramUrl] = useState('');
  const [videoA, setVideoA] = useState(null);
  const [videoB, setVideoB] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleIngest = async () => {
    if (!youtubeUrl || !instagramUrl) {
      setError('Please enter both URLs');
      return;
    }

    setError('');
    setIngesting(true);
    setStatus('Fetching video data and building knowledge base...');
    setVideoA(null);
    setVideoB(null);
    setMessages([]);
    setReady(false);

    try {
      const res = await axios.post(`${API}/ingest`, {
        youtube_url: youtubeUrl,
        instagram_url: instagramUrl
      });

      if (res.data.success) {
        setVideoA(res.data.video_a);
        setVideoB(res.data.video_b);
        setReady(true);
        setStatus('');
        setMessages([{
          role: 'assistant',
          content: `Both videos analyzed! Video A has ${res.data.video_a.engagement_rate}% engagement rate and Video B has ${res.data.video_b.engagement_rate}% engagement rate. Ask me anything!`,
          citations: []
        }]);
      } else {
        setError('Error: ' + res.data.error);
        setStatus('');
      }
    } catch (err) {
      setError('Failed to connect to backend. Make sure it is running on port 8000.');
      setStatus('');
    }

    setIngesting(false);
  };

  const handleChat = async (question) => {
    const msg = question || input.trim();
    if (!msg || loading || !ready) return;

    setInput('');
    setLoading(true);

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: msg }]);

    // Add empty assistant message that we will fill in
    setMessages(prev => [...prev, { role: 'assistant', content: '', citations: [] }]);

    try {
      const response = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') break;

            try {
              const parsed = JSON.parse(data);

              if (parsed.type === 'token') {
                setMessages(prev => {
                  const updated = prev.map((msg, idx) => {
                    if (idx === prev.length - 1) {
                      return { ...msg, content: msg.content + parsed.content };
                    }
                    return msg;
                  });
                  return updated;
                });
              }

              if (parsed.type === 'citations') {
                setMessages(prev => {
                  const updated = [...prev];
                  updated[updated.length - 1].citations = parsed.content;
                  return updated;
                });
              }

              if (parsed.type === 'error') {
                setMessages(prev => {
                  const updated = [...prev];
                  updated[updated.length - 1].content = 'Error: ' + parsed.content;
                  return updated;
                });
              }
            } catch (e) {
              // skip malformed lines
            }
          }
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1].content = 'Connection error. Please try again.';
        return updated;
      });
    }

    setLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChat();
    }
  };

  return (
    <div className="app">
      <div className="header">
        <h1>Video Engagement Analyzer</h1>
        <p>Compare two videos using AI — powered by RAG + LangChain</p>
      </div>

      {/* URL Input Section */}
      <div className="input-section">
        <h2>Enter Video URLs</h2>
        <div className="url-inputs">
          <input
            type="text"
            placeholder="YouTube URL (Video A)"
            value={youtubeUrl}
            onChange={e => setYoutubeUrl(e.target.value)}
            disabled={ingesting}
          />
          <input
            type="text"
            placeholder="Instagram Reel URL (Video B)"
            value={instagramUrl}
            onChange={e => setInstagramUrl(e.target.value)}
            disabled={ingesting}
          />
        </div>
        <button
          className="analyze-btn"
          onClick={handleIngest}
          disabled={ingesting}
        >
          {ingesting ? 'Analyzing Videos...' : 'Analyze Videos'}
        </button>
        {status && <p className="status-msg">{status}</p>}
        {error && <p className="error-msg">{error}</p>}
      </div>

      {/* Video Cards */}
      <div className="video-cards">
        <VideoCard data={videoA} label="A" badgeClass="badge-a" />
        <VideoCard data={videoB} label="B" badgeClass="badge-b" />
      </div>

      {/* Chat Section */}
      <div className="chat-section">
        <div className="chat-header">
          AI Chat — Ask anything about the videos
        </div>

        <div className="chat-messages">
          {messages.length === 0 && (
            <p style={{ color: '#555', fontSize: '14px', textAlign: 'center', marginTop: '40px' }}>
              Analyze two videos above to start chatting
            </p>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-bubble">
                {msg.content || (msg.role === 'assistant' && loading && i === messages.length - 1
                  ? '...'
                  : '')}
              </div>
              {msg.citations && msg.citations.length > 0 && (
                <div className="citations">
                  {msg.citations.map((c, j) => (
                    <span key={j} className="citation">
                      Video {c.video_id} · Chunk {c.chunk_index}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Questions */}
        {ready && (
          <div className="quick-questions">
            {QUICK_QUESTIONS.map((q, i) => (
              <button
                key={i}
                className="quick-btn"
                onClick={() => handleChat(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Chat Input */}
        <div className="chat-input">
          <input
            type="text"
            placeholder={ready ? "Ask anything about the videos..." : "Analyze videos first..."}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading || !ready}
          />
          <button
            className="send-btn"
            onClick={() => handleChat()}
            disabled={loading || !ready}
          >
            {loading ? 'Thinking...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}