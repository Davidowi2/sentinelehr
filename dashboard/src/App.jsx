import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const params = new URLSearchParams(window.location.search);
const ORG_NAME = params.get('org') || "SentinelEHR Demo";
const ORG_SUBTITLE = "Central Texas Community Health Centers";

const App = () => {
  const [token, setToken] = useState( 
    localStorage.getItem('sentinel_token') || null 
  ) 
  const [loginError, setLoginError] = useState('') 
  const [loginForm, setLoginForm] = useState( 
    { username: '', password: '' } 
  ) 

  const handleLogin = async (e) => { 
    e.preventDefault() 
    try { 
      const res = await fetch(`${API_BASE}/login`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify(loginForm) 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        localStorage.setItem('sentinel_token', 
          data.access_token) 
        setToken(data.access_token) 
        setLoginError('') 
      } else { 
        setLoginError('Incorrect username or password') 
      } 
    } catch { 
      setLoginError('Cannot connect to server') 
    } 
  } 

  const handleLogout = () => { 
    localStorage.removeItem('sentinel_token') 
    setToken(null) 
  } 

  const [activeTab, setActiveTab] = useState('OVERVIEW');
  const [apiStatus, setApiStatus] = useState('connecting');
  const [summary, setSummary] = useState(null);
  const [digest, setDigest] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [alertOffset, setAlertOffset] = useState(0);
  const [totalAlerts, setTotalAlerts] = useState(0);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [filters, setFilters] = useState({ severity: '', status: '' });
  const [investigateId, setInvestigateId] = useState('');
  const [profile, setProfile] = useState(null);
  const [profileAlerts, setProfileAlerts] = useState([]);
  const [loading, setLoading] = useState(false);

  // Health check & Summary
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await axios.get(`${API_BASE}/health`);
        setApiStatus(res.data.status === 'ok' ? 'live' : 'error');
      } catch (e) {
        setApiStatus('error');
      }
    };
    
    const fetchSummary = async () => {
      if (!token) return;
      try {
        const res = await axios.get(`${API_BASE}/summary`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        setSummary(res.data);
      } catch (e) {}
    };

    checkHealth();
    fetchSummary();
    const interval = setInterval(() => {
      checkHealth();
      fetchSummary();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Digest for Overview
  useEffect(() => {
    if (activeTab === 'OVERVIEW' && token) {
      axios.get(`${API_BASE}/digest?days=30`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).then(res => setDigest(res.data));
    }
  }, [activeTab, token]);

  // Alerts View
  useEffect(() => {
    if (activeTab === 'ALERTS') {
      fetchAlerts(true);
    }
  }, [activeTab, filters]);

  const fetchAlerts = async (reset = false) => {
    if (!token) return;
    setLoading(true);
    const offset = reset ? 0 : alertOffset;
    const url = `${API_BASE}/alerts?limit=50&offset=${offset}${filters.severity ? `&severity=${filters.severity}` : ''}${filters.status ? `&status=${filters.status}` : ''}`;
    try {
      const res = await axios.get(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (reset) {
        setAlerts(res.data.alerts);
        setAlertOffset(50);
      } else {
        setAlerts([...alerts, ...res.data.alerts]);
        setAlertOffset(offset + 50);
      }
      setTotalAlerts(res.data.total_count);
    } catch (e) {}
    setLoading(false);
  };

  const handleUpdateStatus = async (id, data) => {
    try {
      await axios.patch(`${API_BASE}/alerts/${id}/status`, data, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      setDrawerOpen(false);
      fetchAlerts(true);
    } catch (e) {
      alert("Error updating alert");
    }
  };

  const handleLookup = async (idToLookup) => {
    const id = idToLookup || investigateId;
    if (!id || !token) return;
    setLoading(true);
    try {
      const profileRes = await axios.get(`${API_BASE}/employees/${id}/profile`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      setProfile(profileRes.data);
      
      const alertsRes = await axios.get(`${API_BASE}/alerts?limit=200`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const filtered = alertsRes.data.alerts.filter(a => a.emp_id === parseInt(id));
      setProfileAlerts(filtered);
      if (!idToLookup) setInvestigateId(id);
    } catch (e) {
      setProfile(null);
      alert("Employee not found or access denied");
    }
    setLoading(false);
  };

  const getSeverityColors = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return { main: 'var(--critical)', bg: 'var(--critical-bg)' };
      case 'high': return { main: 'var(--high)', bg: 'var(--high-bg)' };
      case 'medium': return { main: 'var(--medium)', bg: 'var(--medium-bg)' };
      default: return { main: 'var(--text-muted)', bg: 'var(--bg-elevated)' };
    }
  };

  const formatDateTime = (alert) => {
    if (alert.action_datetime) {
      return alert.action_datetime.substring(0, 16);
    }
    return alert.alert_date;
  };

  if (!token) { 
    return ( 
      <div style={{ 
        minHeight: '100vh', 
        background: '#EEF2FF', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        fontFamily: "'DM Sans', sans-serif" 
      }}> 
        <div style={{ 
          background: '#fff', 
          borderRadius: '12px', 
          border: '1px solid #E2E8F4', 
          boxShadow: '0 4px 24px rgba(15,23,42,0.10)', 
          padding: '40px', 
          width: '360px' 
        }}> 
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '10px', 
            marginBottom: '6px' 
          }}> 
            <div style={{ 
              width: '32px', height: '32px', 
              background: '#FFF1F3', 
              borderRadius: '8px', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              fontSize: '16px' 
            }}>🛡</div> 
            <span style={{ 
              fontWeight: 600, 
              fontSize: '18px', 
              color: '#0F172A' 
            }}>SentinelEHR</span> 
          </div> 
          <p style={{ 
            fontSize: '12px', 
            color: '#94A3B8', 
            marginBottom: '28px', 
            marginTop: '2px' 
          }}>EHR Privacy Monitoring System</p> 

          <form onSubmit={handleLogin}> 
            <div style={{ marginBottom: '16px' }}> 
              <label style={{ 
                display: 'block', 
                fontSize: '11px', 
                fontWeight: '500', 
                letterSpacing: '0.08em', 
                textTransform: 'uppercase', 
                color: '#64748B', 
                marginBottom: '6px' 
              }}>Username</label> 
              <input 
                type="text" 
                value={loginForm.username} 
                onChange={e => setLoginForm({ 
                  ...loginForm, username: e.target.value 
                })} 
                placeholder="Enter username" 
                style={{ 
                  width: '100%', 
                  padding: '10px 12px', 
                  border: '1px solid #E2E8F4', 
                  borderRadius: '8px', 
                  fontSize: '14px', 
                  color: '#0F172A', 
                  background: '#FAFBFF', 
                  boxSizing: 'border-box', 
                  outline: 'none', 
                  fontFamily: "'IBM Plex Mono', monospace" 
                }} 
              /> 
            </div> 

            <div style={{ marginBottom: '20px' }}> 
              <label style={{ 
                display: 'block', 
                fontSize: '11px', 
                fontWeight: '500', 
                letterSpacing: '0.08em', 
                textTransform: 'uppercase', 
                color: '#64748B', 
                marginBottom: '6px' 
              }}>Password</label> 
              <input 
                type="password" 
                value={loginForm.password} 
                onChange={e => setLoginForm({ 
                  ...loginForm, password: e.target.value 
                })} 
                placeholder="Enter password" 
                style={{ 
                  width: '100%', 
                  padding: '10px 12px', 
                  border: '1px solid #E2E8F4', 
                  borderRadius: '8px', 
                  fontSize: '14px', 
                  color: '#0F172A', 
                  background: '#FAFBFF', 
                  boxSizing: 'border-box', 
                  outline: 'none', 
                  fontFamily: "'IBM Plex Mono', monospace" 
                }} 
              /> 
            </div> 

            {loginError && ( 
              <p style={{ 
                color: '#E11D48', 
                fontSize: '13px', 
                marginBottom: '16px', 
                marginTop: '-8px' 
              }}>{loginError}</p> 
            )}

            <button type="submit" style={{ 
              width: '100%', 
              padding: '12px', 
              background: '#E11D48', 
              color: '#fff', 
              border: 'none', 
              borderRadius: '8px', 
              fontSize: '12px', 
              fontWeight: '600', 
              letterSpacing: '0.08em', 
              textTransform: 'uppercase', 
              cursor: 'pointer', 
              fontFamily: "'DM Sans', sans-serif" 
            }}>Sign In →</button> 
          </form> 
        </div> 
      </div> 
    ) 
  }

  return (
    <div className="app-container">
      <header className="header">
        <div className="brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="var(--critical)">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" />
          </svg>
          <div className="brand-text-container">
            <h1 className="brand-title">SentinelEHR</h1>
            <span className="brand-subtitle">EHR Privacy Monitoring</span>
          </div>
        </div>
        <div className="header-divider"></div>
        <div className="header-version">v1.0 · Prototype</div>
        <div className="api-status">
          <div className={`status-dot ${apiStatus}`}></div>
          <span className="status-text">{apiStatus.toUpperCase()}</span>
          <button onClick={handleLogout} style={{ 
            background: 'transparent', 
            border: '1px solid #E2E8F4', 
            borderRadius: '6px', 
            padding: '4px 12px', 
            fontSize: '11px', 
            color: '#94A3B8', 
            cursor: 'pointer', 
            fontFamily: "'IBM Plex Mono', monospace", 
            letterSpacing: '0.06em', 
            marginLeft: '12px' 
          }}>SIGN OUT</button> 
        </div>
      </header>

      <nav className="nav-tabs">
        {['OVERVIEW', 'ALERTS', 'INVESTIGATE'].map(tab => (
          <button 
            key={tab} 
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <main className="main-content">
        {activeTab === 'OVERVIEW' && (
          <div className="view-overview">
            <div className="stats-grid">
              {[
                { label: 'Critical Threats', key: 'critical', sub: 'Require immediate action' },
                { label: 'High Risk', key: 'high', sub: 'ML-elevated alerts' },
                { label: 'Medium Risk', key: 'medium', sub: 'Under observation' },
                { label: 'ML Score', key: 'ml', sub: 'Highest anomaly detected', peak: true }
              ].map(stat => {
                const val = stat.key === 'ml' ? summary?.top_anomaly_score : summary?.[stat.key];
                const pct = summary?.total_active ? Math.round((summary[stat.key] / summary.total_active) * 100) : 0;
                const colors = getSeverityColors(stat.key === 'ml' ? 'ml' : stat.key);
                
                return (
                  <div key={stat.key} className="stat-card" style={{ '--accent-color': colors.main }}>
                    <div className="stat-label">{stat.label}</div>
                    <div className="stat-meta">
                      <span className="stat-pct" style={{ color: colors.main }}>
                        {stat.peak ? '90-DAY PEAK' : `${pct}%`}
                      </span>
                      {!stat.peak && <span className="stat-pct-label">of active alerts</span>}
                    </div>
                    <div className="stat-value" style={{ color: colors.main }}>
                      {stat.key === 'ml' ? val?.toFixed(2) || '0.00' : val || 0}
                    </div>
                    <div className="stat-sublabel">{stat.sub}</div>
                  </div>
                );
              })}
            </div>

            <div className="chart-card">
              <div className="chart-header">
                <div className="chart-title-group">
                  <span className="chart-title">ALERT TREND</span>
                  <span className="chart-subtitle">Last 30 days</span>
                </div>
                <div className="chart-legend">
                  <div className="legend-item"><div className="legend-dot" style={{ backgroundColor: 'var(--critical)' }}></div><span>Critical (red)</span></div>
                  <div className="legend-item"><div className="legend-dot" style={{ backgroundColor: 'var(--high)' }}></div><span>High (amber)</span></div>
                  <div className="legend-item"><div className="legend-dot" style={{ backgroundColor: 'var(--medium)' }}></div><span>Medium (blue)</span></div>
                  <div className="legend-item"><div className="legend-line" style={{ borderTop: '2px dashed #94A3B8', width: '16px', marginRight: '8px' }}></div><span style={{ color: '#94A3B8' }}>--- Threshold (dashed gray)</span></div>
                </div>
              </div>
              <div className="chart-body">
                <div style={{ width: '100%', height: 300 }}>
                  <ResponsiveContainer>
                    <LineChart data={[...digest].reverse()}>
                      <CartesianGrid vertical={false} stroke="#EEF2FF" strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="alert_date" 
                        axisLine={false} 
                        tickLine={false} 
                        stroke="var(--text-muted)" 
                        fontSize={10} 
                        tickFormatter={(str) => {
                          const date = new Date(str);
                          return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                        }}
                      />
                      <YAxis axisLine={false} tickLine={false} stroke="var(--text-muted)" fontSize={10} />
                      <YAxis yAxisId="high" orientation="right" axisLine={false} tickLine={false} stroke="var(--high)" fontSize={10} />
                      <ReferenceLine y={3} stroke="#94A3B8" strokeDasharray="4 2" label={{ value: 'threshold', position: 'right', fontSize: 10, fill: '#94A3B8' }} />
                      <Tooltip 
                        content={({ active, payload, label }) => {
                          if (active && payload && payload.length) {
                            const critical = payload.find(p => p.dataKey === 'critical_count')?.value || 0;
                            const high = payload.find(p => p.dataKey === 'high_count')?.value || 0;
                            const medium = payload.find(p => p.dataKey === 'medium_count')?.value || 0;
                            const total = critical + high + medium;
                            return (
                              <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px', boxShadow: 'var(--shadow-md)' }}>
                                <div style={{ marginBottom: '8px', fontWeight: 'bold', color: 'var(--text-primary)' }}>{label}</div>
                                <div style={{ color: 'var(--critical)' }}>Critical: {critical}</div>
                                <div style={{ color: 'var(--high)' }}>High: {high}</div>
                                <div style={{ color: 'var(--medium)' }}>Medium: {medium}</div>
                                <div style={{ marginTop: '8px', borderTop: '1px solid var(--border)', paddingTop: '4px', color: 'var(--text-primary)', fontWeight: 'bold' }}>Total Alerts: {total}</div>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Line type="monotone" dataKey="critical_count" stroke="var(--critical)" strokeWidth={2.5} dot={false} />
                      <Line type="monotone" dataKey="high_count" yAxisId="high" stroke="var(--high)" strokeWidth={3} dot={false} />
                      <Line type="monotone" dataKey="medium_count" stroke="var(--medium)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
              {summary && (
                <div className="chart-footer">
                  Monitoring {ORG_NAME} | Employees {summary.total_employees_monitored} | Active signals {summary.total_active} | Range {new Date(summary.date_range.start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – {new Date(summary.date_range.end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'ALERTS' && (
          <div className="view-alerts">
            <div className="table-card">
              <div className="table-filter-bar">
                <div className="filter-group">
                  <div className="filter-item">
                    <span className="filter-label">Severity</span>
                    <select className="filter-select" value={filters.severity} onChange={e => setFilters({...filters, severity: e.target.value})}>
                      <option value="">All Severities</option>
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                    </select>
                  </div>
                  <div className="filter-item">
                    <span className="filter-label">Status</span>
                    <select className="filter-select" value={filters.status} onChange={e => setFilters({...filters, status: e.target.value})}>
                      <option value="">All Statuses</option>
                      <option value="open">Open</option>
                      <option value="investigating">Investigating</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </div>
                </div>
                <div className="table-stats">
                  {alerts.length} of {totalAlerts} alerts
                </div>
              </div>

              <table>
                <thead>
                  <tr>
                    <th>Priority</th>
                    <th>Severity</th>
                    <th>Employee</th>
                    <th>Rules</th>
                    <th>Score</th>
                    <th>Explanation</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map(alert => {
                    const colors = getSeverityColors(alert.adjusted_severity);
                    return (
                      <tr key={alert.alert_id}>
                        <td className="mono" style={{ color: '#CBD5E1', fontSize: '12px' }}>#{alert.priority_rank}</td>
                        <td>
                          <span className="severity-badge" style={{ 
                            backgroundColor: colors.bg, 
                            color: colors.main,
                            border: `1px solid ${colors.main}4D`
                          }}>
                            {alert.adjusted_severity}
                          </span>
                        </td>
                        <td className="mono" style={{ fontWeight: 500 }}>EMP-{alert.emp_id}</td>
                        <td>
                          {alert.rules_triggered.split(',').map(r => (
                            <span key={r} className="rule-badge">{r}</span>
                          ))}
                        </td>
                        <td>
                          <div className="score-container">
                            <span className="mono" style={{ color: colors.main }}>{alert.anomaly_score.toFixed(2)}</span>
                            <div className="score-bar" style={{ 
                              width: `${Math.min(alert.anomaly_score * 100, 60)}px`, 
                              backgroundColor: colors.main 
                            }}></div>
                          </div>
                        </td>
                        <td className="mono" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {formatDateTime(alert)}
                        </td>
                        <td title={alert.explanation} style={{ cursor: 'pointer', color: '#475569' }}>
                          {alert.explanation.substring(0, 100)}...
                        </td>
                        <td>
                          <button className="review-btn" onClick={() => {
                            setSelectedAlert(alert);
                            setDrawerOpen(true);
                          }}>REVIEW</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {alerts.length < totalAlerts && (
                <button 
                  className="save-btn" 
                  style={{ width: '100%', borderRadius: 0, marginTop: 0 }} 
                  onClick={() => fetchAlerts()}
                >
                  LOAD MORE
                </button>
              )}
            </div>
          </div>
        )}

        {activeTab === 'INVESTIGATE' && (
          <div className="view-investigate">
            <div className="search-section">
              <span className="search-label">EMPLOYEE PROFILE LOOKUP</span>
              <div className="search-row">
                <input 
                  type="text" 
                  className="search-input"
                  placeholder="Enter Employee ID" 
                  value={investigateId}
                  onChange={e => setInvestigateId(e.target.value)}
                />
                <button className="lookup-btn" onClick={() => handleLookup()}>LOOKUP</button>
              </div>
            </div>

            <div className="flagged-section">
              <span className="search-label" style={{ marginBottom: '12px' }}>FLAGGED EMPLOYEES</span>
              <div className="flagged-grid">
                {[
                  { id: '1061', severity: 'critical', role: 'Physician · Dept 7', anomaly: 'BULK EXPORT', score: '0.83' },
                  { id: '1022', severity: 'critical', role: 'MA · Dept 2', anomaly: 'VIP SNOOP', score: '0.66' },
                  { id: '1052', severity: 'high', role: 'MA · Dept 5', anomaly: 'OFF HOURS', score: '0.61' },
                  { id: '1067', severity: 'high', role: 'Physician · Dept 12', anomaly: 'CROSS DEPT', score: '0.53' }
                ].map(emp => {
                  const colors = getSeverityColors(emp.severity);
                  return (
                    <div key={emp.id} className="flagged-card" style={{ '--accent-color': colors.main, backgroundColor: '#FFFFFF' }} onClick={() => handleLookup(emp.id)}>
                      <div className="flagged-top">
                        <span className="flagged-id">EMP-{emp.id}</span>
                        <span className="flagged-score" style={{ color: colors.main }}>{emp.score}</span>
                      </div>
                      <div className="flagged-role">{emp.role}</div>
                      <div className="anomaly-badge" style={{ color: colors.main, opacity: 0.7 }}>
                        {emp.anomaly} ›
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {profile && (
              <div className="profile-result">
                <div className="profile-card">
                  <div className="profile-id">EMP-{profile.emp_id}</div>
                  <div className="profile-meta">
                    <span className="severity-badge" style={{ backgroundColor: 'var(--medium-bg)', color: 'var(--medium)', border: '1px solid var(--medium)4D' }}>{profile.role}</span>
                    <span className="stat-sublabel">Dept {profile.dept_id} · {profile.is_float ? 'Float Status' : 'Permanent'}</span>
                  </div>

                  <span className="section-label">BEHAVIORAL BASELINE</span>
                  {[
                    {label: 'Off-Hours', key: 'off_hours_rate'},
                    {label: 'Out-of-Panel', key: 'in_panel_rate', invert: true},
                    {label: 'Export/Print', key: 'export_print_rate'},
                    {label: 'Break-Glass', key: 'break_glass_rate'},
                    {label: 'Cross-Dept', key: 'cross_dept_rate'}
                  ].map(m => {
                    const val = m.invert ? (1 - profile.baseline[m.key]) : profile.baseline[m.key];
                    let barColor = 'var(--success)';
                    if (val > 0.3) barColor = 'var(--critical)';
                    else if (val > 0.1) barColor = 'var(--high)';
                    
                    return (
                      <div key={m.label} className="metric-row">
                        <div className="metric-header">
                          <span>{m.label}</span>
                          <span className="mono">{(val * 100).toFixed(1)}%</span>
                        </div>
                        <div className="progress-track">
                          <div className="progress-fill" style={{ width: `${val * 100}%`, backgroundColor: barColor }}></div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="profile-card">
                  <span className="section-label">ALERT HISTORY</span>
                  <div className="history-summary">
                    <div className="history-stat"><span className="history-stat-value">{profile.alert_summary.total_alerts}</span><span className="history-stat-label">Total</span></div>
                    <div className="history-stat"><span className="history-stat-value" style={{ color: 'var(--critical)' }}>{profile.alert_summary.critical_count}</span><span className="history-stat-label">Crit</span></div>
                    <div className="history-stat"><span className="history-stat-value" style={{ color: 'var(--high)' }}>{profile.alert_summary.high_count}</span><span className="history-stat-label">High</span></div>
                    <div className="history-stat"><span className="history-stat-value" style={{ color: 'var(--medium)' }}>{profile.alert_summary.medium_count}</span><span className="history-stat-label">Med</span></div>
                  </div>

                  <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                    <table style={{ fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Severity</th>
                          <th>Score</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {profileAlerts.slice(0, 10).map(a => {
                          const colors = getSeverityColors(a.adjusted_severity);
                          let statusColor = 'var(--critical)';
                          if (a.status === 'investigating') statusColor = 'var(--high)';
                          else if (a.status === 'resolved') statusColor = 'var(--success)';

                          return (
                            <tr key={a.alert_id}>
                              <td className="mono">{a.alert_date}</td>
                              <td><span className="severity-badge" style={{ backgroundColor: colors.bg, color: colors.main, border: `1px solid ${colors.main}4D`, fontSize: '9px', padding: '1px 6px' }}>{a.adjusted_severity}</span></td>
                              <td className="mono">{a.anomaly_score.toFixed(2)}</td>
                              <td><div className="status-dot-small" style={{ backgroundColor: statusColor }}></div></td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {drawerOpen && selectedAlert && (
        <div className="drawer-backdrop" onClick={() => setDrawerOpen(false)}>
          <div className="drawer" onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <span className="brand-subtitle">ALERT REVIEW</span>
              <div className="profile-id" style={{ fontSize: '22px', margin: '4px 0' }}>EMP-{selectedAlert.emp_id}</div>
              <span className="severity-badge" style={{ 
                backgroundColor: getSeverityColors(selectedAlert.adjusted_severity).bg, 
                color: getSeverityColors(selectedAlert.adjusted_severity).main,
                border: `1px solid ${getSeverityColors(selectedAlert.adjusted_severity).main}4D`
              }}>
                {selectedAlert.adjusted_severity}
              </span>
              <button className="close-btn" onClick={() => setDrawerOpen(false)}>&times;</button>
            </div>
            
            <div className="drawer-body">
              <div className="explanation-text">{selectedAlert.explanation}</div>

              <span className="search-label" style={{ marginBottom: '8px', display: 'block' }}>UPDATE STATUS</span>
              <div className="status-buttons">
                <button 
                  className={`status-btn ${selectedAlert.status === 'open' ? 'active open' : ''}`}
                  onClick={() => setSelectedAlert({...selectedAlert, status: 'open'})}
                >OPEN</button>
                <button 
                  className={`status-btn ${selectedAlert.status === 'investigating' ? 'active investigating' : ''}`}
                  onClick={() => setSelectedAlert({...selectedAlert, status: 'investigating'})}
                >INVESTIGATING</button>
                <button 
                  className={`status-btn ${selectedAlert.status === 'resolved' ? 'active resolved' : ''}`}
                  onClick={() => setSelectedAlert({...selectedAlert, status: 'resolved'})}
                >RESOLVED</button>
              </div>

              <span className="search-label" style={{ marginBottom: '8px', display: 'block' }}>REVIEWER NAME</span>
              <input 
                type="text" 
                className="input-field"
                defaultValue={selectedAlert.reviewed_by}
                onChange={e => setSelectedAlert({...selectedAlert, reviewed_by: e.target.value})}
              />

              <span className="search-label" style={{ marginBottom: '8px', display: 'block' }}>NOTES</span>
              <textarea 
                rows={4} 
                className="input-field"
                defaultValue={selectedAlert.reviewer_notes}
                onChange={e => setSelectedAlert({...selectedAlert, reviewer_notes: e.target.value})}
              />

              <button className="save-btn" onClick={() => handleUpdateStatus(selectedAlert.alert_id, {
                status: selectedAlert.status,
                reviewer_notes: selectedAlert.reviewer_notes,
                reviewed_by: selectedAlert.reviewed_by
              })}>SAVE CHANGES</button>
            </div>
          </div>
        </div>
      )}

      {apiStatus === 'error' && (
        <div className="error-banner">
          ⚠ Unable to connect to SentinelEHR API at localhost:8000 — check that api.py is running
        </div>
      )}
    </div>
  );
};

export default App;
