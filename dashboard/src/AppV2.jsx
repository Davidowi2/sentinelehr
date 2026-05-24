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

  const [alerts, setAlerts] = useState([]) 
  const [alertsTotal, setAlertsTotal] = useState(0) 
  const [alertsLoading, setAlertsLoading] = useState(false) 
  const [alertSeverity, setAlertSeverity] = useState('') 
  const [alertStatus, setAlertStatus] = useState('') 
  const [alertsOffset, setAlertsOffset] = useState(0) 
  const [selectedAlert, setSelectedAlert] = useState(null) 
  const [alertDetail, setAlertDetail] = useState(null) 
  const [alertNote, setAlertNote] = useState('') 
  const [alertStatusUpdate, setAlertStatusUpdate] = useState('') 
  const [savingAlert, setSavingAlert] = useState(false) 
  
  const [cases, setCases] = useState([]) 
  const [casesTotal, setCasesTotal] = useState(0) 
  const [casesLoading, setCasesLoading] = useState(false) 
  const [caseStatusFilter, setCaseStatusFilter] = useState('Open') 
  const [casePriorityFilter, setCasePriorityFilter] = useState('') 
  const [casesOffset, setCasesOffset] = useState(0) 
  const [selectedCase, setSelectedCase] = useState(null) 
  const [caseDetail, setCaseDetail] = useState(null) 
  const [caseNote, setCaseNote] = useState('') 
  const [caseStatusUpdate, setCaseStatusUpdate] = useState('') 
  const [caseOutcome, setCaseOutcome] = useState('') 
  const [savingCase, setSavingCase] = useState(false) 
  
  const LIMIT = 50 

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
  
  const fetchAlerts = async () => { 
    if (!token) return 
    setAlertsLoading(true) 
    try { 
      const query = new URLSearchParams({ 
        limit: LIMIT, 
        offset: alertsOffset, 
        severity: alertSeverity, 
        status: alertStatus 
      }) 
      const res = await fetch(`${API_BASE}/alerts?${query}`, { 
        headers: authHeaders() 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        setAlerts(data.alerts || []) 
        setAlertsTotal(data.total || 0) 
      } 
    } catch(e) { console.error(e) } 
    setAlertsLoading(false) 
  } 
  
  const fetchAlertDetail = async (id) => { 
    try { 
      const res = await fetch(`${API_BASE}/alerts/${id}`, { 
        headers: authHeaders() 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        setAlertDetail(data) 
        setAlertStatusUpdate(data.status) 
        setAlertNote(data.reviewer_notes || '') 
      } 
    } catch(e) { console.error(e) } 
  } 
  
  const saveAlertUpdate = async () => { 
    if (!selectedAlert) return 
    setSavingAlert(true) 
    try { 
      const res = await fetch(`${API_BASE}/alerts/${selectedAlert}/status`, { 
        method: 'PATCH', 
        headers: authHeaders(), 
        body: JSON.stringify({ 
          status: alertStatusUpdate, 
          reviewer_notes: alertNote 
        }) 
      }) 
      if (res.ok) { 
        await fetchAlertDetail(selectedAlert) 
        fetchAlerts() 
      } 
    } catch(e) { console.error(e) } 
    setSavingAlert(false) 
  } 
  
  const fetchCases = async () => { 
    if (!token) return 
    setCasesLoading(true) 
    try { 
      const query = new URLSearchParams({ 
        limit: LIMIT, 
        offset: casesOffset, 
        status: caseStatusFilter, 
        priority: casePriorityFilter 
      }) 
      const res = await fetch(`${API_BASE}/cases?${query}`, { 
        headers: authHeaders() 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        setCases(data.cases || []) 
        setCasesTotal(data.total || 0) 
      } 
    } catch(e) { console.error(e) } 
    setCasesLoading(false) 
  } 
  
  const fetchCaseDetail = async (id) => { 
    try { 
      const res = await fetch(`${API_BASE}/cases/${id}`, { 
        headers: authHeaders() 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        setCaseDetail(data) 
        setCaseStatusUpdate(data.status) 
        setCaseOutcome(data.outcome || '') 
        setCaseNote('') 
      } 
    } catch(e) { console.error(e) } 
  } 
  
  const saveCaseUpdate = async () => { 
    if (!selectedCase) return 
    setSavingCase(true) 
    try { 
      if (caseStatusUpdate !== caseDetail.status) { 
        await fetch(`${API_BASE}/cases/${selectedCase}/status`, { 
          method: 'PATCH', 
          headers: authHeaders(), 
          body: JSON.stringify({ 
            status: caseStatusUpdate, 
            note: caseNote || 'Status updated' 
          }) 
        }) 
      } 
      if (caseOutcome && caseOutcome !== caseDetail.outcome) { 
        await fetch(`${API_BASE}/cases/${selectedCase}/outcome`, { 
          method: 'PATCH', 
          headers: authHeaders(), 
          body: JSON.stringify({ outcome: caseOutcome }) 
        }) 
      } 
      if (caseNote.trim()) { 
        await fetch(`${API_BASE}/cases/${selectedCase}/notes`, { 
          method: 'POST', 
          headers: authHeaders(), 
          body: JSON.stringify({ note: caseNote }) 
        }) 
      } 
      await fetchCaseDetail(selectedCase) 
      fetchCases() 
    } catch(e) { console.error(e) } 
    setSavingCase(false) 
  } 
  
  useEffect(() => { 
    if (token && activeView === 'overview') { 
      fetchOverviewData() 
    } 
  }, [token, activeView]);

  useEffect(() => { 
    if (token && activeView === 'alerts') fetchAlerts() 
  }, [token, activeView, alertSeverity, alertStatus, alertsOffset]) 
  
  useEffect(() => { 
    if (token && activeView === 'cases') fetchCases() 
  }, [token, activeView, caseStatusFilter, casePriorityFilter, casesOffset]) 

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

  const SeverityBadge = ({ severity }) => { 
    const colors = { 
      'Critical': { main: 'var(--critical)', bg: 'var(--critical-bg)' }, 
      'High': { main: 'var(--high)', bg: 'var(--high-bg)' }, 
      'Medium': { main: 'var(--medium)', bg: 'var(--medium-bg)' }, 
      'Low': { main: 'var(--text-muted)', bg: 'var(--bg-elevated)' } 
    }[severity] || { main: 'var(--text-muted)', bg: 'var(--bg-elevated)' }; 
    return ( 
      <span style={{ 
        padding: '2px 8px', borderRadius: '20px', fontSize: '11px', 
        fontWeight: '600', textTransform: 'uppercase', 
        color: colors.main, background: colors.bg, 
        border: `1px solid ${colors.main}40` 
      }}>{severity}</span> 
    ); 
  }; 
  
  const FilterBar = ({ children, count, total }) => ( 
    <div style={{ 
      background: 'var(--bg-surface)', borderRadius: '10px', 
      border: '1px solid var(--border)', padding: '16px 20px', 
      marginBottom: '16px', display: 'flex', alignItems: 'flex-end', gap: '20px' 
    }}> 
      {children} 
      <div style={{ 
        marginLeft: 'auto', fontSize: '12px', color: 'var(--text-muted)', 
        fontFamily: "'IBM Plex Mono', monospace" 
      }}>{count} of {total}</div> 
    </div> 
  ); 
  
  const FilterLabel = ({ label, children }) => ( 
    <div> 
      <div style={{ 
        fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', 
        textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' 
      }}>{label}</div> 
      {children} 
    </div> 
  ); 
  
  const Select = (props) => ( 
    <select {...props} style={{ 
      background: 'var(--bg-elevated)', border: '1px solid var(--border)', 
      borderRadius: '6px', padding: '8px 12px', fontSize: '13px', 
      color: 'var(--text-primary)', fontFamily: "'IBM Plex Mono', monospace", 
      outline: 'none', minWidth: '140px' 
    }} /> 
  ); 
  
  const TableCard = ({ children }) => ( 
    <div style={{ 
      background: 'var(--bg-surface)', borderRadius: '10px', 
      border: '1px solid var(--border)', boxShadow: 'var(--shadow)', 
      overflow: 'hidden' 
    }}>{children}</div> 
  ); 
  
  const TH = ({ children }) => ( 
    <th style={{ 
      padding: '12px 16px', textAlign: 'left', fontSize: '10px', 
      fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', 
      color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' 
    }}>{children}</th> 
  ); 
  
  const Drawer = ({ title, subtitle, id, onClose, children, loading }) => ( 
    <> 
      <div onClick={onClose} style={{ 
        position: 'fixed', inset: 0, background: 'rgba(10,14,26,0.5)', 
        backdropFilter: 'blur(4px)', zIndex: 100 
      }} /> 
      <div style={{ 
        position: 'fixed', top: 0, right: 0, width: '480px', height: '100vh', 
        background: 'var(--bg-surface)', borderLeft: '1px solid var(--border)', 
        boxShadow: '-8px 0 40px rgba(0,0,0,0.4)', zIndex: 101, overflowY: 'auto', 
        display: 'flex', flexDirection: 'column' 
      }}> 
        <div style={{ 
          background: 'var(--bg-elevated)', padding: '24px', 
          borderBottom: '1px solid var(--border)', flexShrink: 0 
        }}> 
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}> 
            <div> 
              <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>{title}</div> 
              <div style={{ fontSize: '22px', fontWeight: '700', fontFamily: "'IBM Plex Mono', monospace", color: 'var(--accent)' }}>{id}</div> 
              {subtitle && <div style={{ marginTop: '8px' }}>{subtitle}</div>} 
            </div> 
            <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}><LogOut size={20} /></button> 
          </div> 
        </div> 
        <div style={{ padding: '24px', flex: 1 }}> 
          {loading ? <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>Loading...</div> : children} 
        </div> 
      </div> 
    </> 
  ); 
  
  const StatusButtons = ({ options, current, onChange }) => ( 
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}> 
      {options.map(s => { 
        const isActive = current === s; 
        return ( 
          <button key={s} onClick={() => onChange(s)} style={{ 
            padding: '6px 14px', borderRadius: '20px', fontSize: '12px', 
            fontWeight: '600', cursor: 'pointer', 
            border: isActive ? `2px solid var(--accent)` : '1px solid var(--border)', 
            background: isActive ? 'var(--accent-subtle)' : 'var(--bg-elevated)', 
            color: isActive ? 'var(--accent)' : 'var(--text-secondary)', 
            transition: 'all 0.2s' 
          }}>{s}</button> 
        ); 
      })} 
    </div> 
  ); 

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
          
          {activeView === 'alerts' && ( 
            <div> 
              <FilterBar count={alerts.length} total={alertsTotal}> 
                <FilterLabel label="Severity"> 
                  <Select value={alertSeverity} onChange={e => {setAlertSeverity(e.target.value); setAlertsOffset(0)}}> 
                    <option value="">All</option> 
                    <option value="Critical">Critical</option> 
                    <option value="High">High</option> 
                    <option value="Medium">Medium</option> 
                  </Select> 
                </FilterLabel> 
                <FilterLabel label="Status"> 
                  <Select value={alertStatus} onChange={e => {setAlertStatus(e.target.value); setAlertsOffset(0)}}> 
                    <option value="">All</option> 
                    <option value="open">Open</option> 
                    <option value="investigating">Investigating</option> 
                    <option value="resolved">Resolved</option> 
                  </Select> 
                </FilterLabel> 
              </FilterBar> 
        
              <TableCard> 
                <table style={{ width: '100%', borderCollapse: 'collapse' }}> 
                  <thead> 
                    <tr style={{ background: 'var(--bg-elevated)' }}> 
                      <TH>#</TH> 
                      <TH>Severity</TH> 
                      <TH>Employee</TH> 
                      <TH>Rules</TH> 
                      <TH>Score</TH> 
                      <TH>Date</TH> 
                      <TH>Explanation</TH> 
                      <TH>Action</TH> 
                    </tr> 
                  </thead> 
                  <tbody> 
                    {alertsLoading ? <tr><td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>Loading alerts...</td></tr> : 
                     alerts.map(a => ( 
                      <tr key={a.alert_id} style={{ borderBottom: '1px solid var(--border)' }}> 
                        <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace" }}>{a.priority_rank}</td> 
                        <td style={{ padding: '12px 16px' }}><SeverityBadge severity={a.adjusted_severity} /></td> 
                        <td style={{ padding: '12px 16px', fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', fontFamily: "'IBM Plex Mono', monospace" }}>EMP-{a.emp_id}</td> 
                        <td style={{ padding: '12px 16px' }}> 
                          {a.rules_triggered.split(',').map(r => ( 
                            <span key={r} style={{ fontSize: '10px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', padding: '2px 6px', borderRadius: '4px', marginRight: '4px', color: 'var(--text-secondary)' }}>{r}</span> 
                          ))} 
                        </td> 
                        <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--accent)', fontWeight: '600', fontFamily: "'IBM Plex Mono', monospace" }}>{a.anomaly_score.toFixed(2)}</td> 
                        <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-secondary)' }}>{new Date(a.alert_date).toLocaleDateString()}</td> 
                        <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-muted)', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.explanation}>{a.explanation}</td> 
                        <td style={{ padding: '12px 16px' }}> 
                          <button onClick={() => {setSelectedAlert(a.alert_id); fetchAlertDetail(a.alert_id)}} style={{ padding: '6px 12px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '11px', fontWeight: '600', cursor: 'pointer' }}>REVIEW</button> 
                        </td> 
                      </tr> 
                    ))} 
                  </tbody> 
                </table> 
                {alertsTotal > LIMIT && ( 
                  <div style={{ padding: '16px', borderTop: '1px solid var(--border)', display: 'flex', gap: '8px' }}> 
                    <button onClick={() => setAlertsOffset(Math.max(0, alertsOffset - LIMIT))} disabled={alertsOffset === 0} style={{ padding: '6px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer', opacity: alertsOffset === 0 ? 0.5 : 1 }}>Previous</button> 
                    <button onClick={() => setAlertsOffset(alertsOffset + LIMIT)} disabled={alertsOffset + LIMIT >= alertsTotal} style={{ padding: '6px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer', opacity: alertsOffset + LIMIT >= alertsTotal ? 0.5 : 1 }}>Next</button> 
                  </div> 
                )} 
              </TableCard> 
        
              {selectedAlert && ( 
                <Drawer title="Alert Review" id={`ALT-${selectedAlert}`} onClose={() => setSelectedAlert(null)} loading={!alertDetail}> 
                  {alertDetail && ( 
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Explanation</div> 
                        <div style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.6', background: 'var(--bg-elevated)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)' }}>{alertDetail.explanation}</div> 
                      </div> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Update Status</div> 
                        <StatusButtons options={['open', 'investigating', 'resolved']} current={alertStatusUpdate} onChange={setAlertStatusUpdate} /> 
                      </div> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Notes</div> 
                        <textarea value={alertNote} onChange={e => setAlertNote(e.target.value)} style={{ width: '100%', minHeight: '100px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', color: 'var(--text-primary)', fontSize: '13px', outline: 'none' }} placeholder="Add investigation notes..." /> 
                      </div> 
                      <button onClick={saveAlertUpdate} disabled={savingAlert} style={{ width: '100%', padding: '14px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', cursor: 'pointer', opacity: savingAlert ? 0.7 : 1 }}> 
                        {savingAlert ? 'Saving...' : 'Save Changes'} 
                      </button> 
                    </div> 
                  )} 
                </Drawer> 
              )} 
            </div> 
          )} 
        
          {activeView === 'cases' && ( 
            <div> 
              <FilterBar count={cases.length} total={casesTotal}> 
                <FilterLabel label="Status"> 
                  <Select value={caseStatusFilter} onChange={e => {setCaseStatusFilter(e.target.value); setCasesOffset(0)}}> 
                    <option value="">All</option> 
                    <option value="Open">Open</option> 
                    <option value="Under Investigation">Under Investigation</option> 
                    <option value="Pending HR">Pending HR</option> 
                    <option value="Resolved">Resolved</option> 
                  </Select> 
                </FilterLabel> 
                <FilterLabel label="Priority"> 
                  <Select value={casePriorityFilter} onChange={e => {setCasePriorityFilter(e.target.value); setCasesOffset(0)}}> 
                    <option value="">All</option> 
                    <option value="Critical">Critical</option> 
                    <option value="High">High</option> 
                    <option value="Medium">Medium</option> 
                  </Select> 
                </FilterLabel> 
              </FilterBar> 
        
              <TableCard> 
                <table style={{ width: '100%', borderCollapse: 'collapse' }}> 
                  <thead> 
                    <tr style={{ background: 'var(--bg-elevated)' }}> 
                      <TH>Case ID</TH> 
                      <TH>Employee</TH> 
                      <TH>Priority</TH> 
                      <TH>Status</TH> 
                      <TH>Days Open</TH> 
                      <TH>Alerts</TH> 
                      <TH>Window</TH> 
                      <TH>Assigned</TH> 
                    </tr> 
                  </thead> 
                  <tbody> 
                    {casesLoading ? <tr><td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>Loading cases...</td></tr> : 
                     cases.map(c => ( 
                      <tr key={c.case_id} onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'} onMouseLeave={e => e.currentTarget.style.background = 'transparent'}> 
                        <td style={{ padding: '12px 16px', fontSize: '13px', fontWeight: '700', color: 'var(--accent)', fontFamily: "'IBM Plex Mono', monospace" }}>{c.case_id}</td> 
                        <td style={{ padding: '12px 16px', fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)', fontFamily: "'IBM Plex Mono', monospace" }}>EMP-{c.emp_id}</td> 
                        <td style={{ padding: '12px 16px' }}><SeverityBadge severity={c.priority} /></td> 
                        <td style={{ padding: '12px 16px' }}> 
                          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)' }}> 
                            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: c.status === 'Open' ? 'var(--critical)' : c.status === 'Resolved' ? 'var(--success)' : 'var(--warning)' }} /> 
                            {c.status} 
                          </span> 
                        </td> 
                        <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--text-secondary)', fontFamily: "'IBM Plex Mono', monospace" }}>{c.days_open || 0}d</td> 
                        <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--text-secondary)', fontFamily: "'IBM Plex Mono', monospace" }}>{Array.isArray(c.alert_ids) ? c.alert_ids.length : 0}</td> 
                        <td style={{ padding: '12px 16px', fontSize: '11px', color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace" }}> 
                          {new Date(c.window_start).toLocaleDateString()}<br/> 
                          to {new Date(c.window_end).toLocaleDateString()} 
                        </td> 
                        <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-muted)' }}>{c.assigned_to_name || '—'}</td> 
                      </tr> 
                    ))} 
                  </tbody> 
                </table> 
                {casesTotal > LIMIT && ( 
                  <div style={{ padding: '16px', borderTop: '1px solid var(--border)', display: 'flex', gap: '8px' }}> 
                    <button onClick={() => setCasesOffset(Math.max(0, casesOffset - LIMIT))} disabled={casesOffset === 0} style={{ padding: '6px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer', opacity: casesOffset === 0 ? 0.5 : 1 }}>Previous</button> 
                    <button onClick={() => setCasesOffset(casesOffset + LIMIT)} disabled={casesOffset + LIMIT >= casesTotal} style={{ padding: '6px 12px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer', opacity: casesOffset + LIMIT >= casesTotal ? 0.5 : 1 }}>Next</button> 
                  </div> 
                )} 
              </TableCard> 
        
              {selectedCase && ( 
                <Drawer title="Case Investigation" id={selectedCase} onClose={() => setSelectedCase(null)} loading={!caseDetail} subtitle={caseDetail && <SeverityBadge severity={caseDetail.priority} />}> 
                  {caseDetail && ( 
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Update Status</div> 
                        <StatusButtons options={['Open', 'Under Investigation', 'Pending HR', 'Resolved']} current={caseStatusUpdate} onChange={setCaseStatusUpdate} /> 
                      </div> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Outcome</div> 
                        <Select value={caseOutcome} onChange={e => setCaseOutcome(e.target.value)} style={{ width: '100%' }}> 
                          <option value="">— Not set —</option> 
                          <option>Legitimate Access</option> 
                          <option>Policy Violation</option> 
                          <option>Training Required</option> 
                          <option>Termination Recommended</option> 
                        </Select> 
                      </div> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Add Note</div> 
                        <textarea value={caseNote} onChange={e => setCaseNote(e.target.value)} style={{ width: '100%', minHeight: '80px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', color: 'var(--text-primary)', fontSize: '13px', outline: 'none' }} placeholder="Add investigation notes..." /> 
                      </div> 
                      <button onClick={saveCaseUpdate} disabled={savingCase} style={{ width: '100%', padding: '14px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', cursor: 'pointer', opacity: savingCase ? 0.7 : 1 }}> 
                        {savingCase ? 'Saving...' : 'Save Changes'} 
                      </button> 
        
                      {caseDetail.audit_log && caseDetail.audit_log.length > 0 && ( 
                        <div style={{ marginTop: '12px' }}> 
                          <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '12px' }}>Audit Trail</div> 
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}> 
                            {caseDetail.audit_log.map((log, i) => ( 
                              <div key={i} style={{ padding: '12px', background: 'var(--bg-elevated)', borderRadius: '8px', borderLeft: '3px solid var(--border)', fontSize: '12px' }}> 
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}> 
                                  <span style={{ fontWeight: '700', color: 'var(--text-primary)', textTransform: 'uppercase', fontSize: '10px' }}>{log.action}</span> 
                                  <span style={{ color: 'var(--text-muted)', fontFamily: "'IBM Plex Mono', monospace", fontSize: '10px' }}>{new Date(log.timestamp).toLocaleString()}</span> 
                                </div> 
                                <div style={{ color: 'var(--text-secondary)' }}>{log.note}</div> 
                                <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>by {log.changed_by_name}</div> 
                              </div> 
                            ))} 
                          </div> 
                        </div> 
                      )} 
                    </div> 
                  )} 
                </Drawer> 
              )} 
            </div> 
          )} 
        
          {(activeView === 'investigate' || activeView === 'settings') && ( 
            <div style={{ 
              display:'flex', alignItems:'center', 
              justifyContent:'center', height:'60vh', 
              color:'var(--text-muted)', fontSize:'13px', 
              fontFamily:"'IBM Plex Mono',monospace" 
            }}> 
              {activeView} — coming in Phase 4 
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
