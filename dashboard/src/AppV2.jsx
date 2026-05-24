import React, { useState, useEffect, useRef } from 'react';
import { 
  LayoutGrid, 
  Bell, 
  Folder, 
  Search, 
  Settings, 
  ChevronLeft, 
  ChevronRight, 
  LogOut, 
  Sun, 
  Moon,
  Shield,
  Check
} from 'lucide-react';

const THEMES = {
  dark: `
    --bg-app: #0A0E1A;
    --bg-surface: #111827;
    --bg-elevated: #1A2235;
    --bg-hover: #1E2A40;
    --border: #1E2D45;
    --text-primary: #F1F5F9;
    --text-secondary: #7A8EA8;
    --text-muted: #3D5170;
    --accent: #E11D48;
    --accent-hover: #BE123C;
    --accent-subtle: rgba(225,29,72,0.12);
    --success: #10B981;
    --warning: #F59E0B;
    --info: #3B82F6;
    --critical: #E11D48;
    --critical-bg: rgba(225,29,72,0.1);
    --high: #F59E0B;
    --high-bg: rgba(245,158,11,0.1);
    --medium: #3B82F6;
    --medium-bg: rgba(59,130,246,0.1);
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
  `,
  light: `
    --bg-app: #F1F5F9;
    --bg-surface: #FFFFFF;
    --bg-elevated: #F8FAFF;
    --bg-hover: #F1F5FF;
    --border: #E2E8F4;
    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #94A3B8;
    --accent: #E11D48;
    --accent-hover: #BE123C;
    --accent-subtle: rgba(225,29,72,0.06);
    --success: #059669;
    --warning: #D97706;
    --info: #2563EB;
    --critical: #E11D48;
    --critical-bg: #FFF1F3;
    --high: #D97706;
    --high-bg: #FFFBEB;
    --medium: #2563EB;
    --medium-bg: #EFF6FF;
    --shadow: 0 4px 24px rgba(15,23,42,0.08);
  `
};

const applyTheme = (themeName) => {
  const themeValues = THEMES[themeName];
  if (!themeValues) return;
  
  const root = document.documentElement;
  // Parse the theme string and set properties
  themeValues.split(';').forEach(prop => {
    if (!prop.trim()) return;
    const [name, value] = prop.split(':');
    if (name && value) {
      root.style.setProperty(name.trim(), value.trim());
    }
  });
};

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: <LayoutGrid size={18} /> },
  { id: 'alerts', label: 'Alerts', icon: <Bell size={18} /> },
  { id: 'cases', label: 'Cases', icon: <Folder size={18} /> },
  { id: 'investigate', label: 'Investigate', icon: <Search size={18} /> },
  { id: 'divider' },
  { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
];

export default function AppV2() {
  const [theme, setTheme] = useState(localStorage.getItem('sentinel_theme') || 'dark');
  const [token, setToken] = useState(localStorage.getItem('sentinel_token') || null);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });
  const [loginError, setLoginError] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeView, setActiveView] = useState('overview');
  const [summary, setSummary] = useState(null);
  const [digest, setDigest] = useState([]);
  const [dataLoading, setDataLoading] = useState(false);

  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem('sentinel_theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError('');
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('sentinel_token', data.access_token);
        setToken(data.access_token);
      } else {
        const errData = await res.json().catch(() => ({}));
        setLoginError(errData.detail || 'Incorrect username or password');
      }
    } catch (e) {
      setLoginError('Cannot connect to server');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('sentinel_token');
    setToken(null);
  };

  const authHeaders = () => ({ 
    'Authorization': `Bearer ${token}`, 
    'Content-Type': 'application/json' 
  });
  
  const fetchOverviewData = async () => { 
    if (!token) return 
    setDataLoading(true) 
    try { 
      const [sumRes, digRes] = await Promise.all([ 
        fetch(`${API_BASE}/summary`, 
          {headers: authHeaders()}), 
        fetch(`${API_BASE}/digest?days=30`, 
          {headers: authHeaders()}) 
      ]) 
      if (sumRes.ok) setSummary(await sumRes.json()) 
      if (digRes.ok) { 
        const d = await digRes.json() 
        setDigest(Array.isArray(d) ? d : []) 
      } 
    } catch(e) { console.error(e) } 
    setDataLoading(false) 
  };
  
  useEffect(() => { 
    if (token && activeView === 'overview') { 
      fetchOverviewData() 
    } 
  }, [token, activeView]);

  useEffect(() => { 
    if (!digest.length || !chartRef.current) return 
    if (chartInstanceRef.current) { 
      chartInstanceRef.current.destroy() 
    } 
    const ctx = chartRef.current.getContext('2d') 
    const labels = digest.slice(-30).map(d => { 
      const date = new Date(d.alert_date) 
      return date.toLocaleDateString('en-US', 
        {month:'short', day:'numeric'}) 
    }) 
    const last30 = digest.slice(-30) 
    chartInstanceRef.current = new window.Chart(ctx, { 
      type: 'line', 
      data: { 
        labels, 
        datasets: [ 
          { 
            label:'Critical', 
            data: last30.map(d => d.critical_count||0), 
            borderColor: '#E11D48', 
            backgroundColor: 'rgba(225,29,72,0.06)', 
            borderWidth: 2, 
            fill: true, 
            tension: 0.15, 
            pointRadius: 0, 
            pointHoverRadius: 4 
          }, 
          { 
            label:'High', 
            data: last30.map(d => d.high_count||0), 
            borderColor: '#F59E0B', 
            backgroundColor: 'transparent', 
            borderWidth: 2, 
            tension: 0.15, 
            pointRadius: 0, 
            pointHoverRadius: 4 
          }, 
          { 
            label:'Medium', 
            data: last30.map(d => d.medium_count||0), 
            borderColor: '#3B82F6', 
            backgroundColor: 'transparent', 
            borderWidth: 1.5, 
            tension: 0.15, 
            pointRadius: 0, 
            pointHoverRadius: 4 
          }, 
          { 
            label:'Threshold', 
            data: last30.map(() => 3), 
            borderColor: 'rgba(100,116,139,0.3)', 
            borderWidth: 1, 
            borderDash: [6,4], 
            pointRadius: 0, 
            fill: false, 
            tension: 0 
          } 
        ] 
      }, 
      options: { 
        responsive: true, 
        maintainAspectRatio: false, 
        interaction: {mode:'index', intersect:false}, 
        plugins: { 
          legend: {display: false}, 
          tooltip: { 
            backgroundColor: 'var(--bg-elevated)', 
            borderColor: 'var(--border)', 
            borderWidth: 1, 
            titleColor: 'var(--text-primary)', 
            bodyColor: 'var(--text-secondary)', 
            padding: 10 
          } 
        }, 
        scales: { 
          x: { 
            grid: {display:false}, 
            border: { 
              color:'var(--border)' 
            }, 
            ticks: { 
              color:'var(--text-muted)', 
              font:{size:10}, 
              maxTicksLimit:8 
            } 
          }, 
          y: { 
            min: 0, 
            grid: {color:'var(--border-subtle)'}, 
            border: {display:false}, 
            ticks: { 
              color:'var(--text-muted)', 
              font:{size:10}, 
              stepSize:2 
            } 
          } 
        } 
      } 
    }) 
    return () => { 
      if (chartInstanceRef.current) { 
        chartInstanceRef.current.destroy() 
      } 
    } 
  }, [digest]);

  if (!token) {
    return (
      <div style={{ 
        display: 'flex', 
        height: '100vh', 
        width: '100vw', 
        overflow: 'hidden',
        fontFamily: "'DM Sans', sans-serif",
        background: 'var(--bg-app)'
      }}>
        {/* LEFT PANEL */}
        <div style={{ 
          width: '45%', 
          background: 'var(--bg-surface)', 
          display: 'flex', 
          flexDirection: 'column', 
          justifyContent: 'center', 
          alignItems: 'center',
          padding: '40px'
        }}>
          <div style={{ width: '100%', maxWidth: '380px' }}>
            {/* Logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '40px' }}>
              <Shield size={20} stroke="#E11D48" />
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: 'bold', fontSize: '18px', color: 'var(--text-primary)' }}>SentinelEHR</span>
                <span style={{ 
                  fontSize: '10px', 
                  letterSpacing: '0.1em', 
                  textTransform: 'uppercase', 
                  color: 'var(--text-muted)',
                  fontWeight: '600'
                }}>Healthcare Insider Risk</span>
              </div>
            </div>

            <h2 style={{ fontSize: '28px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px' }}>Welcome back</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '32px' }}>Sign in to your compliance dashboard</p>

            <form onSubmit={handleLogin}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '12px', 
                  fontWeight: '600', 
                  textTransform: 'uppercase', 
                  color: 'var(--text-muted)', 
                  marginBottom: '8px',
                  letterSpacing: '0.05em'
                }}>Username</label>
                <input 
                  type="text" 
                  value={loginForm.username}
                  onChange={e => setLoginForm({...loginForm, username: e.target.value})}
                  required
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '14px',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'border-color 0.2s'
                  }}
                  onFocus={e => e.target.style.borderColor = '#E11D48'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '12px', 
                  fontWeight: '600', 
                  textTransform: 'uppercase', 
                  color: 'var(--text-muted)', 
                  marginBottom: '8px',
                  letterSpacing: '0.05em'
                }}>Password</label>
                <input 
                  type="password" 
                  value={loginForm.password}
                  onChange={e => setLoginForm({...loginForm, password: e.target.value})}
                  required
                  style={{
                    width: '100%',
                    padding: '12px 16px',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    color: 'var(--text-primary)',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '14px',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'border-color 0.2s'
                  }}
                  onFocus={e => e.target.style.borderColor = '#E11D48'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
              </div>

              {loginError && (
                <div style={{ 
                  padding: '12px', 
                  background: 'rgba(225,29,72,0.1)', 
                  border: '1px solid rgba(225,29,72,0.2)', 
                  borderRadius: '8px', 
                  color: '#E11D48', 
                  fontSize: '14px', 
                  marginBottom: '20px' 
                }}>
                  {loginError}
                </div>
              )}

              <button 
                type="submit" 
                disabled={loggingIn}
                style={{
                  width: '100%',
                  padding: '14px',
                  background: '#E11D48',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '700',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  cursor: loggingIn ? 'default' : 'pointer',
                  opacity: loggingIn ? 0.7 : 1,
                  transition: 'background 0.2s'
                }}
              >
                {loggingIn ? 'Connecting...' : 'Sign In →'}
              </button>
            </form>

            <button 
              onClick={toggleTheme}
              style={{
                marginTop: '32px',
                background: 'transparent',
                border: 'none',
                color: 'var(--text-secondary)',
                fontSize: '14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            </button>
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div style={{ 
          flex: 1, 
          background: 'linear-gradient(135deg, #0D1525, #1A2235, #0A1628)',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          color: '#FFFFFF'
        }}>
          {/* Grid Overlay */}
          <div style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `linear-gradient(rgba(225,29,72,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(225,29,72,0.03) 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
            pointerEvents: 'none'
          }} />

          {/* Shield Illustration */}
          <div style={{ position: 'relative', width: '160px', height: '180px', marginBottom: '40px' }}>
            <svg width="160" height="180" viewBox="0 0 160 180" fill="none">
              <defs>
                <linearGradient id="shieldGrad" x1="80" y1="0" x2="80" y2="180" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#1E293B" />
                  <stop offset="1" stopColor="#0F172A" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="4" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>
              <path d="M80 0L10 30V80C10 130 40 165 80 180C120 165 150 130 150 80V30L80 0Z" fill="url(#shieldGrad)" stroke="#1E2D45" strokeWidth="2"/>
              <path d="M55 90 L72 107 L105 74" stroke="#E11D48" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" filter="url(#glow)"/>
            </svg>
            <div style={{ 
              position: 'absolute', 
              bottom: '-20px', 
              left: '50%', 
              transform: 'translateX(-50%)',
              width: '120px', 
              height: '10px', 
              background: 'rgba(0,0,0,0.3)', 
              borderRadius: '50%', 
              filter: 'blur(8px)' 
            }} />
          </div>

          <h3 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px', textAlign: 'center' }}>Healthcare Insider Risk Intelligence</h3>
          <p style={{ 
            fontSize: '14px', 
            color: '#94A3B8', 
            textAlign: 'center', 
            maxWidth: '400px', 
            lineHeight: '1.6',
            marginBottom: '48px'
          }}>Real-time behavioral monitoring for Epic EHR. Detect threats before they become breaches.</p>

          <div style={{ display: 'flex', gap: '48px', textAlign: 'center' }}>
            <div>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '22px', fontWeight: '700', color: '#E11D48' }}>325K</div>
              <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '4px' }}>Events Monitored</div>
            </div>
            <div>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '22px', fontWeight: '700', color: '#E11D48' }}>0</div>
              <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '4px' }}>PHI Stored</div>
            </div>
            <div>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '22px', fontWeight: '700', color: '#E11D48' }}>86%</div>
              <div style={{ fontSize: '11px', fontWeight: '600', color: '#475569', textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: '4px' }}>Alert Precision</div>
            </div>
          </div>

          <div style={{ 
            position: 'absolute', 
            bottom: '40px', 
            right: '40px',
            padding: '6px 16px',
            border: '1px solid rgba(225,29,72,0.4)',
            borderRadius: '20px',
            color: '#E11D48',
            fontSize: '11px',
            fontFamily: "'IBM Plex Mono', monospace",
            fontWeight: '600'
          }}>
            HIPAA §164.312(b) COMPLIANT
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      display: 'flex', 
      height: '100vh', 
      width: '100vw', 
      background: 'var(--bg-app)',
      color: 'var(--text-primary)',
      fontFamily: "'DM Sans', sans-serif"
    }}>
      {/* SIDEBAR */}
      <aside style={{
        width: sidebarCollapsed ? '64px' : '220px',
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        zIndex: 10
      }}>
        {/* Top Logo */}
        <div style={{ 
          height: '60px', 
          display: 'flex', 
          alignItems: 'center', 
          padding: '0 20px', 
          borderBottom: '1px solid var(--border)',
          gap: '12px',
          overflow: 'hidden'
        }}>
          <Shield size={22} color="#E11D48" style={{ flexShrink: 0 }} />
          {!sidebarCollapsed && <span style={{ fontWeight: '700', fontSize: '16px', whiteSpace: 'nowrap' }}>SentinelEHR</span>}
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '16px 0', overflowY: 'auto' }}>
          {NAV_ITEMS.map((item, idx) => {
            if (item.id === 'divider') {
              return <div key={`div-${idx}`} style={{ height: '1px', background: 'var(--border)', margin: '16px 0' }} />;
            }
            
            const isActive = activeView === item.id;
            
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                title={sidebarCollapsed ? item.label : ''}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  padding: '12px 20px',
                  background: isActive ? 'var(--accent-subtle)' : 'transparent',
                  border: 'none',
                  borderLeft: isActive ? '3px solid var(--accent)' : '3px solid transparent',
                  color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  gap: '12px',
                  transition: 'background 0.2s',
                  textAlign: 'left'
                }}
                onMouseEnter={e => !isActive && (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={e => !isActive && (e.currentTarget.style.background = 'transparent')}
              >
                <span style={{ flexShrink: 0 }}>{item.icon}</span>
                {!sidebarCollapsed && <span style={{ fontSize: '14px', fontWeight: isActive ? '600' : '500' }}>{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Bottom Actions */}
        <div style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
          <button 
            onClick={toggleTheme}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              padding: '12px 20px',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              gap: '12px'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            {!sidebarCollapsed && <span style={{ fontSize: '14px' }}>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
          </button>
          
          <button 
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              padding: '12px 20px',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              gap: '12px'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            {!sidebarCollapsed && <span style={{ fontSize: '14px' }}>Collapse Sidebar</span>}
          </button>

          <button 
            onClick={handleLogout}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              padding: '12px 20px',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              gap: '12px'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <LogOut size={18} />
            {!sidebarCollapsed && <span style={{ fontSize: '14px' }}>Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Top Bar */}
        <header style={{
          height: '60px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          flexShrink: 0
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: '700', textTransform: 'capitalize' }}>{activeView}</h2>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ 
              width: '8px', 
              height: '8px', 
              background: 'var(--success)', 
              borderRadius: '50%',
              boxShadow: '0 0 8px var(--success)',
              animation: 'pulse 2s infinite'
            }} />
            <span style={{ 
              fontFamily: "'IBM Plex Mono', monospace", 
              fontSize: '12px', 
              fontWeight: '600', 
              color: 'var(--text-muted)' 
            }}>LIVE</span>
          </div>
        </header>

        {/* Content Area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
          {activeView === 'overview' && ( 
            <div style={{maxWidth:'1200px'}}> 
          
              {/* Stat cards */} 
              <div style={{ 
                display:'grid', 
                gridTemplateColumns:'repeat(4, 1fr)', 
                gap:'16px', marginBottom:'24px' 
              }}> 
                {[ 
                  { 
                    label:'CRITICAL THREATS', 
                    value: summary?.critical ?? '—', 
                    sub:'Require immediate action', 
                    color:'var(--critical)', 
                    bg:'var(--critical-bg)' 
                  }, 
                  { 
                    label:'HIGH RISK', 
                    value: summary?.high ?? '—', 
                    sub:'ML-elevated alerts', 
                    color:'var(--high)', 
                    bg:'var(--high-bg)' 
                  }, 
                  { 
                    label:'MEDIUM RISK', 
                    value: summary?.medium ?? '—', 
                    sub:'Under observation', 
                    color:'var(--medium)', 
                    bg:'var(--medium-bg)' 
                  }, 
                  { 
                    label:'ML PEAK SCORE', 
                    value: summary?.top_anomaly_score 
                      ? summary.top_anomaly_score.toFixed(2) 
                      : '—', 
                    sub:'90-day highest anomaly', 
                    color:'var(--text-primary)', 
                    bg:'var(--bg-elevated)' 
                  } 
                ].map(card => ( 
                  <div key={card.label} style={{ 
                    background:'var(--bg-surface)', 
                    border:'1px solid var(--border)', 
                    borderRadius:'10px', 
                    padding:'20px', 
                    boxShadow:'var(--shadow-sm)', 
                    position:'relative', 
                    overflow:'hidden' 
                  }}> 
                    <div style={{ 
                      position:'absolute', left:0, 
                      top:0, bottom:0, width:'3px', 
                      background: card.color, 
                      borderRadius:'10px 0 0 10px' 
                    }}/> 
                    <div style={{ 
                      fontSize:'10px', fontWeight:'600', 
                      letterSpacing:'0.1em', 
                      textTransform:'uppercase', 
                      color:'var(--text-muted)', 
                      marginBottom:'8px' 
                    }}>{card.label}</div> 
                    <div style={{ 
                      fontSize:'40px', fontWeight:'700', 
                      color: card.color, lineHeight:1, 
                      fontFamily:"'IBM Plex Mono',monospace", 
                      letterSpacing:'-0.02em', 
                      marginBottom:'8px' 
                    }}>{card.value}</div> 
                    <div style={{ 
                      fontSize:'12px', 
                      color:'var(--text-muted)' 
                    }}>{card.sub}</div> 
                  </div> 
                ))} 
              </div> 
          
              {/* Chart card */} 
              <div style={{ 
                background:'var(--bg-surface)', 
                border:'1px solid var(--border)', 
                borderRadius:'10px', 
                boxShadow:'var(--shadow-sm)', 
                overflow:'hidden' 
              }}> 
                <div style={{ 
                  padding:'20px 24px 0', 
                  display:'flex', 
                  justifyContent:'space-between', 
                  alignItems:'flex-start' 
                }}> 
                  <div> 
                    <div style={{ 
                      fontSize:'10px', fontWeight:'600', 
                      letterSpacing:'0.1em', 
                      textTransform:'uppercase', 
                      color:'var(--text-muted)', 
                      marginBottom:'4px' 
                    }}>ALERT TREND</div> 
                    <div style={{ 
                      fontSize:'18px', fontWeight:'700', 
                      color:'var(--text-primary)', 
                      letterSpacing:'-0.02em' 
                    }}>Last 30 days</div> 
                  </div> 
                  <div style={{ 
                    display:'flex', gap:'20px', 
                    alignItems:'center' 
                  }}> 
                    {[ 
                      {c:'var(--critical)',l:'Critical'}, 
                      {c:'var(--high)',l:'High'}, 
                      {c:'var(--medium)',l:'Medium'}, 
                    ].map(item => ( 
                      <span key={item.l} style={{ 
                        display:'flex', alignItems:'center', 
                        gap:'6px', fontSize:'12px', 
                        color:'var(--text-secondary)' 
                      }}> 
                        <span style={{ 
                          display:'inline-block', 
                          width:'20px', height:'2px', 
                          background: item.c, 
                          borderRadius:'2px' 
                        }}/> 
                        {item.l} 
                      </span> 
                    ))} 
                  </div> 
                </div> 
          
                <div style={{ 
                  padding:'16px 24px', 
                  height:'220px', position:'relative' 
                }}> 
                  {digest.length === 0 ? ( 
                    <div style={{ 
                      display:'flex', alignItems:'center', 
                      justifyContent:'center', height:'100%', 
                      color:'var(--text-muted)', fontSize:'13px' 
                    }}>Loading chart data...</div> 
                  ) : ( 
                    <canvas ref={chartRef} 
                      style={{width:'100%', height:'100%'}}/> 
                  )} 
                </div> 
          
                <div style={{ 
                  borderTop:'1px solid var(--border)', 
                  padding:'12px 24px', 
                  display:'grid', 
                  gridTemplateColumns:'repeat(4,1fr)' 
                }}> 
                  {[ 
                    {label:'Monitoring', 
                     value:'SentinelEHR Demo'}, 
                    {label:'Employees', 
                     value: summary 
                       ?.total_employees_monitored ?? 80}, 
                    {label:'Active Signals', 
                     value: summary?.total_active ?? '—'}, 
                    {label:'Range', 
                     value: summary?.date_range 
                       ? `${summary.date_range.start} – ${summary.date_range.end}` 
                       : 'Jan 5 – Mar 31'} 
                  ].map(s => ( 
                    <div key={s.label} style={{ 
                      textAlign:'center', 
                      borderRight:'1px solid var(--border)', 
                      padding:'0 16px', 
                      '&:last-child': {borderRight:'none'} 
                    }}> 
                      <div style={{ 
                        fontSize:'11px', 
                        color:'var(--text-muted)', 
                        marginBottom:'2px' 
                      }}>{s.label}</div> 
                      <div style={{ 
                        fontSize:'12px', fontWeight:'600', 
                        color:'var(--text-secondary)', 
                        fontFamily:"'IBM Plex Mono',monospace" 
                      }}>{s.value}</div> 
                    </div> 
                  ))} 
                </div> 
              </div> 
            </div> 
          )} 
          
          {activeView !== 'overview' && ( 
            <div style={{ 
              display:'flex', alignItems:'center', 
              justifyContent:'center', height:'60vh', 
              color:'var(--text-muted)', fontSize:'13px', 
              fontFamily:"'IBM Plex Mono',monospace" 
            }}> 
              {activeView} — coming in Phase 3 
            </div> 
          )}
        </div>
      </main>

      <style>{`
        @keyframes pulse {
          0% { opacity: 1; }
          50% { opacity: 0.4; }
          100% { opacity: 1; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
