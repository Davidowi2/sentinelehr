import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const params = new URLSearchParams(window.location.search);
const ORG_NAME = params.get('org') || "SentinelEHR Demo";
const ORG_SUBTITLE = "Central Texas Community Health Centers";

const App = () => {
  const [token, setToken] = useState( 
    localStorage.getItem('sentinel_token') || null 
  ) 
  const [loggingIn, setLoggingIn] = useState(false) 
  const [loginError, setLoginError] = useState('') 
  const [loginForm, setLoginForm] = useState( 
    { username: '', password: '' } 
  ) 
  const [appLoading, setAppLoading] = useState(false) 

  const handleLogin = async (e) => { 
    e.preventDefault() 
    setLoggingIn(true) 
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
        setAppLoading(true) 
        setTimeout(() => setAppLoading(false), 2000) 
        setLoginError('') 
      } else { 
        setLoginError('Incorrect username or password') 
      } 
    } catch { 
      setLoginError('Cannot connect to server') 
    } 
    setLoggingIn(false) 
  } 

  useEffect(() => { 
    if (!token) { 
      fetch(`${API_BASE}/health`) 
        .catch(() => {}) 
    } 
  }, [token]) 

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

  const [casesData, setCasesData] = useState([]) 
  const [casesTotal, setCasesTotal] = useState(0) 
  const [casesLoading, setCasesLoading] = useState(false) 
  const [caseStatusFilter, setCaseStatusFilter] = useState('Open') 
  const [casePriorityFilter, setCasePriorityFilter] = useState('') 
  const [casesOffset, setCasesOffset] = useState(0) 
  const [casesError, setCasesError] = useState(null) 
  const CASES_LIMIT = 50 

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

  const fetchCases = async () => { 
    setCasesLoading(true) 
    setCasesError(null)
    try { 
      let url = `${API_BASE}/cases?limit=${CASES_LIMIT}&offset=${casesOffset}` 
      if (caseStatusFilter) url += `&status=${encodeURIComponent(caseStatusFilter)}` 
      if (casePriorityFilter) url += `&priority=${casePriorityFilter}` 
      const res = await fetch(url, { 
        headers: { 'Authorization': `Bearer ${token}` } 
      }) 
      if (!res.ok) { 
        console.error('Cases API error:', res.status) 
        setCasesError(res.status)
        setCasesData([]) 
        setCasesLoading(false) 
        return 
      } 
      const data = await res.json() 
      setCasesData(data.cases || []) 
      setCasesTotal(data.total_count || 0) 
    } catch(e) { 
      console.error('Cases fetch failed', e) 
      setCasesError('Connection Failed')
    } 
    setCasesLoading(false) 
  } 
  
  useEffect(() => { 
    if (activeTab === 'cases') fetchCases() 
  }, [activeTab, caseStatusFilter, casePriorityFilter, casesOffset, token]) 

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
          boxShadow: '0 1px 3px rgba(15,23,42,0.08), 0 4px 16px rgba(15,23,42,0.06)', 
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

            <button type="submit" 
              disabled={loggingIn}
              style={{ 
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
              cursor: loggingIn ? 'not-allowed' : 'pointer', 
              opacity: loggingIn ? 0.7 : 1,
              fontFamily: "'DM Sans', sans-serif" 
            }}>
              {loggingIn ? 'Connecting...' : 'Sign In →'}
            </button> 
          </form> 
        </div> 
      </div> 
    ) 
  }

  if (appLoading) return ( 
    <div style={{minHeight:'100vh', 
      background:'#EEF2FF', display:'flex', 
      alignItems:'center', justifyContent:'center', 
      flexDirection:'column', gap:'16px'}}> 
      <div style={{width:'40px', height:'40px', 
        border:'3px solid #E2E8F4', 
        borderTop:'3px solid #E11D48', 
        borderRadius:'50%', 
        animation:'spin 1s linear infinite'}}/> 
      <p style={{color:'#94A3B8', fontSize:'13px', 
        fontFamily:'IBM Plex Mono, monospace'}}> 
        Connecting to SentinelEHR...</p> 
    </div> 
  )

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
        {['OVERVIEW', 'ALERTS', 'CASES', 'INVESTIGATE'].map(tab => (
          <button 
            key={tab} 
            className={`tab ${activeTab === tab.toUpperCase() || (activeTab === 'cases' && tab === 'CASES') ? 'active' : ''}`}
            onClick={() => setActiveTab(tab === 'CASES' ? 'cases' : tab)}
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
                const fallbacks = { critical: 285, high: 200, medium: 314, ml: 0.85 };
                const val = stat.key === 'ml' ? (summary?.top_anomaly_score || fallbacks.ml) : (summary?.[stat.key] || fallbacks[stat.key]);
                const pct = summary?.total_active ? Math.round(((summary?.[stat.key] || fallbacks[stat.key]) / (summary?.total_active || 799)) * 100) : 0;
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

            {(() => { 
              const chartRef = useRef(null) 
              const chartInstance = useRef(null) 
             
              useEffect(() => { 
                if (!digest.length || !chartRef.current) return 
                 
                const last30 = [...digest].reverse().slice(-30) 
                const labels = last30.map(d => { 
                  const date = new Date(d.alert_date) 
                  return date.toLocaleDateString('en-US',  
                    { month: 'short', day: 'numeric' }) 
                }) 
                 
                if (chartInstance.current) { 
                  chartInstance.current.destroy() 
                } 
                 
                const ctx = chartRef.current.getContext('2d') 
                chartInstance.current = new window.Chart(ctx, { 
                  type: 'line', 
                  data: { 
                    labels, 
                    datasets: [ 
                      { 
                        label: 'Critical', 
                        data: last30.map(d => d.critical_count || 0), 
                        borderColor: '#e11d48', 
                        backgroundColor: 'rgba(225, 29, 72, 0.04)', 
                        borderWidth: 2.5, 
                        fill: true,
                        pointRadius: 0, 
                        pointHoverRadius: 4, 
                        pointHoverBackgroundColor: '#e11d48', 
                        tension: 0.15 
                      }, 
                      { 
                        label: 'High', 
                        data: last30.map(d => d.high_count || 0), 
                        borderColor: '#f97316', 
                        backgroundColor: 'transparent', 
                        borderWidth: 2.5, 
                        pointRadius: 0, 
                        pointHoverRadius: 4, 
                        pointHoverBackgroundColor: '#f97316', 
                        tension: 0.15 
                      }, 
                      { 
                        label: 'Medium', 
                        data: last30.map(d => d.medium_count || 0), 
                        borderColor: '#3b82f6', 
                        backgroundColor: 'transparent', 
                        borderWidth: 2.5, 
                        pointRadius: 0, 
                        pointHoverRadius: 4, 
                        pointHoverBackgroundColor: '#3b82f6', 
                        tension: 0.15 
                      }, 
                      { 
                        label: 'Threshold', 
                        data: last30.map(() => 3), 
                        borderColor: '#cbd5e1', 
                        backgroundColor: 'transparent', 
                        borderWidth: 1.5, 
                        borderDash: [6, 4], 
                        pointRadius: 0, 
                        pointHoverRadius: 0, 
                        tension: 0 
                      } 
                    ] 
                  }, 
                  options: { 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    interaction: { mode: 'index', intersect: false }, 
                    plugins: { 
                      legend: { display: false }, 
                      tooltip: { 
                        backgroundColor: '#fff', 
                        borderColor: '#e2e8f0', 
                        borderWidth: 1, 
                        titleColor: '#0f172a', 
                        bodyColor: '#475569', 
                        padding: 10, 
                        bodySpacing: 6 
                      } 
                    }, 
                    scales: { 
                      x: { 
                        grid: { display: false }, 
                        border: { color: '#e2e8f0' }, 
                        ticks: { 
                          color: '#94a3b8', 
                          font: { size: 11 }, 
                          maxTicksLimit: 8 
                        } 
                      }, 
                      y: { 
                        min: 0, 
                        suggestedMax: 16,
                        grid: { color: '#f1f5f9' }, 
                        border: { display: false }, 
                        ticks: { 
                          color: '#94a3b8', 
                          font: { size: 11 }, 
                          stepSize: 2 
                        } 
                      } 
                    } 
                  } 
                }) 
                 
                return () => { 
                  if (chartInstance.current) { 
                    chartInstance.current.destroy() 
                  } 
                } 
              }, [digest]) 
             
              return ( 
                <div style={{ 
                  background: '#fff', 
                  borderRadius: '12px', 
                  border: '1px solid #E2E8F4', 
                  boxShadow: '0 1px 4px rgba(15,23,42,0.06)', 
                  padding: '28px 32px', 
                  margin: '0 32px 24px' 
                }}> 
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'flex-start', 
                    marginBottom: '20px' 
                  }}> 
                    <div> 
                      <div style={{ 
                        fontSize: '11px', 
                        fontWeight: '600', 
                        letterSpacing: '0.08em', 
                        textTransform: 'uppercase', 
                        color: '#94a3b8', 
                        marginBottom: '4px' 
                      }}>Alert Trend</div> 
                      <div style={{ 
                        fontSize: '20px', 
                        fontWeight: '700', 
                        color: '#0f172a' 
                      }}>Last 30 days</div> 
                    </div> 
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '20px', 
                      fontSize: '12px', 
                      color: '#475569' 
                    }}> 
                      {[ 
                        { color: '#e11d48', label: 'Critical' }, 
                        { color: '#f97316', label: 'High' }, 
                        { color: '#3b82f6', label: 'Medium' } 
                      ].map(item => ( 
                        <span key={item.label} style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          gap: '6px' 
                        }}> 
                          <span style={{ 
                            display: 'inline-block', 
                            width: '20px', 
                            height: '3px', 
                            background: item.color, 
                            borderRadius: '2px' 
                          }}></span> 
                          {item.label} 
                        </span> 
                      ))} 
                      <span style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '6px' 
                      }}> 
                        <span style={{ 
                          display: 'inline-block', 
                          width: '20px', 
                          height: '0', 
                          borderTop: '2px dashed #94a3b8' 
                        }}></span> 
                        Threshold 
                      </span> 
                    </div> 
                  </div> 
             
                  <div style={{ position: 'relative', height: '260px' }}> 
                    <canvas 
                      ref={chartRef} 
                      role="img" 
                      aria-label="Alert trend over last 30 days" 
                    /> 
                  </div> 
             
                  <div style={{ 
                    borderTop: '1px solid #e2e8f0', 
                    marginTop: '20px', 
                    paddingTop: '14px', 
                    display: 'flex', 
                    alignItems: 'center' 
                  }}> 
                    {[ 
                      { label: 'Monitoring', value: ORG_NAME }, 
                      { label: 'Employees',  
                        value: summary?.total_employees_monitored || 80 }, 
                      { label: 'Active signals',  
                        value: summary?.total_active || 799 }, 
                      { label: 'Range',  
                        value: summary ?  
                          `${new Date(summary.date_range?.start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} –  
                           ${new Date(summary.date_range?.end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}` :  
                          'Jan 1 – Mar 31' } 
                    ].map((item, i, arr) => ( 
                      <div key={item.label} style={{ 
                        flex: 1, 
                        textAlign: 'center', 
                        padding: '0 16px', 
                        borderRight: i < arr.length - 1 ?  
                          '1px solid #e2e8f0' : 'none' 
                      }}> 
                        <div style={{ 
                          fontSize: '11px', 
                          color: '#94a3b8', 
                          marginBottom: '2px' 
                        }}>{item.label}</div> 
                        <div style={{ 
                          fontSize: '11px', 
                          fontWeight: '600', 
                          color: '#475569' 
                        }}>{item.value}</div> 
                      </div> 
                    ))} 
                  </div> 
                </div> 
              ) 
            })()} 
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

        {activeTab === 'cases' && ( 
          <div style={{padding: '24px 32px'}}> 
        
            {/* Filter bar */} 
            <div style={{ 
              background: '#fff', 
              borderRadius: '12px', 
              border: '1px solid #E2E8F4', 
              boxShadow: '0 1px 4px rgba(15,23,42,0.06)', 
              padding: '16px 20px', 
              marginBottom: '16px', 
              display: 'flex', 
              alignItems: 'flex-end', 
              gap: '16px' 
            }}> 
              <div> 
                <div style={{fontSize:'11px', fontWeight:'500', 
                  letterSpacing:'0.08em', textTransform:'uppercase', 
                  color:'#64748B', marginBottom:'6px'}}> 
                  Status 
                </div> 
                <select 
                  value={caseStatusFilter} 
                  onChange={e => { 
                    setCaseStatusFilter(e.target.value) 
                    setCasesOffset(0) 
                  }} 
                  style={{background:'#FAFBFF', 
                    border:'1px solid #E2E8F4', 
                    borderRadius:'6px', padding:'8px 12px', 
                    fontSize:'13px', color:'#0F172A', 
                    fontFamily:'IBM Plex Mono, monospace'}}> 
                  <option value="">All</option> 
                  <option value="Open">Open</option> 
                  <option value="Under Investigation"> 
                    Under Investigation</option> 
                  <option value="Pending HR">Pending HR</option> 
                  <option value="Resolved">Resolved</option> 
                  <option value="Closed">Closed</option> 
                </select> 
              </div> 
        
              <div> 
                <div style={{fontSize:'11px', fontWeight:'500', 
                  letterSpacing:'0.08em', textTransform:'uppercase', 
                  color:'#64748B', marginBottom:'6px'}}> 
                  Priority 
                </div> 
                <select 
                  value={casePriorityFilter} 
                  onChange={e => { 
                    setCasePriorityFilter(e.target.value) 
                    setCasesOffset(0) 
                  }} 
                  style={{background:'#FAFBFF', 
                    border:'1px solid #E2E8F4', 
                    borderRadius:'6px', padding:'8px 12px', 
                    fontSize:'13px', color:'#0F172A', 
                    fontFamily:'IBM Plex Mono, monospace'}}> 
                  <option value="">All</option> 
                  <option value="Critical">Critical</option> 
                  <option value="Medium">Medium</option> 
                  <option value="Low">Low</option> 
                </select> 
              </div> 
        
              <div style={{marginLeft:'auto', fontSize:'12px', 
                color:'#94A3B8', 
                fontFamily:'IBM Plex Mono, monospace'}}> 
                {casesTotal} cases 
              </div> 
            </div> 
        
            {/* Cases table */} 
            <div style={{ 
              background: '#fff', 
              borderRadius: '12px', 
              border: '1px solid #E2E8F4', 
              boxShadow: '0 1px 4px rgba(15,23,42,0.06)', 
              overflow: 'hidden' 
            }}> 
              <table style={{width:'100%', 
                borderCollapse:'collapse'}}> 
                <thead> 
                  <tr style={{background:'#F8FAFF'}}> 
                    {['Case ID','Employee','Priority', 
                      'Status','Days Open','Alerts', 
                      'Window','Assigned To'].map(h => ( 
                      <th key={h} style={{ 
                        padding:'12px 16px', 
                        textAlign:'left', 
                        fontSize:'10px', 
                        fontWeight:'600', 
                        letterSpacing:'0.12em', 
                        textTransform:'uppercase', 
                        color:'#94A3B8', 
                        borderBottom:'1px solid #E2E8F4' 
                      }}>{h}</th> 
                    ))} 
                  </tr> 
                </thead> 
                <tbody> 
                  {casesError && ( 
                    <tr><td colSpan={8} style={{ 
                      padding:'40px', textAlign:'center', 
                      color:'#E11D48', fontSize:'13px', 
                      fontFamily:'IBM Plex Mono, monospace' 
                    }}>API error {casesError} — check server connection</td></tr> 
                  )} 
                  {casesLoading ? ( 
                    <tr><td colSpan={8} style={{ 
                      padding:'40px', textAlign:'center', 
                      color:'#94A3B8', fontSize:'13px' 
                    }}>Loading cases...</td></tr> 
                  ) : casesData.length === 0 ? ( 
                    <tr><td colSpan={8} style={{ 
                      padding:'40px', textAlign:'center', 
                      color:'#94A3B8', fontSize:'13px' 
                    }}>No cases found</td></tr> 
                  ) : casesData.map(c => { 
                    const priorityColor = 
                      c.priority === 'Critical' ? '#E11D48' : 
                      c.priority === 'Medium' ? '#2563EB' : '#64748B' 
                    const statusColor = 
                      c.status === 'Open' ? '#E11D48' : 
                      c.status === 'Under Investigation' ? '#D97706' : 
                      c.status === 'Pending HR' ? '#7C3AED' : 
                      c.status === 'Resolved' ? '#059669' : '#64748B' 
                    const daysOpen = Math.round( 
                      c.days_open || 0) 
                    const alertCount = Array.isArray(c.alert_ids) 
                      ? c.alert_ids.length 
                      : (c.alert_ids 
                        ? JSON.parse(c.alert_ids).length 
                        : 0) 
                    const windowStart = c.window_start 
                      ? c.window_start.slice(0,10) : '' 
                    const windowEnd = c.window_end 
                      ? c.window_end.slice(0,10) : '' 
        
                    return ( 
                      <tr key={c.case_id} 
                        style={{borderBottom:'1px solid #E2E8F4', 
                          cursor:'pointer', transition:'background 0.1s ease'}} 
                        onMouseEnter={e => 
                          e.currentTarget.style.background='#F1F5FF'} 
                        onMouseLeave={e => 
                          e.currentTarget.style.background='#fff'} 
                      > 
                        <td style={{padding:'14px 16px'}}> 
                          <span style={{ 
                            fontFamily:'IBM Plex Mono, monospace', 
                            fontSize:'12px', fontWeight:'600', 
                            color:'#E11D48' 
                          }}>{c.case_id}</span> 
                        </td> 
                        <td style={{padding:'14px 16px', 
                          fontFamily:'IBM Plex Mono, monospace', 
                          fontSize:'12px', color:'#0F172A', 
                          fontWeight:'500'}}> 
                          EMP-{c.emp_id} 
                        </td> 
                        <td style={{padding:'14px 16px'}}> 
                          <span style={{ 
                            display:'inline-block', 
                            padding:'3px 10px', 
                            borderRadius:'20px', 
                            fontSize:'11px', 
                            fontWeight:'500', 
                            textTransform:'uppercase', 
                            letterSpacing:'0.06em', 
                            color: priorityColor, 
                            background: c.priority==='Critical' 
                              ? '#FFF1F3' 
                              : c.priority==='Medium' 
                              ? '#EFF6FF' : '#F8FAFF', 
                            border:`1px solid ${priorityColor}40` 
                          }}>{c.priority}</span> 
                        </td> 
                        <td style={{padding:'14px 16px'}}> 
                          <span style={{ 
                            display:'inline-flex', 
                            alignItems:'center', 
                            gap:'6px', 
                            fontSize:'12px', 
                            color: statusColor, 
                            fontWeight:'500' 
                          }}> 
                            <span style={{ 
                              width:'6px', height:'6px', 
                              borderRadius:'50%', 
                              background: statusColor, 
                              flexShrink:0 
                            }}/> 
                            {c.status} 
                          </span> 
                        </td> 
                        <td style={{ 
                          padding:'14px 16px', 
                          fontFamily:'IBM Plex Mono, monospace', 
                          fontSize:'12px', 
                          color: daysOpen > 14 ? '#E11D48' 
                            : '#475569', 
                          fontWeight: daysOpen > 14 ? '600':'400' 
                        }}> 
                          {daysOpen}d 
                          {daysOpen > 14 && 
                            <span style={{marginLeft:'4px', 
                              fontSize:'10px'}}>⚠</span>} 
                        </td> 
                        <td style={{ 
                          padding:'14px 16px', 
                          fontFamily:'IBM Plex Mono, monospace', 
                          fontSize:'12px', color:'#475569' 
                        }}>{alertCount}</td> 
                        <td style={{ 
                          padding:'14px 16px', 
                          fontSize:'11px', color:'#94A3B8', 
                          fontFamily:'IBM Plex Mono, monospace' 
                        }}> 
                          {windowStart}<br/> 
                          <span style={{color:'#CBD5E1'}}> 
                            to {windowEnd} 
                          </span> 
                        </td> 
                        <td style={{ 
                          padding:'14px 16px', 
                          fontSize:'12px', color:'#94A3B8', 
                          fontFamily:'IBM Plex Mono, monospace' 
                        }}> 
                          {c.assigned_to 
                            ? `USR-${c.assigned_to}` 
                            : '—'} 
                        </td> 
                      </tr> 
                    ) 
                  })} 
                </tbody> 
              </table> 
        
              {/* Pagination */} 
              {casesTotal > CASES_LIMIT && ( 
                <div style={{ 
                  padding:'16px 20px', 
                  borderTop:'1px solid #E2E8F4', 
                  display:'flex', gap:'8px', 
                  alignItems:'center' 
                }}> 
                  <button 
                    onClick={() => setCasesOffset( 
                      Math.max(0, casesOffset - CASES_LIMIT))} 
                    disabled={casesOffset === 0} 
                    style={{ 
                      padding:'6px 16px', 
                      border:'1px solid #E2E8F4', 
                      borderRadius:'6px', background:'#fff', 
                      fontSize:'12px', cursor:'pointer', 
                      color: casesOffset===0 
                        ? '#CBD5E1' : '#475569' 
                    }}>← Prev</button> 
                  <span style={{fontSize:'12px', 
                    color:'#94A3B8', 
                    fontFamily:'IBM Plex Mono, monospace'}}> 
                    {casesOffset + 1}– 
                    {Math.min(casesOffset+CASES_LIMIT, casesTotal)} 
                    {' '}of {casesTotal} 
                  </span> 
                  <button 
                    onClick={() => setCasesOffset( 
                      casesOffset + CASES_LIMIT)} 
                    disabled={casesOffset+CASES_LIMIT >= casesTotal} 
                    style={{ 
                      padding:'6px 16px', 
                      border:'1px solid #E2E8F4', 
                      borderRadius:'6px', background:'#fff', 
                      fontSize:'12px', cursor:'pointer', 
                      color: casesOffset+CASES_LIMIT>=casesTotal 
                        ? '#CBD5E1' : '#475569' 
                    }}>Next →</button> 
                </div> 
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
