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
  Check,
  Mail,
  User,
  Activity,
  AlertTriangle,
  Download,
  FileText,
  Printer,
  X,
  Plus,
  ArrowRight,
  BellRing,
  Calendar,
  ClipboardList,
  Info,
  LayoutDashboard,
  Lock,
  ScanSearch,
  ShieldCheck,
  AlertOctagon,
  Eye,
  EyeOff
} from 'lucide-react';

const THEMES = {
  dark: `
    --surface-dim: #0b1326;
    --surface-container-low: #131b2e;
    --surface-container: #131b2e;
    --surface-container-high: #222a3d;
    --surface-container-highest: #2a3449;
    --surface-container-lowest: #060e20;
    --outline-variant: rgba(140,144,159,0.2);
    --outline: #8c909f;
    --primary: #adc6ff;
    --primary-container: #8aa8e8;
    --on-primary-container: #0b1326;
    --on-surface: #d3e4fe;
    --on-surface-variant: #bdc8ce;
    --error: #ffb4ab;
    --tertiary: #ffb873;
    --background: #0b1326;
    --critical: #f43f5e;
    --critical-bg: rgba(244,63,94,0.1);
    --high: #f97316;
    --high-bg: rgba(249,115,22,0.1);
    --medium: #3b82f6;
    --medium-bg: rgba(59,130,246,0.1);
    --success: #10B981;
    --warning: #f97316;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
    
    --bg-app: #0b1326;
    --bg-surface: #131b2e;
    --bg-elevated: #222a3d;
    --bg-hover: #2a3449;
    --border: rgba(140,144,159,0.2);
    --text-primary: #d3e4fe;
    --text-secondary: #bdc8ce;
    --text-muted: #8c909f;
    --accent: #adc6ff;
    --accent-hover: #8aa8e8;
    --accent-subtle: rgba(173,198,255,0.12);
  `,
  light: `
    --surface-dim: #d3e4fe;
    --surface-container-low: #e8f1ff;
    --surface-container: #eef5ff;
    --surface-container-high: #f4f8ff;
    --surface-container-highest: #fafcff;
    --surface-container-lowest: #ffffff;
    --outline-variant: #bdc8ce;
    --outline: #879298;
    --primary: #2563eb;
    --primary-container: #4a9eff;
    --on-primary-container: #002e3b;
    --on-surface: #0f172a;
    --on-surface-variant: #475569;
    --error: #dc2626;
    --tertiary: #ea580c;
    --background: #fafcff;
    --critical: #dc2626;
    --critical-bg: #fee2e2;
    --high: #ea580c;
    --high-bg: #ffedd5;
    --medium: #2563eb;
    --medium-bg: #dbeafe;
    --success: #059669;
    --warning: #ea580c;
    --shadow: 0 4px 24px rgba(15,23,42,0.08);
    
    --bg-app: #fafcff;
    --bg-surface: #ffffff;
    --bg-elevated: #f4f8ff;
    --bg-hover: #eef5ff;
    --border: #bdc8ce;
    --text-primary: #0f172a;
    --text-secondary: #475569;
    --text-muted: #94a3b8;
    --accent: #2563eb;
    --accent-hover: #1e7a99;
    --accent-subtle: rgba(38,157,190,0.08);
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

const API_BASE = import.meta.env.VITE_API_URL || 'https://sentinelehr-api.onrender.com';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: <LayoutGrid size={18} /> },
  { id: 'alerts', label: 'Alerts', icon: <Bell size={18} /> },
  { id: 'cases', label: 'Cases', icon: <Folder size={18} /> },
  { id: 'investigate', label: 'Investigate', icon: <Search size={18} /> },
  { id: 'divider' },
  { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
];

const RULE_DESCRIPTIONS = {
  'R1': 'Volume Spike',
  'R2': 'Volume spike',
  'R3': 'Off-Hours Access',
  'R4': 'VIP Record Access',
  'R6': 'Bulk export detected',
  'R7': 'Break-glass abuse',
  'R8': 'Sensitive Record Access',
  'R_SENSITIVE': 'Sensitive Record Flag'
};

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
      fontFamily: "'JetBrains Mono', monospace" 
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
    color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", 
    outline: 'none', minWidth: '140px' 
  }} /> 
); 

const TableCard = ({ children }) => ( 
  <div style={{ 
    background: '#131b2e', borderRadius: '10px', 
    border: '1px solid rgba(140,144,159,0.2)',
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
      background: '#0d1f35', borderLeft: '1px solid rgba(255,255,255,0.08)',
      zIndex: 101, overflowY: 'auto', 
      display: 'flex', flexDirection: 'column' 
    }}> 
      <div style={{ 
        background: 'var(--bg-elevated)', padding: '24px', 
        borderBottom: '1px solid var(--border)', flexShrink: 0 
      }}> 
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}> 
          <div> 
            <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>{title}</div> 
            <div style={{ fontSize: '22px', fontWeight: '700', fontFamily: "'JetBrains Mono', monospace", color: 'var(--accent)' }}>{id}</div> 
            {subtitle && <div style={{ marginTop: '8px' }}>{subtitle}</div>} 
          </div> 
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}><X size={20} /></button> 
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

const InvestigateResults = React.memo(({ results }) => {
  if (!results || results.error) return null;

  const alerts = results.alerts || [];
  const totalAlerts = alerts.length;
  let daysMonitored = 0;
  if (totalAlerts > 0) {
    const dates = alerts.map(a => new Date(a.alert_date).getTime());
    const minDate = Math.min(...dates);
    const maxDate = Math.max(...dates);
    daysMonitored = Math.ceil((maxDate - minDate) / (1000 * 60 * 60 * 24)) + 1;
  }
  const topScore = results.top_score ?? 0;
  const outOfPanelAlerts = alerts.filter(a => a.rules_triggered.includes('R4') || a.rules_triggered.includes('R8')).length;
  const outOfPanelPct = totalAlerts > 0 ? (outOfPanelAlerts / totalAlerts * 100).toFixed(1) : '0.0';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Row: Profile + Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: '24px' }}>
        {/* Employee Profile - col-span-8 */}
        <div style={{ gridColumn: 'span 8', background: '#0b1c30', border: '1px solid rgba(140,144,159,0.2)', borderRadius: '12px', padding: '28px' }}>
          <div style={{ marginBottom: '24px' }}>
            <div style={{ fontSize: '10px', fontWeight: '600', color: '#879298', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '8px' }}>Employee Profile</div>
            <div style={{ fontSize: '28px', fontWeight: '700', color: '#d3e4fe', fontFamily: "'JetBrains Mono', monospace" }}>EMP-{results.emp_id}</div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
            <div>
              <div style={{ fontSize: '10px', fontWeight: '600', color: '#879298', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>Role</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#bdc8ce' }}>{results.role}</div>
            </div>
            <div>
              <div style={{ fontSize: '10px', fontWeight: '600', color: '#879298', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>Department</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#bdc8ce' }}>Dept {results.dept_id}</div>
            </div>
            <div>
              <div style={{ fontSize: '10px', fontWeight: '600', color: '#879298', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>Clearance</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#bdc8ce' }}>Level {results.clearance_level || 'N/A'}</div>
            </div>
          </div>

          {/* Investigation Insight */}
          <div style={{ 
            background: '#000f21', 
            border: '1px solid rgba(140,144,159,0.2)', 
            borderRadius: '10px', 
            padding: '20px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Activity size={16} style={{ color: '#adc6ff' }} />
              <div style={{ fontSize: '10px', fontWeight: '600', color: '#adc6ff', letterSpacing: '0.1em', textTransform: 'uppercase' }}>Investigation Insight</div>
            </div>
            <div style={{ fontSize: '14px', color: '#d3e4fe', lineHeight: '1.6' }}>
              This employee triggered sensitive record access rules on {totalAlerts} of {daysMonitored || 1} monitored days, 
              with an aggregate risk score of {topScore.toFixed(2)} — 
              {topScore > 0.5 ? ' significantly above' : ' near'} the 0.5 threshold for investigation.
            </div>
          </div>
        </div>

        {/* Mini Stats - col-span-4 */}
        <div style={{ gridColumn: 'span 4', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Anomaly Gauge */}
          <div style={{ background: '#0b1c30', border: '1px solid rgba(140,144,159,0.2)', borderRadius: '12px', padding: '28px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ position: 'relative', width: '128px', height: '128px', marginBottom: '16px' }}>
              <div style={{
                position: 'relative',
                width: '128px',
                height: '128px',
                borderRadius: '50%',
                border: '4px solid #4a9eff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <div style={{ fontSize: '36px', fontWeight: '700', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace", lineHeight: 1 }}>
                  {topScore.toFixed(2)}
                </div>
              </div>
            </div>

            {/* High Risk Warning */}
            {topScore > 0.7 && (
              <div style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                gap: '8px',
                padding: '12px 20px',
                background: 'rgba(244,63,94,0.1)',
                border: '1px solid rgba(244,63,94,0.2)',
                borderRadius: '8px',
                width: '100%'
              }}>
                <AlertTriangle size={20} style={{ color: '#f43f5e' }} />
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#f43f5e', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  High Risk
                </div>
              </div>
            )}
          </div>

          {/* Mini Stat Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
            {[
              { label: 'Total Alerts', value: totalAlerts, icon: <Bell size={48} /> },
              { label: 'Days Monitored', value: daysMonitored || 1, icon: <Calendar size={48} /> },
              { label: 'Out-of-Panel %', value: `${outOfPanelPct}%`, icon: <Shield size={48} /> }
            ].map(stat => (
              <div key={stat.label} style={{ 
                background: '#0b1c30', 
                border: '1px solid rgba(140,144,159,0.2)', 
                borderRadius: '12px', 
                padding: '16px',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{ position: 'relative', zIndex: 1 }}>
                  <div style={{ fontSize: '10px', fontWeight: '600', color: '#879298', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    {stat.label}
                  </div>
                  <div style={{ fontSize: '24px', fontWeight: '700', color: '#d3e4fe', fontFamily: "'JetBrains Mono', monospace" }}>
                    {stat.value}
                  </div>
                </div>
                <div style={{ 
                  position: 'absolute', 
                  right: '12px', 
                  top: '50%', 
                  transform: 'translateY(-50%)',
                  color: '#adc6ff',
                  opacity: 0.2
                }}>
                  {stat.icon}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Alert History - col-span-12 */}
      <div style={{ gridColumn: 'span 12' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <Bell size={18} color="#4a9eff" />
          <h3 style={{ fontSize: '16px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#d3e4fe' }}>Recent Alert History</h3>
        </div>
        <div style={{
          background: '#0b1c30',
          border: '1px solid rgba(140,144,159,0.2)',
          borderRadius: '12px',
          overflow: 'hidden'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}> 
            <thead> 
              <tr style={{ background: 'rgba(27,43,63,0.5)' }}> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Date</th> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Severity</th> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Rules Triggered</th> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Score</th> 
              </tr> 
            </thead> 
            <tbody> 
              {alerts.length > 0 ? (
                alerts.slice(0, 20).map((a, i) => ( 
                  <tr 
                    key={i} 
                    style={{ borderTop: '1px solid rgba(62,72,77,0.3)', transition: 'background 0.2s' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(38,54,74,0.3)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  > 
                    <td style={{ padding: '14px 20px', fontSize: '13px', color: '#bdc8ce', fontFamily: "'JetBrains Mono', monospace" }}> 
                      {new Date(a.alert_date).toLocaleDateString()} 
                    </td> 
                    <td style={{ padding: '14px 20px' }}> 
                      <span style={{
                        padding: '4px 12px',
                        borderRadius: '20px',
                        fontSize: '11px',
                        fontWeight: '700',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        background: a.adjusted_severity === 'Critical' ? '#f43f5e1a' : a.adjusted_severity === 'High' ? '#f973161a' : '#3b82f61a',
                        color: a.adjusted_severity === 'Critical' ? '#f43f5e' : a.adjusted_severity === 'High' ? '#f97316' : '#3b82f6',
                        border: `1px solid ${a.adjusted_severity === 'Critical' ? '#f43f5e33' : a.adjusted_severity === 'High' ? '#f9731633' : '#3b82f633'}`
                      }}>{a.adjusted_severity}</span>
                    </td> 
                    <td style={{ padding: '14px 20px' }}> 
                      <div className="flex flex-wrap gap-1">
                        {a.rules_triggered.split(',').map(r => ( 
                          <div key={r} className="tooltip">
                            <span 
                              style={{ 
                                fontSize: '10px', 
                                background: '#26364a', 
                                border: '1px solid rgba(140,144,159,0.2)', 
                                padding: '3px 8px', 
                                borderRadius: '6px', 
                                color: '#bdc8ce',
                                cursor: 'help',
                                display: 'inline-block',
                                marginBottom: '4px'
                              }}
                            >
                              {r}
                            </span>
                            <span className="tooltiptext">{RULE_DESCRIPTIONS[r.trim()] || r}</span>
                          </div> 
                        ))} 
                      </div>
                    </td> 
                    <td style={{ padding: '14px 20px', fontSize: '14px', color: '#adc6ff', fontWeight: '700', fontFamily: "'JetBrains Mono', monospace" }}> 
                      {(a.anomaly_score ?? 0).toFixed(2)} 
                    </td> 
                  </tr> 
                ))
              ) : (
                <tr><td colSpan="4" style={{ padding: '24px', textAlign: 'center', color: '#879298', fontSize: '13px' }}>No alert history found for this employee.</td></tr>
              )} 
            </tbody> 
          </table> 
        </div>
      </div>

      {/* Open Cases */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <Folder size={18} color="#4a9eff" />
          <h3 style={{ fontSize: '16px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#d3e4fe' }}>Open Cases</h3>
        </div>
        <div style={{
          background: '#0b1c30',
          border: '1px solid rgba(140,144,159,0.2)',
          borderRadius: '12px',
          overflow: 'hidden'
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}> 
            <thead> 
              <tr style={{ background: 'rgba(27,43,63,0.5)' }}> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Case ID</th> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Status</th> 
                <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Days Open</th> 
              </tr> 
            </thead> 
            <tbody> 
              {results.cases?.length > 0 ? (
                results.cases.filter(c => c.status !== 'Resolved').map((c, i) => ( 
                  <tr 
                    key={i} 
                    style={{ borderTop: '1px solid rgba(62,72,77,0.3)', transition: 'background 0.2s' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(38,54,74,0.3)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  > 
                    <td style={{ padding: '14px 20px', fontSize: '13px', fontWeight: '700', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>{c.case_id}</td> 
                    <td style={{ padding: '14px 20px' }}> 
                      <span style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: '600', color: '#bdc8ce' }}> 
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f97316' }} /> 
                        {c.status} 
                      </span> 
                    </td> 
                    <td style={{ padding: '14px 20px', fontSize: '13px', color: '#bdc8ce', fontFamily: "'JetBrains Mono', monospace" }}>{c.days_open}d</td> 
                  </tr> 
                ))
              ) : (
                <tr><td colSpan="3" style={{ padding: '24px', textAlign: 'center', color: '#879298', fontSize: '13px' }}>No active cases found for this employee.</td></tr>
              )} 
            </tbody> 
          </table> 
        </div>
      </div>
    </div>
  );
});

const SettingsSection = ({ title, icon, children }) => (
  <div className="w-full" style={{ 
    background: '#0d1f35', border: '1px solid rgba(255,255,255,0.08)', 
    borderRadius: '12px', padding: '24px', marginBottom: '24px'
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
      <div style={{ color: 'var(--accent)' }}>{icon}</div>
      <h3 style={{ fontSize: '16px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</h3>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {children}
    </div>
  </div>
);

const SettingsField = ({ label, value, subtext, disabled, type = 'text' }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
    <label style={{ fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</label>
    {type === 'select' ? (
      <Select value={value} disabled={disabled} style={{ width: '100%', opacity: disabled ? 0.6 : 1 }} />
    ) : (
      <input 
        id="settings-field"
        name="settings-field"
        type="text" 
        readOnly 
        value={value} 
        style={{ 
          background: 'var(--bg-elevated)', border: '1px solid var(--border)', 
          borderRadius: '6px', padding: '10px 14px', fontSize: '13px', 
          color: disabled ? 'var(--text-muted)' : 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", 
          outline: 'none', width: '100%', cursor: 'default'
        }} 
      />
    )}
    {subtext && <div style={{ fontSize: '11px', color: 'var(--accent)', marginTop: '2px', fontWeight: '500' }}>{subtext}</div>}
  </div>
);

const SettingsView = ({ 
  thresholds, 
  setThresholds, 
  handleSaveThresholds, 
  savingThresholds, 
  thresholdMessage,
  userEmail,
  userRole,
  token,
  authHeaders
}) => {
  const [showPasswordForm, setShowPasswordForm] = useState(false); 
  const [passwordData, setPasswordData] = useState({current: '', new: '', confirm: ''}); 
  const [passwordMsg, setPasswordMsg] = useState(null); 

  return (
    <div style={{ width: '100%' }}>
      {userRole !== 'admin' && ( 
        <div style={{padding:'12px 16px', background:'rgba(173,198,255,0.08)', border:'1px solid rgba(173,198,255,0.15)', borderRadius:'8px', marginBottom:'24px', fontSize:'13px', color:'var(--text-secondary)', display:'flex', alignItems:'center', gap:'8px'}}> 
          <Info size={14} /> 
          Some settings require admin access. Contact your administrator to make changes. 
        </div> 
      )}
      <SettingsSection title="Monitor Configuration" icon={<Activity size={20} />}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <SettingsField label="Epic Connection Status" value="Demo Mode — Synthetic Data" disabled />
          <SettingsField label="Monitoring Window" value="2026-01-05 to 2026-03-31" disabled />
          <SettingsField label="Employees Monitored" value="80" disabled />
        </div>
      </SettingsSection>

      <SettingsSection title="Alert Thresholds" icon={<AlertTriangle size={20} />}>
        {userRole !== 'admin' && <p style={{fontSize:'12px', color:'var(--text-secondary)', marginBottom:'12px'}}>View only — admin access required to modify thresholds.</p>}
        <div style={{opacity: userRole === 'admin' ? 1 : 0.5, pointerEvents: userRole === 'admin' ? 'auto' : 'none'}}> 
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Critical Threshold</label>
              <input 
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={thresholds.critical}
                onChange={(e) => setThresholds({...thresholds, critical: parseFloat(e.target.value) || 0})}
                style={{ 
                  background: 'var(--bg-elevated)', 
                  border: '1px solid var(--border)', 
                  borderRadius: '6px', 
                  padding: '10px 14px', 
                  fontSize: '13px', 
                  color: 'var(--text-primary)', 
                  fontFamily: "'JetBrains Mono', monospace", 
                  outline: 'none', 
                  width: '100%',
                  cursor: 'text'
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>High Threshold</label>
              <input 
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={thresholds.high}
                onChange={(e) => setThresholds({...thresholds, high: parseFloat(e.target.value) || 0})}
                style={{ 
                  background: 'var(--bg-elevated)', 
                  border: '1px solid var(--border)', 
                  borderRadius: '6px', 
                  padding: '10px 14px', 
                  fontSize: '13px', 
                  color: 'var(--text-primary)', 
                  fontFamily: "'JetBrains Mono', monospace", 
                  outline: 'none', 
                  width: '100%',
                  cursor: 'text'
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Medium Threshold</label>
              <input 
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={thresholds.medium}
                onChange={(e) => setThresholds({...thresholds, medium: parseFloat(e.target.value) || 0})}
                style={{ 
                  background: 'var(--bg-elevated)', 
                  border: '1px solid var(--border)', 
                  borderRadius: '6px', 
                  padding: '10px 14px', 
                  fontSize: '13px', 
                  color: 'var(--text-primary)', 
                  fontFamily: "'JetBrains Mono', monospace", 
                  outline: 'none', 
                  width: '100%',
                  cursor: 'text'
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
              />
            </div>
          </div>
          
          {/* Success/Error Message */}
          {thresholdMessage.text && (
            <div style={{ 
              marginTop: '16px',
              padding: '12px 16px', 
              background: thresholdMessage.type === 'success' ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)', 
              border: `1px solid ${thresholdMessage.type === 'success' ? 'rgba(16,185,129,0.2)' : 'rgba(244,63,94,0.2)'}`, 
              borderRadius: '8px', 
              color: thresholdMessage.type === 'success' ? '#10B981' : '#f43f5e', 
              fontSize: '13px',
              fontWeight: '500',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              {thresholdMessage.type === 'success' ? '✓' : '⚠'} {thresholdMessage.text}
            </div>
          )}
          
          {/* Save Button */}
          <button
            onClick={handleSaveThresholds}
            disabled={savingThresholds}
            style={{
              marginTop: '16px',
              padding: '12px 24px',
              background: savingThresholds ? 'var(--text-muted)' : 'var(--accent)',
              color: savingThresholds ? 'var(--bg-elevated)' : '#0b1326',
              border: 'none',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: '700',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              cursor: savingThresholds ? 'not-allowed' : 'pointer',
              opacity: savingThresholds ? 0.7 : 1,
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => !savingThresholds && (e.target.style.background = 'var(--accent-hover)')}
            onMouseLeave={(e) => !savingThresholds && (e.target.style.background = 'var(--accent)')}
          >
            {savingThresholds ? 'Saving...' : 'Save Thresholds'}
          </button>
        </div>
      </SettingsSection>

      <SettingsSection title="Account" icon={<User size={20} />}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <SettingsField label="Username" value={userEmail || 'demo'} disabled />
          <SettingsField label="Role" value={userRole ? userRole.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'User'} disabled />
        </div>
        
        <div style={{display:'flex', flexDirection:'column', gap:'8px'}}> 
          <label style={{fontSize:'11px', fontWeight:'600', letterSpacing:'0.05em', color:'var(--text-secondary)'}}>EMAIL</label> 
          <div style={{display:'flex', gap:'8px'}}> 
            <input 
              type='email' 
              defaultValue={userEmail} 
              id='emailUpdateInput' 
              style={{flex:1, padding:'12px', background:'var(--bg-app)', border:'1px solid var(--border)', borderRadius:'8px', color:'var(--text-primary)', fontSize:'14px'}} 
            /> 
            <button onClick={async () => { 
              const newEmail = document.getElementById('emailUpdateInput').value; 
              if (!newEmail || !newEmail.includes('@')) return; 
              try { 
                const res = await secureFetch('https://sentinelehr.onrender.com/users/update-email', { 
                  method: 'POST', 
                  headers: authHeaders(), 
                  body: JSON.stringify({new_email: newEmail}) 
                }); 
                if (res.ok) showToast('Email updated. Please log in again.'); 
              } catch { showToast('Failed to update email', 'error'); } 
            }} 
            style={{padding:'12px 20px', background:'var(--accent)', border:'none', borderRadius:'8px', color:'#000', fontWeight:'700', cursor:'pointer', whiteSpace:'nowrap'}}> 
              UPDATE 
            </button> 
          </div> 
        </div>

        <button 
          onClick={() => setShowPasswordForm(!showPasswordForm)} 
          style={{ 
            marginTop: '16px', padding: '12px 20px', background: 'var(--bg-elevated)', 
            color: 'var(--text-primary)', border: '1px solid var(--border)', 
            borderRadius: '8px', fontSize: '12px', fontWeight: '600', 
            textTransform: 'uppercase', letterSpacing: '0.05em', cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onMouseEnter={(e) => e.target.style.borderColor = 'var(--accent)'}
          onMouseLeave={(e) => e.target.style.borderColor = 'var(--border)'}
        >
          Change Password
        </button>

        {showPasswordForm && ( 
          <div style={{marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '400px'}}> 
            <input type='password' placeholder='Current password' 
              value={passwordData.current} 
              onChange={e => setPasswordData({...passwordData, current: e.target.value})} 
              style={{padding: '12px', background: 'var(--bg-app)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text-primary)'}} 
            /> 
            <input type='password' placeholder='New password (min 8 characters)' 
              value={passwordData.new} 
              onChange={e => setPasswordData({...passwordData, new: e.target.value})} 
              style={{padding: '12px', background: 'var(--bg-app)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text-primary)'}} 
            /> 
            <input type='password' placeholder='Confirm new password' 
              value={passwordData.confirm} 
              onChange={e => setPasswordData({...passwordData, confirm: e.target.value})} 
              style={{padding: '12px', background: 'var(--bg-app)', border: '1px solid var(--border)', borderRadius: '8px', color: 'var(--text-primary)'}} 
            /> 
            <button onClick={async () => { 
              if (passwordData.new !== passwordData.confirm) { 
                setPasswordMsg({type: 'error', text: 'New passwords do not match'}); 
                return; 
              } 
              if (passwordData.new.length < 8) { 
                setPasswordMsg({type: 'error', text: 'Password must be at least 8 characters'}); 
                return; 
              } 
              try { 
                const res = await secureFetch('https://sentinelehr.onrender.com/users/change-password', { 
                  method: 'POST', 
                  headers: authHeaders(), 
                  body: JSON.stringify({current_password: passwordData.current, new_password: passwordData.new}) 
                }); 
                const data = await res.json(); 
                if (res.ok) { 
                  setPasswordMsg({type: 'success', text: 'Password updated successfully'}); 
                  setPasswordData({current: '', new: '', confirm: ''}); 
                  setTimeout(() => setShowPasswordForm(false), 2000); 
                } else { 
                  setPasswordMsg({type: 'error', text: data.detail || 'Failed to update password'}); 
                } 
              } catch { 
                setPasswordMsg({type: 'error', text: 'Connection error'}); 
              } 
            }} 
            style={{padding: '12px', background: 'var(--accent)', border: 'none', borderRadius: '8px', color: '#000', fontWeight: '700', cursor: 'pointer'}}> 
              UPDATE PASSWORD 
            </button> 
            {passwordMsg && ( 
              <div style={{padding: '10px', borderRadius: '6px', 
                background: passwordMsg.type === 'success' ? 'rgba(0,200,100,0.1)' : 'rgba(255,50,50,0.1)', 
                color: passwordMsg.type === 'success' ? '#00c864' : '#ff4444', 
                fontSize: '13px'}}> 
                {passwordMsg.text} 
              </div> 
            )} 
          </div> 
        )} 
      </SettingsSection>
    </div>
  );
};


const InvestigateTab = ({ investigateId, setInvestigateId, handleInvestigate, investigateResults, investigating }) => (
  <div> 
    {/* Query Section */}
    <div className="w-full" style={{
      background: '#0b1c30',
      border: '1px solid rgba(140,144,159,0.2)',
      borderRadius: '12px',
      padding: '24px',
      marginBottom: '24px'
    }}>
      <form onSubmit={handleInvestigate} style={{ display: 'flex', gap: '16px', alignItems: 'flex-end' }}> 
        <div style={{ flex: 1 }}>
          <div style={{
            fontSize: '10px',
            fontWeight: '600',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: '#879298',
            marginBottom: '8px'
          }}>Employee ID</div>
          <div style={{ position: 'relative' }}>
            <User size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#879298' }} />
            <input 
              id="employee-search"
              name="employee-search"
              type="text" 
              value={investigateId} 
              onChange={e => setInvestigateId(e.target.value)} 
              placeholder="Enter EMP-ID (e.g. 10042)" 
              style={{ 
                background: '#000f21', 
                border: '1px solid rgba(140,144,159,0.2)', 
                borderRadius: '8px', 
                padding: '10px 14px 10px 40px', 
                fontSize: '13px', 
                color: '#d3e4fe', 
                fontFamily: "'JetBrains Mono', monospace", 
                outline: 'none', 
                width: '100%',
                transition: 'border-color 0.2s'
              }}
              onFocus={e => e.target.style.borderColor = '#4a9eff'}
              onBlur={e => e.target.style.borderColor = '#3e484d'}
            /> 
          </div>
        </div>
        <button 
          type="submit" 
          disabled={investigating} 
          style={{ 
            padding: '10px 24px', 
            background: '#2563eb', 
            color: '#fff', 
            border: 'none', 
            borderRadius: '8px', 
            fontSize: '12px', 
            fontWeight: '700', 
            textTransform: 'uppercase', 
            letterSpacing: '0.05em', 
            cursor: investigating ? 'default' : 'pointer', 
            opacity: investigating ? 0.7 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'all 0.2s'
          }}
          onMouseEnter={e => !investigating && (e.currentTarget.style.background = '#1d4ed8')}
          onMouseLeave={e => !investigating && (e.currentTarget.style.background = '#2563eb')}
        > 
          <Search size={16} />
          {investigating ? 'Searching...' : 'Run Query'} 
        </button> 
      </form> 
    </div>

    {investigateResults?.error && ( 
      <div style={{ 
        padding: '24px', 
        background: 'rgba(244,63,94,0.1)', 
        color: '#f43f5e', 
        borderRadius: '10px', 
        border: '1px solid #f43f5e', 
        fontSize: '14px', 
        marginBottom: '24px', 
        display: 'flex', 
        alignItems: 'center', 
        gap: '12px' 
      }}> 
        <AlertTriangle size={20} />
        <span>{investigateResults.error}</span> 
      </div> 
    )} 

    {/* Empty State */}
    {!investigateResults && !investigating && (
      <div className="w-full" style={{
        background: '#0b1c30',
        border: '1px solid rgba(140,144,159,0.2)',
        borderRadius: '12px',
        padding: '64px',
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <ScanSearch size={48} style={{
          color: '#adc6ff',
          opacity: 0.3,
          marginBottom: '24px'
        }} />
        <div style={{
          fontSize: '18px',
          fontWeight: '600',
          color: '#94a3b8',
          marginBottom: '12px'
        }}>Enter an Employee ID to begin investigation</div>
        <div style={{
          fontSize: '14px',
          color: '#64748b'
        }}>Search by employee number (e.g. 10042)</div>
      </div>
    )}

    <InvestigateResults results={investigateResults} />
  </div> 
);

const CaseReportModal = ({ report, onClose }) => {
  if (!report) return null;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div style={{ 
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', 
      backdropFilter: 'blur(8px)', zIndex: 1000, display: 'flex', 
      alignItems: 'center', justifyContent: 'center', padding: '40px'
    }}>
      <div style={{ 
        background: '#fff', color: '#111827', width: '100%', maxWidth: '900px', 
        height: '90vh', borderRadius: '16px', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)', overflow: 'hidden'
      }}>
        {/* Modal Header */}
        <div className="no-print" style={{ 
          padding: '16px 24px', borderBottom: '1px solid #E5E7EB', 
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: '#F9FAFB'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <FileText size={20} color="#E11D48" />
            <h2 style={{ fontSize: '16px', fontWeight: '700', textTransform: 'uppercase', color: '#374151' }}>Investigation Report: {report.case_metadata.case_id}</h2>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={handlePrint} style={{ 
              padding: '8px 16px', background: '#374151', color: '#fff', 
              border: 'none', borderRadius: '6px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: '600'
            }}>
              <Printer size={16} /> Print
            </button>
            <button onClick={onClose} style={{ 
              background: 'transparent', border: 'none', color: '#9CA3AF', cursor: 'pointer', padding: '4px'
            }}>
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div style={{ padding: '48px', overflowY: 'auto', flex: 1 }} id="printable-report">
          <style>{`
            @media print {
              .no-print { display: none !important; }
              body { background: #fff !important; }
              #printable-report { padding: 0 !important; }
            }
          `}</style>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '40px', borderBottom: '2px solid #111827', paddingBottom: '24px' }}>
            <div>
              <h1 style={{ fontSize: '28px', fontWeight: '800', color: '#111827', marginBottom: '4px' }}>SentinelEHR</h1>
              <p style={{ fontSize: '12px', fontWeight: '700', color: '#E11D48', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Insider Risk Investigation</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: '#6B7280' }}>Report Generated:</div>
              <div style={{ fontSize: '14px', fontWeight: '700', color: '#111827' }}>{new Date(report.report_generated_at).toLocaleString()}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px', marginBottom: '40px' }}>
            <div>
              <h3 style={{ fontSize: '12px', fontWeight: '800', color: '#6B7280', textTransform: 'uppercase', marginBottom: '12px', borderBottom: '1px solid #E5E7EB', paddingBottom: '4px' }}>Employee Information</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr', gap: '8px', fontSize: '14px' }}>
                <div style={{ fontWeight: '600', color: '#6B7280' }}>ID:</div>
                <div style={{ fontWeight: '700', fontFamily: 'monospace' }}>EMP-{report.employee_info?.emp_id}</div>
                <div style={{ fontWeight: '600', color: '#6B7280' }}>Role:</div>
                <div style={{ fontWeight: '600' }}>{report.employee_info?.role}</div>
                <div style={{ fontWeight: '600', color: '#6B7280' }}>Department:</div>
                <div style={{ fontWeight: '600' }}>Dept {report.employee_info?.dept_id}</div>
              </div>
            </div>
            <div>
              <h3 style={{ fontSize: '12px', fontWeight: '800', color: '#6B7280', textTransform: 'uppercase', marginBottom: '12px', borderBottom: '1px solid #E5E7EB', paddingBottom: '4px' }}>Case Metadata</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '100px 1fr', gap: '8px', fontSize: '14px' }}>
                <div style={{ fontWeight: '600', color: '#6B7280' }}>Case ID:</div>
                <div style={{ fontWeight: '700', fontFamily: 'monospace', color: '#E11D48' }}>{report.case_metadata.case_id}</div>
                <div style={{ fontWeight: '600', color: '#6B7280' }}>Priority:</div>
                <div style={{ fontWeight: '700' }}>{report.case_metadata.priority}</div>
                <div style={{ fontWeight: '600', color: '#6B7280' }}>Current Status:</div>
                <div style={{ fontWeight: '700' }}>{report.case_metadata.status}</div>
              </div>
            </div>
          </div>

          <h3 style={{ fontSize: '12px', fontWeight: '800', color: '#6B7280', textTransform: 'uppercase', marginBottom: '16px', borderBottom: '1px solid #E5E7EB', paddingBottom: '4px' }}>Linked Alerts</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '40px' }}>
            <thead>
              <tr style={{ background: '#F3F4F6' }}>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>Date</th>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>Severity</th>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>Rules Triggered</th>
                <th style={{ padding: '10px', textAlign: 'right', fontSize: '11px', fontWeight: '700', textTransform: 'uppercase' }}>Score</th>
              </tr>
            </thead>
            <tbody>
              {report.linked_alerts.map((a, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #E5E7EB' }}>
                  <td style={{ padding: '10px', fontSize: '13px' }}>{new Date(a.alert_date).toLocaleDateString()}</td>
                  <td style={{ padding: '10px', fontSize: '13px', fontWeight: '600' }}>{a.adjusted_severity}</td>
                  <td style={{ padding: '10px', fontSize: '12px', color: '#4B5563' }}>{a.rules_triggered}</td>
                  <td style={{ padding: '10px', fontSize: '13px', textAlign: 'right', fontWeight: '700' }}>{a.anomaly_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 style={{ fontSize: '12px', fontWeight: '800', color: '#6B7280', textTransform: 'uppercase', marginBottom: '16px', borderBottom: '1px solid #E5E7EB', paddingBottom: '4px' }}>Timeline & Notes</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {report.timeline.map((t, i) => (
              <div key={i} style={{ borderLeft: '2px solid #E5E7EB', paddingLeft: '16px', position: 'relative' }}>
                <div style={{ position: 'absolute', left: '-5px', top: '0', width: '8px', height: '8px', borderRadius: '50%', background: '#E11D48' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: '700', color: '#111827' }}>{t.action.toUpperCase()}</span>
                  <span style={{ fontSize: '11px', color: '#6B7280' }}>{new Date(t.timestamp).toLocaleString()} by {t.actor_name || 'System'}</span>
                </div>
                {t.note && <p style={{ fontSize: '13px', color: '#4B5563', margin: 0, fontStyle: 'italic' }}>"{t.note}"</p>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default function AppV2() {
  const [theme, setTheme] = useState(localStorage.getItem('sentinel_theme') || 'dark');
  // Store auth in memory only (not localStorage) for security
  const [token, setToken] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [userEmail, setUserEmail] = useState(null);
  const [userOrganization, setUserOrganization] = useState(null);
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
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
  const [createCaseStatus, setCreateCaseStatus] = useState({ loading: false, message: '', type: '' })
  
  const [cases, setCases] = useState([]) 
  const [casesTotal, setCasesTotal] = useState(0) 
  const [casesLoading, setCasesLoading] = useState(false) 
  const [caseStatusFilter, setCaseStatusFilter] = useState('Open') 
  const [casePriorityFilter, setCasePriorityFilter] = useState('') 
  const [casesOffset, setCasesOffset] = useState(0) 
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState({ alerts: [], cases: [], employees: [] })
  const [searchDropdownOpen, setSearchDropdownOpen] = useState(false) 
  const [selectedCase, setSelectedCase] = useState(null) 
  const [caseDetail, setCaseDetail] = useState(null) 
  const [caseNote, setCaseNote] = useState('') 
  const [caseStatusUpdate, setCaseStatusUpdate] = useState('') 
  const [caseOutcome, setCaseOutcome] = useState('') 
  const [savingCase, setSavingCase] = useState(false) 
  
  const [investigateId, setInvestigateId] = useState('') 
  const [thresholds, setThresholds] = useState({ critical: 0.7, high: 0.4, medium: 0.2 })
  const [savingThresholds, setSavingThresholds] = useState(false)
  const [thresholdMessage, setThresholdMessage] = useState({ type: '', text: '' }) 
  const [investigateResults, setInvestigateResults] = useState(null) 
  const [investigating, setInvestigating] = useState(false) 
  
  const [caseReport, setCaseReport] = useState(null)
  const [generatingReport, setGeneratingReport] = useState(false)
  const [exportingAlerts, setExportingAlerts] = useState(false)
  const [alertDateFilter, setAlertDateFilter] = useState(null)
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false)
  const [showUnsavedWarning, setShowUnsavedWarning] = useState(false)
  const [unsavedWarningType, setUnsavedWarningType] = useState(null)
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' })

  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast(prev => ({ ...prev, show: false })), 4000);
  };
  
  const LIMIT = 50 

  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const searchContainerRef = useRef(null);

  useEffect(() => {
    applyTheme(theme);
    localStorage.setItem('sentinel_theme', theme);
  }, [theme]);

  // Close search dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target)) {
        setSearchDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Redirect it_director away from investigate tab
  useEffect(() => {
    if (userRole === 'it_director' && activeView === 'investigate') {
      setActiveView('overview');
    }
  }, [userRole, activeView]);

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
        // Store in memory only (not localStorage)
        setToken(data.access_token);
        setUserRole(data.role);
        setUserEmail(data.email);
        setUserOrganization(data.organization);
      } else {
        const errData = await res.json().catch(() => ({}));
        setLoginError(errData.detail || 'Incorrect email or password');
      }
    } catch (e) {
      setLoginError('Cannot connect to server');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    // Clear memory-only auth state
    setToken(null);
    setUserRole(null);
    setUserEmail(null);
    setUserOrganization(null);
  };

  const secureFetch = async (url, options = {}) => {
    // Merge auth headers into options
    const secureOptions = {
      ...options,
      headers: {
        ...authHeaders(),
        ...(options.headers || {})
      }
    };
    try {
      const res = await fetch(url, secureOptions);
      
      if (res.status === 401) {
        // Clone response to read body without consuming original
        const clone = res.clone();
        try {
          const data = await clone.json();
          const detail = String(data.detail || "").toLowerCase();
          
          if (detail.includes("expired") || detail.includes("invalid or expired token")) {
            handleLogout();
            showToast('Session expired. Please log in again.', 'error');
          } else {
            showToast(data.detail || 'Unauthorized access', 'error');
          }
        } catch (e) {
          // If body is not JSON or parsing fails
          showToast('Unauthorized access', 'error');
        }
        return res;
      }

      // Check for specific error message in JSON responses (for other status codes)
      const contentType = res.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const clone = res.clone();
        try {
          const data = await clone.json();
          const detail = String(data.detail || "").toLowerCase();
          if (detail.includes("invalid or expired token") || detail.includes("token expired")) {
            handleLogout();
            showToast('Session expired. Please log in again.', 'error');
          }
        } catch (e) {
          // Not JSON or parse error, ignore
        }
      }

      return res;
    } catch (e) {
      throw e;
    }
  };

  const handleCloseAlertDrawer = () => {
    if (alertNote && alertNote.trim().length > 0) {
      setUnsavedWarningType('alert');
      setShowUnsavedWarning(true);
    } else {
      setSelectedAlert(null);
    }
  };

  const handleCloseCaseDrawer = () => {
    if (caseNote && caseNote.trim().length > 0) {
      setUnsavedWarningType('case');
      setShowUnsavedWarning(true);
    } else {
      setSelectedCase(null);
    }
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
        secureFetch(`${API_BASE}/summary`, 
          {headers: authHeaders()}), 
        secureFetch(`${API_BASE}/digest?days=180`, 
          {headers: authHeaders()}) 
      ]) 
      if (sumRes.ok) setSummary(await sumRes.json()) 
      if (digRes.ok) { 
        const d = await digRes.json() 
        setDigest(Array.isArray(d) ? d : []) 
      } 
      // Also fetch alerts for overview stats
      fetchAlerts();
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
      const res = await secureFetch(`${API_BASE}/alerts?${query}`, { 
        headers: authHeaders() 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        setAlerts(data.alerts || []) 
        setAlertsTotal(data.total_count || data.total || (data.alerts?.length || 0)) 
      } 
    } catch(e) { console.error(e) } 
    setAlertsLoading(false) 
  } 
  
  const fetchAlertDetail = async (id) => { 
    try { 
      const res = await secureFetch(`${API_BASE}/alerts/${id}`, { 
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
      const res = await secureFetch(`${API_BASE}/alerts/${selectedAlert}/status`, { 
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

  const handleCreateCaseFromAlert = async (alertId) => {
    setCreateCaseStatus({ loading: true, message: '', type: '' });
    try {
      const res = await secureFetch(`${API_BASE}/alerts/${alertId}/create-case`, {
        method: 'POST',
        headers: authHeaders()
      });
      if (res.ok) {
        setCreateCaseStatus({ loading: false, message: 'Case created successfully', type: 'success' });
        fetchCases();
        setTimeout(() => setCreateCaseStatus({ loading: false, message: '', type: '' }), 3000);
      } else {
        setCreateCaseStatus({ loading: false, message: 'Failed to create case — check if case already exists', type: 'error' });
      }
    } catch (e) {
      console.error(e);
      setCreateCaseStatus({ loading: false, message: 'Failed to create case — check connection', type: 'error' });
    }
  };
  
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
      const res = await secureFetch(`${API_BASE}/cases?${query}`, { 
        headers: authHeaders() 
      }) 
      if (res.ok) { 
        const data = await res.json() 
        setCases(data.cases || []) 
        setCasesTotal(data.total_count || 0) 
      } 
    } catch(e) { console.error(e) } 
    setCasesLoading(false) 
  } 
  
  const fetchCaseDetail = async (id) => { 
    try { 
      const res = await secureFetch(`${API_BASE}/cases/${id}`, { 
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
        await secureFetch(`${API_BASE}/cases/${selectedCase}/status`, { 
          method: 'PATCH', 
          headers: authHeaders(), 
          body: JSON.stringify({ 
            status: caseStatusUpdate, 
            note: caseNote || 'Status updated' 
          }) 
        }) 
      } 
      if (caseOutcome && caseOutcome !== caseDetail.outcome) { 
        await secureFetch(`${API_BASE}/cases/${selectedCase}/outcome`, { 
          method: 'PATCH', 
          headers: authHeaders(), 
          body: JSON.stringify({ outcome: caseOutcome }) 
        }) 
      } 
      if (caseNote.trim()) { 
        await secureFetch(`${API_BASE}/cases/${selectedCase}/notes`, { 
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

  const handleInvestigate = async (e) => { 
    e.preventDefault(); 
    if (!investigateId) return; 
    setInvestigating(true); 
    try { 
      const res = await secureFetch(`${API_BASE}/employees/${investigateId}/profile`, { 
        headers: authHeaders() 
      }); 
      if (res.ok) { 
        setInvestigateResults(await res.json()); 
      } else { 
        setInvestigateResults({ error: "Employee profile not found. Please verify the ID." }); 
      } 
    } catch(e) { 
      console.error(e); 
      setInvestigateResults({ error: "Failed to connect to investigation service." });
    } 
    setInvestigating(false); 
  };

  const handleSaveThresholds = async () => {
    if (!token) return;
    setSavingThresholds(true);
    setThresholdMessage({ type: '', text: '' });
    
    try {
      const res = await secureFetch(`${API_BASE}/settings/thresholds`, {
        method: 'PUT',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          critical_threshold: thresholds.critical,
          high_threshold: thresholds.high,
          medium_threshold: thresholds.medium
        })
      });
      
      if (res.ok) {
        setThresholdMessage({ type: 'success', text: 'Thresholds updated' });
        setTimeout(() => setThresholdMessage({ type: '', text: '' }), 3000);
      } else {
        const data = await res.json().catch(() => ({}));
        setThresholdMessage({ 
          type: 'error', 
          text: data.message || 'Failed to update thresholds' 
        });
      }
    } catch(e) {
      console.error(e);
      setThresholdMessage({ type: 'error', text: 'Network error. Please try again.' });
    }
    setSavingThresholds(false);
  };

  const handleLookup = async (id) => {
    if (!id || !token) return;
    setInvestigating(true);
    setInvestigateId(id);
    try {
      const res = await secureFetch(`${API_BASE}/employees/${id}/profile`, {
        headers: authHeaders()
      });
      if (res.ok) {
        setInvestigateResults(await res.json());
      } else {
        setInvestigateResults({ error: "Employee profile not found. Please verify the ID." });
      }
    } catch(e) {
      console.error(e);
      setInvestigateResults({ error: "Failed to connect to investigation service." });
    }
    setInvestigating(false);
  };

  const handleGlobalSearch = (query) => {
    setSearchQuery(query);
    
    if (!query || query.trim().length < 2) {
      setSearchResults({ alerts: [], cases: [], employees: [] });
      setSearchDropdownOpen(false);
      return;
    }

    const lowerQuery = query.toLowerCase();
    
    // Search alerts
    const matchingAlerts = alerts.filter(alert => 
      String(alert.emp_id).includes(query) ||
      (alert.rules_triggered && alert.rules_triggered.toLowerCase().includes(lowerQuery)) ||
      (alert.explanation && alert.explanation.toLowerCase().includes(lowerQuery))
    ).slice(0, 5);

    // Search cases
    const matchingCases = cases.filter(c => 
      String(c.case_id).toLowerCase().includes(lowerQuery) ||
      String(c.emp_id).includes(query)
    ).slice(0, 5);

    // Search employees (from alert emp_ids)
    const uniqueEmpIds = [...new Set(alerts.map(a => a.emp_id))];
    const matchingEmployees = uniqueEmpIds.filter(empId => 
      String(empId).includes(query)
    ).slice(0, 5);

    setSearchResults({
      alerts: matchingAlerts,
      cases: matchingCases,
      employees: matchingEmployees
    });
    setSearchDropdownOpen(true);
  };

  const handleSearchResultClick = async (type, item) => {
    setSearchDropdownOpen(false);
    setSearchQuery('');
    
    if (type === 'alerts') {
      setActiveView('alerts');
      setSelectedAlert(item.alert_id);
      await fetchAlertDetail(item.alert_id);
    } else if (type === 'cases') {
      setActiveView('cases');
      setSelectedCase(item.case_id);
      await fetchCaseDetail(item.case_id);
    } else if (type === 'employees') {
      setActiveView('investigate');
      setInvestigateId(String(item));
      handleLookup(String(item));
    }
  };

  const handleExportAlerts = async () => {
    setExportingAlerts(true);
    try {
      const query = new URLSearchParams({
        severity: alertSeverity,
        status: alertStatus
      });
      const res = await secureFetch(`${API_BASE}/export/alerts?${query}`, {
        headers: authHeaders()
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const date = new Date().toISOString().split('T')[0];
        a.download = `sentinelehr_alerts_${date}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    } catch (e) {
      console.error('Export failed', e);
    }
    setExportingAlerts(false);
  };

  const handleGenerateReport = async (caseId) => {
    console.log('Report button clicked for case:', caseId);
    try {
      const res = await secureFetch(`${API_BASE}/export/case/${caseId}`);
      console.log('Response status:', res.status);
      if (!res.ok) {
        const err = await res.text();
        console.error('API error:', err);
        showToast('Failed to load report: ' + err, 'error');
        return;
      }
      const data = await res.json();
      console.log('Report data received:', data);
      setCaseReport(data);
    } catch (err) {
      console.error('Report fetch failed:', err);
      showToast('Error: ' + err.message, 'error');
    }
  };
  
  useEffect(() => { 
    if (token && activeView === 'overview') fetchOverviewData() 
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
    const last30 = [...digest].slice(-30).reverse()
    const labels = last30.map(d => { 
      const date = new Date(d.alert_date) 
      return date.toLocaleDateString('en-US', 
        {month:'short', day:'numeric'}) 
    }) 
    chartInstanceRef.current = new window.Chart(ctx, { 
      type: 'bar', 
      data: { 
        labels, 
        datasets: [ 
          { 
            label:'Critical', 
            data: last30.map(d => d.critical_count||0), 
            borderColor: '#f43f5e', 
            backgroundColor: '#f43f5e',
            borderWidth: 1
          }, 
          { 
            label:'High', 
            data: last30.map(d => d.high_count||0), 
            borderColor: '#f97316', 
            backgroundColor: '#f97316',
            borderWidth: 1
          }, 
          { 
            label:'Medium', 
            data: last30.map(d => d.medium_count||0), 
            borderColor: '#3b82f6', 
            backgroundColor: '#3b82f6',
            borderWidth: 1
          }
        ] 
      }, 
      options: { 
        responsive: true, 
        maintainAspectRatio: false, 
        interaction: {mode:'index', intersect:false}, 
        onClick: (event, elements) => {
          if (!elements || elements.length === 0) return;
          const index = elements[0].index;
          const rawDate = last30[index]?.alert_date;
          if (!rawDate) return;
          // Normalise to YYYY-MM-DD
          const dateStr = rawDate.split('T')[0];
          setAlertDateFilter(dateStr);
          setActiveView('alerts');
        },
        plugins: { 
          legend: {display: false}, 
          tooltip: { 
            callbacks: { 
              title: (items) => items[0]?.label || '', 
              label: (ctx) => { 
                return '  ' + ctx.dataset.label + ': ' + ctx.parsed.y 
              } 
            }, 
            backgroundColor: '#102034', 
            borderColor: '#3e484d', 
            borderWidth: 1, 
            titleColor: '#d3e4fe', 
            bodyColor: '#bdc8ce', 
            padding: 12,
            cornerRadius: 8
          } 
        }, 
        scales: { 
          x: { 
            stacked: false,
            grid: {
              display: true,
              color: 'rgba(255,255,255,0.05)',
              drawBorder: false,
              lineWidth: 1
            }, 
            border: { 
              color:'#3e484d',
              display: false
            }, 
            ticks: { 
              color:'#879298', 
              font:{size:10}, 
              maxTicksLimit:8 
            } 
          }, 
          y: { 
            stacked: false,
            min: 0, 
            grid: {
              color: 'rgba(255,255,255,0.05)',
              drawBorder: false,
              lineWidth: 1
            }, 
            border: {display:false}, 
            ticks: { 
              color:'#879298', 
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
        fontFamily: "'DM Sans', sans-serif"
      }}>
        {/* LEFT COLUMN - 40% */}
        <div style={{ 
          width: '40%', 
          background: '#060e20', 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '48px',
          borderRight: '1px solid rgba(140,144,159,0.2)'
        }}>
          {/* Centered Shield Icon */}
          <div style={{ marginBottom: '32px' }}>
            <img src='/sentinelehr-logo.png' alt='SentinelEHR' style={{width:'180px', height:'180px', objectFit:'contain'}} />
          </div>

          {/* Headline */}
          <h1 style={{
            fontSize: '32px',
            fontWeight: '800',
            color: '#ffffff',
            marginBottom: '48px',
            textAlign: 'center',
            lineHeight: 1.2,
            letterSpacing: '-0.02em'
          }}>Healthcare Insider<br />Risk Intelligence</h1>

          {/* Three Stat Boxes */}
          <div style={{
            display: 'flex',
            gap: '16px',
            width: '100%',
            maxWidth: '480px'
          }}>
            <div style={{
              flex: 1,
              background: '#0b1326',
              border: '1px solid rgba(140,144,159,0.2)',
              borderRadius: '12px',
              padding: '20px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '28px', fontWeight: '700', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>325K</div>
              <div style={{ fontSize: '11px', color: '#879298', marginTop: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Events</div>
            </div>
            <div style={{
              flex: 1,
              background: '#0b1326',
              border: '1px solid rgba(140,144,159,0.2)',
              borderRadius: '12px',
              padding: '20px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '28px', fontWeight: '700', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>0</div>
              <div style={{ fontSize: '11px', color: '#879298', marginTop: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>PHI Stored</div>
            </div>
            <div style={{
              flex: 1,
              background: '#0b1326',
              border: '1px solid rgba(140,144,159,0.2)',
              borderRadius: '12px',
              padding: '20px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '28px', fontWeight: '700', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>86%</div>
              <div style={{ fontSize: '11px', color: '#879298', marginTop: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Precision</div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN - 60% */}
        <div style={{ 
          flex: 1, 
          background: '#0b1326',
          display: 'flex',
          flexDirection: 'column',
          padding: '48px 64px',
          position: 'relative'
        }}>
          {/* Top: Logo */}
          <div style={{ marginBottom: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'transparent',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <img src='/sentinelehr-logo.png' alt='SentinelEHR' style={{width:'36px', height:'36px', objectFit:'contain'}} />
              </div>
              <span style={{ fontWeight: '700', fontSize: '20px', color: '#adc6ff' }}>SentinelEHR</span>
            </div>
          </div>

          {/* Center: Login Form */}
          <div style={{ width: '100%', maxWidth: '440px', margin: '0 auto' }}>
            <h2 style={{ fontSize: '40px', fontWeight: '800', color: '#d3e4fe', marginBottom: '12px', letterSpacing: '-0.02em' }}>Secure Access</h2>
            <p style={{ color: '#879298', marginBottom: '48px', fontSize: '16px', lineHeight: '1.6' }}>Enter credentials to access the compliance terminal.</p>

            <form onSubmit={handleLogin}>
              {/* Email Field */}
              <div style={{ marginBottom: '24px' }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '11px', 
                  fontWeight: '600', 
                  textTransform: 'uppercase', 
                  color: '#879298', 
                  marginBottom: '10px',
                  letterSpacing: '0.1em'
                }}>Email</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={20} style={{ 
                    position: 'absolute', 
                    left: '16px', 
                    top: '50%', 
                    transform: 'translateY(-50%)', 
                    color: '#879298'
                  }} />
                  <input 
                    id="corporate-email"
                    name="email"
                    autoComplete="email"
                    type="email" 
                    value={loginForm.email}
                    onChange={e => setLoginForm({...loginForm, email: e.target.value})}
                    required
                    placeholder="name@company.com"
                    style={{
                      width: '100%',
                      padding: '14px 16px 14px 48px',
                      backgroundColor: '#131b2e',
                      color: '#d3e4fe',
                      border: '1px solid rgba(140,144,159,0.2)',
                      borderRadius: '10px',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '14px',
                      outline: 'none',
                      boxSizing: 'border-box',
                      transition: 'all 0.2s ease'
                    }}
                    onFocus={e => {
                      e.target.style.borderColor = '#adc6ff';
                      e.target.style.boxShadow = '0 0 0 1px rgba(173,198,255,0.2)';
                    }}
                    onBlur={e => {
                      e.target.style.borderColor = 'rgba(140,144,159,0.2)';
                      e.target.style.boxShadow = 'none';
                    }}
                  />
                </div>
              </div>

              {/* Password Field */}
              <div style={{ marginBottom: '32px' }}>
                <label style={{ 
                  display: 'block', 
                  fontSize: '11px', 
                  fontWeight: '600', 
                  textTransform: 'uppercase', 
                  color: '#879298', 
                  marginBottom: '10px',
                  letterSpacing: '0.1em'
                }}>Password</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={20} style={{ 
                    position: 'absolute', 
                    left: '16px', 
                    top: '50%', 
                    transform: 'translateY(-50%)', 
                    color: '#879298'
                  }} />
                  <input 
                    id="password"
                    name="password"
                    autoComplete="current-password"
                    type={showPassword ? 'text' : 'password'} 
                    value={loginForm.password}
                    onChange={e => setLoginForm({...loginForm, password: e.target.value})}
                    required
                    placeholder="••••••••"
                    style={{
                      width: '100%',
                      padding: '14px 48px 14px 48px',
                      backgroundColor: '#131b2e',
                      color: '#d3e4fe',
                      border: '1px solid rgba(140,144,159,0.2)',
                      borderRadius: '10px',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '14px',
                      outline: 'none',
                      boxSizing: 'border-box',
                      transition: 'all 0.2s ease'
                    }}
                    onFocus={e => {
                      e.target.style.borderColor = '#adc6ff';
                      e.target.style.boxShadow = '0 0 0 1px rgba(173,198,255,0.2)';
                    }}
                    onBlur={e => {
                      e.target.style.borderColor = 'rgba(140,144,159,0.2)';
                      e.target.style.boxShadow = 'none';
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: 'absolute',
                      right: '16px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      color: '#879298',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '4px',
                      borderRadius: '4px',
                      transition: 'color 0.2s ease'
                    }}
                    onMouseEnter={e => e.currentTarget.style.color = '#adc6ff'}
                    onMouseLeave={e => e.currentTarget.style.color = '#879298'}
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              {/* Error Message */}
              {loginError && (
                <div style={{ 
                  padding: '14px 18px', 
                  background: 'rgba(244,63,94,0.1)', 
                  border: '1px solid rgba(244,63,94,0.2)', 
                  borderRadius: '8px', 
                  color: '#f43f5e', 
                  fontSize: '13px', 
                  marginBottom: '24px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px'
                }}>
                  <AlertTriangle size={18} />
                  {loginError}
                </div>
              )}

              {/* Sign In Button */}
              <button 
                type="submit" 
                disabled={loggingIn}
                style={{
                  width: '100%',
                  padding: '16px',
                  background: '#adc6ff',
                  color: '#0b1326',
                  border: 'none',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: '700',
                  textTransform: 'uppercase',
                  letterSpacing: '0.15em',
                  cursor: loggingIn ? 'default' : 'pointer',
                  opacity: loggingIn ? 0.7 : 1,
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px'
                }}
                onMouseEnter={e => !loggingIn && (e.target.style.background = '#8aa8e8')}
                onMouseLeave={e => !loggingIn && (e.target.style.background = '#adc6ff')}
              >
                {loggingIn ? 'Authenticating...' : 'Sign In'}
                {!loggingIn && <ArrowRight size={18} />}
              </button>
            </form>
          </div>

          {/* Bottom: Architecture Info */}
          <div style={{ marginTop: 'auto' }}>
            <div style={{ 
              display: 'flex',
              alignItems: 'center',
              gap: '16px',
              padding: '16px 0',
              borderTop: '1px solid rgba(140,144,159,0.2)'
            }}>
              <ShieldCheck size={18} style={{ color: '#adc6ff' }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
                <div style={{ fontSize: '11px', fontWeight: '700', color: '#d3e4fe', fontFamily: "'JetBrains Mono', monospace" }}>ZERO PHI STORAGE ARCHITECTURE</div>
                <div style={{ width: '1px', height: '20px', background: 'rgba(140,144,159,0.2)' }} />
                <div style={{ fontSize: '10px', color: '#879298', fontFamily: "'JetBrains Mono', monospace" }}>ENCRYPTION: AES-256-GCM</div>
              </div>
            </div>
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
        width: '260px',
        background: '#060e20',
        borderRight: '1px solid rgba(140,144,159,0.2)',
        display: 'flex',
        flexDirection: 'column',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 10
      }}>
        {/* Top Logo */}
        <div style={{ 
          padding: '24px 20px', 
          borderBottom: '1px solid #3e484d',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div style={{background:'transparent', border:'none', boxShadow:'none', padding:0, display:'flex', alignItems:'center'}}>
            <img src='/sentinelehr-logo.png' alt='SentinelEHR' style={{width:'38px', height:'38px', objectFit:'contain'}} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ fontWeight: '700', fontSize: '18px', color: '#adc6ff', lineHeight: 1 }}>SentinelEHR</span>
            <span style={{ fontSize: '10px', fontWeight: '600', color: '#879298', textTransform: 'uppercase', letterSpacing: '0.05em' }}>COMPLIANCE INTELLIGENCE</span>
          </div>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '16px 0', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1 }}>
            {NAV_ITEMS.map((item, idx) => {
              if (item.id === 'divider') {
                return null; // Remove the divider
              }
              
              // Hide Investigate tab for it_director role
              if (item.id === 'investigate' && userRole === 'it_director') {
                return null;
              }
              
              // Skip settings here, we'll render it separately
              if (item.id === 'settings') {
                return null;
              }
              
              const isActive = activeView === item.id;
              
              // Map nav items to Lucide icons
              const iconMap = {
                'overview': <LayoutDashboard size={18} />,
                'alerts': <BellRing size={18} />,
                'cases': <ClipboardList size={18} />,
                'investigate': <ScanSearch size={18} />,
                'settings': <Settings size={18} />
              };
              
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveView(item.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    padding: '12px 20px',
                    background: isActive ? '#222a3d' : 'transparent',
                    border: 'none',
                    borderLeft: isActive ? '2px solid #adc6ff' : '2px solid transparent',
                    color: isActive ? '#adc6ff' : '#bdc8ce',
                    cursor: 'pointer',
                    gap: '12px',
                    transition: 'all 0.2s',
                    textAlign: 'left'
                  }}
                  onMouseEnter={e => !isActive && (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
                  onMouseLeave={e => !isActive && (e.currentTarget.style.background = 'transparent')}
                >
                  {iconMap[item.id]}
                  <span style={{ fontSize: '14px', fontWeight: isActive ? '600' : '500' }}>{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Settings and Sign Out at bottom */}
          <div style={{ marginTop: 'auto' }}>
            <div style={{ height: '1px', background: 'rgba(140,144,159,0.2)', margin: '16px 0' }} />
            
            {/* Settings */}
            <button
              onClick={() => setActiveView('settings')}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                padding: '12px 20px',
                background: activeView === 'settings' ? '#222a3d' : 'transparent',
                border: 'none',
                borderLeft: activeView === 'settings' ? '2px solid #adc6ff' : '2px solid transparent',
                color: activeView === 'settings' ? '#adc6ff' : '#bdc8ce',
                cursor: 'pointer',
                gap: '12px',
                transition: 'all 0.2s',
                textAlign: 'left'
              }}
              onMouseEnter={e => activeView !== 'settings' && (e.currentTarget.style.background = 'rgba(255,255,255,0.05)')}
              onMouseLeave={e => activeView !== 'settings' && (e.currentTarget.style.background = 'transparent')}
            >
              <Settings size={18} />
              <span style={{ fontSize: '14px', fontWeight: activeView === 'settings' ? '600' : '500' }}>Settings</span>
            </button>
          </div>
        </nav>

        {/* Bottom Actions */}
        <div style={{ padding: '8px 0', borderTop: '1px solid rgba(140,144,159,0.2)' }}>
          <button 
            onClick={() => setShowLogoutConfirm(true)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              padding: '12px 20px',
              background: 'transparent',
              border: 'none',
              color: '#bdc8ce',
              cursor: 'pointer',
              gap: '12px',
              transition: 'all 0.2s'
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <LogOut size={18} />
            <span style={{ fontSize: '14px', fontWeight: '500' }}>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main style={{ marginLeft: '260px', display: 'flex', flexDirection: 'column', minHeight: '100vh', flex: 1, minWidth: 0 }}>
        {/* Top Bar */}
        <header style={{
          height: '64px',
          background: '#000f21',
          borderBottom: '1px solid #3e484d',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 40
        }}>
          {/* Left: Search */}
          <div 
            ref={searchContainerRef}
            style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '12px',
            background: '#102034',
            borderRadius: '8px',
            padding: '8px 16px',
            width: '320px',
            border: '1px solid rgba(140,144,159,0.2)',
            position: 'relative'
          }}>
            <Search size={20} style={{ color: '#879298' }} />
            <input 
              id="global-search"
              name="global-search"
              type="text" 
              placeholder="Search alerts, cases, employees..."
              value={searchQuery}
              onChange={(e) => handleGlobalSearch(e.target.value)}
              onFocus={() => searchQuery.trim().length >= 2 && setSearchDropdownOpen(true)}
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#d3e4fe',
                fontSize: '13px',
                width: '100%'
              }}
            />
            
            {/* Search Dropdown */}
            {searchDropdownOpen && (searchResults.alerts.length > 0 || searchResults.cases.length > 0 || searchResults.employees.length > 0) && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                marginTop: '8px',
                background: '#131b2e',
                border: '1px solid rgba(140,144,159,0.2)',
                borderRadius: '8px',
                maxHeight: '400px',
                overflowY: 'auto',
                zIndex: 200
              }}>
                {/* Alerts Section */}
                {searchResults.alerts.length > 0 && (
                  <div>
                    <div style={{
                      padding: '8px 16px',
                      fontSize: '10px',
                      fontWeight: '600',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: '#879298',
                      borderBottom: '1px solid rgba(140,144,159,0.2)'
                    }}>
                      Alerts
                    </div>
                    {searchResults.alerts.map(alert => (
                      <div
                        key={alert.alert_id}
                        onClick={() => handleSearchResultClick('alerts', alert)}
                        style={{
                          padding: '12px 16px',
                          cursor: 'pointer',
                          borderBottom: '1px solid #1b2b3f',
                          transition: 'background 0.15s'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = '#1b2b3f'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '12px', fontWeight: '600', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>
                            Alert #{alert.alert_id}
                          </span>
                          <span style={{ fontSize: '10px', color: '#879298', fontFamily: "'JetBrains Mono', monospace" }}>
                            EMP-{alert.emp_id}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {alert.rules_triggered?.split(',').map(r => (
                            <div key={r} className="tooltip">
                              <span 
                                style={{ 
                                  fontSize: '9px', 
                                  background: '#0b1c30', 
                                  border: '1px solid rgba(140,144,159,0.1)', 
                                  padding: '2px 6px', 
                                  borderRadius: '4px', 
                                  color: '#879298'
                                }}
                              >
                                {r}
                              </span>
                              <span className="tooltiptext">{RULE_DESCRIPTIONS[r.trim()] || r}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Cases Section */}
                {searchResults.cases.length > 0 && (
                  <div>
                    <div style={{
                      padding: '8px 16px',
                      fontSize: '10px',
                      fontWeight: '600',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: '#879298',
                      borderBottom: '1px solid rgba(140,144,159,0.2)'
                    }}>
                      Cases
                    </div>
                    {searchResults.cases.map(c => (
                      <div
                        key={c.case_id}
                        onClick={() => handleSearchResultClick('cases', c)}
                        style={{
                          padding: '12px 16px',
                          cursor: 'pointer',
                          borderBottom: '1px solid #1b2b3f',
                          transition: 'background 0.15s'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = '#1b2b3f'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '12px', fontWeight: '600', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>
                            {c.case_id}
                          </span>
                          <span style={{ fontSize: '10px', color: '#879298', fontFamily: "'JetBrains Mono', monospace" }}>
                            EMP-{c.emp_id}
                          </span>
                        </div>
                        <div style={{ fontSize: '11px', color: '#bdc8ce' }}>
                          {c.priority} · {c.status}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Employees Section */}
                {searchResults.employees.length > 0 && (
                  <div>
                    <div style={{
                      padding: '8px 16px',
                      fontSize: '10px',
                      fontWeight: '600',
                      textTransform: 'uppercase',
                      letterSpacing: '0.05em',
                      color: '#879298',
                      borderBottom: '1px solid rgba(140,144,159,0.2)'
                    }}>
                      Employees
                    </div>
                    {searchResults.employees.map(empId => (
                      <div
                        key={empId}
                        onClick={() => handleSearchResultClick('employees', empId)}
                        style={{
                          padding: '12px 16px',
                          cursor: 'pointer',
                          borderBottom: '1px solid #1b2b3f',
                          transition: 'background 0.15s'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = '#1b2b3f'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                      >
                        <div style={{ fontSize: '12px', fontWeight: '600', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace" }}>
                          EMP-{empId}
                        </div>
                        <div style={{ fontSize: '11px', color: '#879298' }}>
                          View employee profile
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Right: Actions and User */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {/* Vertical Divider */}
            <div style={{ width: '1px', height: '32px', background: 'rgba(140,144,159,0.2)' }} />
            
            {/* User Info */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '13px', fontWeight: '600', color: '#d3e4fe' }}>
                  {userEmail || 'User'}
                </div>
                <div style={{ fontSize: '10px', fontWeight: '600', color: '#879298', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  {userRole === 'compliance_officer' ? 'COMPLIANCE OFFICER' : userRole === 'it_director' ? 'IT DIRECTOR' : userRole === 'admin' ? 'ADMIN' : 'USER'}
                </div>
              </div>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: '#2563eb',
                border: '2px solid rgba(74,158,255,0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontWeight: '700',
                fontSize: '14px'
              }}>
                {(userEmail || 'U').charAt(0).toUpperCase()}
              </div>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="w-full px-6 py-6" style={{ flex: 1, overflowY: 'auto', paddingBottom: '72px' }}>
          {activeView === 'overview' && ( 
            <div style={{ width: '100%' }}> 
          
              {/* Stat cards */} 
              <div className="w-full" style={{ 
                display: 'flex',
                gap: '24px', 
                marginBottom: '40px' 
              }}> 
                {[ 
                  { 
                    label: 'CRITICAL THREATS', 
                    value: summary?.critical ?? alerts.filter(a => a.adjusted_severity === 'Critical').length, 
                    sub: 'Require immediate action', 
                    color: '#f43f5e',
                    icon: <AlertTriangle size={20} />
                  }, 
                  { 
                    label: 'HIGH RISK', 
                    value: summary?.high ?? alerts.filter(a => a.adjusted_severity === 'High').length, 
                    sub: 'ML-elevated alerts', 
                    color: '#f97316',
                    icon: <AlertOctagon size={20} />
                  }, 
                  { 
                    label: 'MEDIUM RISK', 
                    value: summary?.medium ?? alerts.filter(a => a.adjusted_severity === 'Medium').length, 
                    sub: 'Under observation', 
                    color: '#3b82f6',
                    icon: <Info size={20} />
                  }, 
                  { 
                    label: 'ML PEAK SCORE', 
                    value: summary?.top_anomaly_score 
                      ? summary.top_anomaly_score.toFixed(2) 
                      : (alerts.length > 0 ? Math.max(...alerts.map(a => a.anomaly_score)).toFixed(2) : '—'), 
                    sub: '90-day highest anomaly', 
                    color: '#adc6ff',
                    icon: <Activity size={20} />
                  } 
                ].map((card, idx) => (
                  <div 
                    key={card.label} 
                    style={{ 
                      flex: 1,
                      minWidth: 0,
                      background: '#131b2e',
                      border: '1px solid rgba(140,144,159,0.2)',
                      borderBottom: '2px solid transparent',
                      borderRadius: '12px', 
                      padding: '32px', 
                      position: 'relative', 
                      cursor: 'pointer',
                      transition: 'border-bottom-color 0.2s ease'
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderBottomColor = card.color;
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderBottomColor = 'transparent';
                    }}
                  > 
                    <div style={{ 
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      marginBottom: '16px'
                    }}>
                      <div style={{ 
                        fontSize: '12px', 
                        fontWeight: '600', 
                        letterSpacing: '0.05em', 
                        textTransform: 'uppercase', 
                        color: '#64748b'
                      }}>{card.label}</div>
                      <div style={{ color: card.color }}>
                        {card.icon}
                      </div>
                    </div>
                    <div style={{ 
                      fontSize: '56px', 
                      fontWeight: '700', 
                      color: card.color, 
                      lineHeight: 1, 
                      fontFamily: "'JetBrains Mono', monospace", 
                      letterSpacing: '-0.02em', 
                      marginBottom: '12px' 
                    }}>{card.value}</div> 
                    <div style={{ 
                      fontSize: '12px', 
                      color: '#475569',
                      fontFamily: "'Inter', sans-serif",
                      lineHeight: 1.6
                    }}>{card.sub}</div>
                  </div>
                ))} 
              </div> 
          
              {/* Chart card */}
              <div className="w-full" style={{ 
                background: '#131b2e',
                border: '1px solid rgba(140,144,159,0.2)',
                borderRadius: '12px', 
                overflow: 'hidden',
                marginBottom: '40px'
              }}> 
                <div style={{ 
                  padding: '24px 28px 0',
                  background: '#102034',
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'flex-start' 
                }}> 
                  <div> 
                    <div style={{ 
                      fontSize: '10px', 
                      fontWeight: '600', 
                      letterSpacing: '0.1em', 
                      textTransform: 'uppercase', 
                      color: '#879298', 
                      marginBottom: '6px' 
                    }}>ALERT TREND ANALYSIS</div> 
                    <div style={{ 
                      fontSize: '20px', 
                      fontWeight: '700', 
                      color: '#d3e4fe', 
                      letterSpacing: '-0.02em' 
                    }}>30-Day Alert Trend</div> 
                  </div> 
                  <div style={{ 
                    display: 'flex', 
                    gap: '24px', 
                    alignItems: 'center' 
                  }}> 
                    {[ 
                      { c: '#f43f5e', l: 'Critical' }, 
                      { c: '#f97316', l: 'High' }, 
                      { c: '#3b82f6', l: 'Medium' }, 
                    ].map(item => ( 
                      <span key={item.l} style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '8px', 
                        fontSize: '12px', 
                        fontWeight: '600',
                        color: '#bdc8ce' 
                      }}> 
                        <span style={{ 
                          display: 'inline-block', 
                          width: '24px', 
                          height: '3px', 
                          background: item.c, 
                          borderRadius: '2px' 
                        }}/> 
                        {item.l} 
                      </span> 
                    ))} 
                  </div> 
                </div> 
          
                <div style={{ 
                  padding: '20px 28px', 
                  height: '320px', 
                  position: 'relative',
                  background: '#102034'
                }}> 
                  {dataLoading ? (
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      height: '100%', 
                      color: '#879298', 
                      fontSize: '13px' 
                    }}>Loading chart data...</div> 
                  ) : digest.length === 0 ? ( 
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      height: '100%', 
                      color: '#879298', 
                      fontSize: '13px' 
                    }}>No activity detected in the last 30 days.</div> 
                  ) : ( 
                    <canvas ref={chartRef} style={{ width: '100%', height: '100%', cursor: 'pointer' }}/> 
                  )} 
                </div> 
              </div>

            </div> 
          )} 
          
          {activeView === 'alerts' && ( 
            <div> 
              {/* Date filter indicator — shown when drilled in from chart */}
              {alertDateFilter && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 16px',
                  marginBottom: '16px',
                  background: 'rgba(173,198,255,0.08)',
                  border: '1px solid rgba(173,198,255,0.25)',
                  borderRadius: '8px'
                }}>
                  <Calendar size={15} style={{ color: '#adc6ff', flexShrink: 0 }} />
                  <span style={{ fontSize: '13px', fontWeight: '600', color: '#adc6ff' }}>
                    Filtered by: {new Date(alertDateFilter + 'T12:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                  </span>
                  <button
                    onClick={() => setAlertDateFilter(null)}
                    title="Clear date filter"
                    style={{
                      marginLeft: 'auto',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '4px 10px',
                      background: 'transparent',
                      border: '1px solid rgba(173,198,255,0.3)',
                      borderRadius: '6px',
                      color: '#adc6ff',
                      fontSize: '12px',
                      fontWeight: '600',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(173,198,255,0.12)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <X size={13} /> Clear
                  </button>
                </div>
              )}

              {/* Filter Bar */}
              <div style={{
                background: '#0b1c30',
                border: '1px solid rgba(140,144,159,0.2)',
                borderRadius: '12px',
                padding: '20px 24px',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'flex-end',
                gap: '20px'
              }}>
                <div style={{ flex: 1, display: 'flex', gap: '20px' }}>
                  <div>
                    <div style={{
                      fontSize: '10px',
                      fontWeight: '600',
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color: '#879298',
                      marginBottom: '8px'
                    }}>SEVERITY</div>
                    <select 
                      value={alertSeverity} 
                      onChange={e => {setAlertSeverity(e.target.value); setAlertsOffset(0)}}
                      style={{
                        background: '#000f21',
                        border: '1px solid rgba(140,144,159,0.2)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        fontSize: '13px',
                        color: '#d3e4fe',
                        fontFamily: "'JetBrains Mono', monospace",
                        outline: 'none',
                        minWidth: '160px',
                        cursor: 'pointer'
                      }}
                    >
                      <option value="">All</option>
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                    </select>
                  </div>
                  <div>
                    <div style={{
                      fontSize: '10px',
                      fontWeight: '600',
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color: '#879298',
                      marginBottom: '8px'
                    }}>STATUS</div>
                    <select 
                      value={alertStatus} 
                      onChange={e => {setAlertStatus(e.target.value); setAlertsOffset(0)}}
                      style={{
                        background: '#000f21',
                        border: '1px solid rgba(140,144,159,0.2)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        fontSize: '13px',
                        color: '#d3e4fe',
                        fontFamily: "'JetBrains Mono', monospace",
                        outline: 'none',
                        minWidth: '160px',
                        cursor: 'pointer'
                      }}
                    >
                      <option value="">All</option>
                      <option value="open">Open</option>
                      <option value="investigating">Investigating</option>
                      <option value="resolved">Resolved</option>
                    </select>
                  </div>
                </div>
                <button 
                  onClick={handleExportAlerts}
                  disabled={exportingAlerts}
                  style={{ 
                    padding: '10px 20px',
                    background: '#2563eb',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: '700',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    cursor: exportingAlerts ? 'default' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    opacity: exportingAlerts ? 0.7 : 1,
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={e => !exportingAlerts && (e.currentTarget.style.background = '#1d4ed8')}
                  onMouseLeave={e => !exportingAlerts && (e.currentTarget.style.background = '#2563eb')}
                > 
                  <Download size={18} />
                  {exportingAlerts ? 'Exporting...' : 'Export CSV'} 
                </button>
                <div style={{
                  marginLeft: 'auto',
                  fontSize: '12px',
                  color: '#879298',
                  fontFamily: "'JetBrains Mono', monospace",
                  fontWeight: '600'
                }}>{alertsOffset + 1}-{Math.min(alertsOffset + alerts.length, alertsTotal)} of {alertsTotal}</div>
              </div>
        
              {/* Table */}
              <div style={{
                background: '#0b1c30',
                border: '1px solid rgba(140,144,159,0.2)',
                borderRadius: '12px',
                overflow: 'auto',
                marginBottom: '24px'
              }}>
                <table style={{ width: '100%', minWidth: '900px', borderCollapse: 'collapse' }}> 
                  <thead> 
                    <tr style={{ background: 'rgba(27,43,63,0.5)' }}> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>SEVERITY</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>EMPLOYEE</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>RULES</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>SCORE</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>DATE</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>EXPLANATION</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>ACTION</th> 
                    </tr> 
                  </thead> 
                  <tbody> 
                    {alertsLoading ? <tr><td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: '#879298' }}>Loading alerts...</td></tr> : 
                     alerts.filter(a => {
                       if (!alertDateFilter) return true;
                       return a.alert_date && a.alert_date.split('T')[0] === alertDateFilter;
                     }).map(a => ( 
                      <tr 
                        key={a.alert_id} 
                        style={{ borderTop: '1px solid rgba(62,72,77,0.3)', transition: 'background 0.2s', verticalAlign: 'middle' }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(38,54,74,0.3)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      > 
                        <td style={{ padding: '14px 20px' }}>
                          <span style={{
                            padding: '4px 12px',
                            borderRadius: '20px',
                            fontSize: '11px',
                            fontWeight: '700',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            background: a.adjusted_severity === 'Critical' ? '#f43f5e1a' : a.adjusted_severity === 'High' ? '#f973161a' : '#3b82f61a',
                            color: a.adjusted_severity === 'Critical' ? '#f43f5e' : a.adjusted_severity === 'High' ? '#f97316' : '#3b82f6',
                            border: `1px solid ${a.adjusted_severity === 'Critical' ? '#f43f5e33' : a.adjusted_severity === 'High' ? '#f9731633' : '#3b82f633'}`
                          }}>{a.adjusted_severity}</span>
                        </td> 
                        <td style={{ padding: '14px 20px', fontSize: '14px', fontWeight: '600', color: '#d3e4fe', fontFamily: "'JetBrains Mono', monospace" }}>EMP-{a.emp_id}</td> 
                        <td style={{ padding: '14px 20px' }}> 
                          <div className="flex flex-wrap gap-1">
                            {a.rules_triggered.split(',').map(r => ( 
                              <div key={r} className="tooltip">
                                <span 
                                  style={{ 
                                    fontSize: '10px', 
                                    background: '#26364a', 
                                    border: '1px solid rgba(140,144,159,0.2)', 
                                    padding: '3px 8px', 
                                    borderRadius: '6px', 
                                    color: '#bdc8ce',
                                    cursor: 'help',
                                    display: 'inline-block'
                                  }}
                                >
                                  {r}
                                </span>
                                <span className="tooltiptext">{RULE_DESCRIPTIONS[r.trim()] || r}</span>
                              </div> 
                            ))} 
                          </div>
                        </td> 
                        <td style={{ 
                          padding: '14px 20px', 
                          fontSize: '14px', 
                          fontWeight: '700', 
                          fontFamily: "'JetBrains Mono', monospace",
                          color: a.adjusted_severity === 'Critical' ? '#f43f5e' : a.adjusted_severity === 'High' ? '#f97316' : '#3b82f6'
                        }}>{a.anomaly_score.toFixed(2)}</td> 
                        <td style={{ padding: '14px 20px', fontSize: '14px', color: '#bdc8ce' }}>{new Date(a.alert_date).toLocaleDateString()}</td> 
                        <td style={{ padding: '14px 20px', fontSize: '14px', color: '#879298', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.explanation}>{a.explanation}</td> 
                        <td style={{ padding: '14px 20px' }}> 
                          <button 
                            onClick={() => {setSelectedAlert(a.alert_id); fetchAlertDetail(a.alert_id)}} 
                            style={{ 
                              padding: '4px 12px', 
                              background: '#2563eb', 
                              color: '#fff', 
                              border: 'none', 
                              borderRadius: '6px', 
                              fontSize: '11px', 
                              fontWeight: '700', 
                              cursor: 'pointer',
                              textTransform: 'uppercase',
                              letterSpacing: '0.05em',
                              transition: 'all 0.2s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = '#1d4ed8'}
                            onMouseLeave={e => e.currentTarget.style.background = '#2563eb'}
                          >REVIEW</button> 
                        </td> 
                      </tr> 
                    ))} 
                  </tbody> 
                </table> 
                {alertsTotal > LIMIT && ( 
                  <div style={{ padding: '16px 20px', borderTop: '1px solid rgba(62,72,77,0.3)', display: 'flex', gap: '12px', justifyContent: 'center' }}> 
                    <button onClick={() => setAlertsOffset(Math.max(0, alertsOffset - LIMIT))} disabled={alertsOffset === 0} style={{ padding: '8px 16px', background: '#102034', border: '1px solid rgba(140,144,159,0.2)', color: '#d3e4fe', borderRadius: '6px', cursor: 'pointer', opacity: alertsOffset === 0 ? 0.5 : 1, fontWeight: '600', fontSize: '12px' }}>Previous</button> 
                    <button onClick={() => setAlertsOffset(alertsOffset + LIMIT)} disabled={alertsOffset + LIMIT >= alertsTotal} style={{ padding: '8px 16px', background: '#102034', border: '1px solid rgba(140,144,159,0.2)', color: '#d3e4fe', borderRadius: '6px', cursor: 'pointer', opacity: alertsOffset + LIMIT >= alertsTotal ? 0.5 : 1, fontWeight: '600', fontSize: '12px' }}>Next</button> 
                  </div> 
                )} 
              </div>
        
              {selectedAlert && ( 
                <Drawer title="Alert Review" id={`ALT-${selectedAlert}`} onClose={handleCloseAlertDrawer} loading={!alertDetail}> 
                  {alertDetail && ( 
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}> 
                      <div> 
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Rules Triggered</div> 
                        <div className="flex flex-wrap gap-1 mb-4">
                          {alertDetail.rules_triggered?.split(',').map(r => (
                            <div key={r} className="tooltip">
                              <span 
                                style={{ 
                                  fontSize: '11px', 
                                  background: 'var(--bg-elevated)', 
                                  border: '1px solid var(--border)', 
                                  padding: '4px 10px', 
                                  borderRadius: '6px', 
                                  color: 'var(--text-secondary)',
                                  cursor: 'help'
                                }}
                              >
                                {r}
                              </span>
                              <span className="tooltiptext">{RULE_DESCRIPTIONS[r.trim()] || r}</span>
                            </div>
                          ))}
                        </div>
                        <div style={{ fontSize: '10px', fontWeight: '600', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Explanation</div> 
                        <div style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.6', background: 'var(--bg-elevated)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border)' }}>{alertDetail.explanation}</div> 
                        <button 
                          onClick={() => {
                            setInvestigateId(alertDetail.emp_id);
                            setActiveView('investigate');
                            setSelectedAlert(null);
                          }}
                          style={{
                            marginTop: '16px',
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '8px',
                            padding: '10px',
                            background: '#0f172a',
                            border: '1px solid #4a9eff',
                            color: '#adc6ff',
                            borderRadius: '8px',
                            fontSize: '14px',
                            fontWeight: '500',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(74,158,255,0.1)'}
                          onMouseLeave={e => e.currentTarget.style.background = '#0f172a'}
                        >
                          <Search size={16} />
                          Investigate Employee
                        </button>
                        
                        <button 
                          onClick={() => handleCreateCaseFromAlert(alertDetail.alert_id)}
                          disabled={createCaseStatus.loading}
                          style={{
                            marginTop: '8px',
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '8px',
                            padding: '10px',
                            background: '#0f172a',
                            border: '1px solid #22c55e',
                            color: '#22c55e',
                            borderRadius: '8px',
                            fontSize: '14px',
                            fontWeight: '500',
                            cursor: createCaseStatus.loading ? 'default' : 'pointer',
                            opacity: createCaseStatus.loading ? 0.7 : 1,
                            transition: 'all 0.2s'
                          }}
                          onMouseEnter={e => !createCaseStatus.loading && (e.currentTarget.style.background = 'rgba(34,197,94,0.1)')}
                          onMouseLeave={e => !createCaseStatus.loading && (e.currentTarget.style.background = '#0f172a')}
                        >
                          <Plus size={16} />
                          {createCaseStatus.loading ? 'Creating...' : 'Create Case from Alert'}
                        </button>
                        
                        {createCaseStatus.message && (
                          <div style={{ 
                            marginTop: '8px', 
                            fontSize: '12px', 
                            textAlign: 'center',
                            fontWeight: '600',
                            color: createCaseStatus.type === 'success' ? '#22c55e' : '#f43f5e'
                          }}>
                            {createCaseStatus.message}
                          </div>
                        )}
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
              <div style={{
                background: '#0b1c30',
                border: '1px solid rgba(140,144,159,0.2)',
                borderRadius: '12px',
                padding: '20px 24px',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'flex-end',
                gap: '20px'
              }}>
                <div style={{ flex: 1, display: 'flex', gap: '20px' }}>
                  <div>
                    <div style={{
                      fontSize: '10px',
                      fontWeight: '600',
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color: '#879298',
                      marginBottom: '8px'
                    }}>STATUS</div>
                    <select 
                      value={caseStatusFilter} 
                      onChange={e => {setCaseStatusFilter(e.target.value); setCasesOffset(0)}}
                      style={{
                        background: '#000f21',
                        border: '1px solid rgba(140,144,159,0.2)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        fontSize: '13px',
                        color: '#d3e4fe',
                        fontFamily: "'JetBrains Mono', monospace",
                        outline: 'none',
                        minWidth: '200px',
                        cursor: 'pointer'
                      }}
                    >
                      <option value="">All</option> 
                      <option value="Open">Open</option> 
                      <option value="Under Investigation">Under Investigation</option> 
                      <option value="Pending HR">Pending HR</option> 
                      <option value="Resolved">Resolved</option> 
                    </select>
                  </div>
                  <div>
                    <div style={{
                      fontSize: '10px',
                      fontWeight: '600',
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      color: '#879298',
                      marginBottom: '8px'
                    }}>PRIORITY</div>
                    <select 
                      value={casePriorityFilter} 
                      onChange={e => {setCasePriorityFilter(e.target.value); setCasesOffset(0)}}
                      style={{
                        background: '#000f21',
                        border: '1px solid rgba(140,144,159,0.2)',
                        borderRadius: '8px',
                        padding: '10px 14px',
                        fontSize: '13px',
                        color: '#d3e4fe',
                        fontFamily: "'JetBrains Mono', monospace",
                        outline: 'none',
                        minWidth: '160px',
                        cursor: 'pointer'
                      }}
                    >
                      <option value="">All</option> 
                      <option value="Critical">Critical</option> 
                      <option value="High">High</option> 
                      <option value="Medium">Medium</option> 
                    </select>
                  </div>
                </div>
                <div style={{
                  marginLeft: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '24px'
                }}>
                  <div style={{
                    fontSize: '12px',
                    color: '#879298',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontWeight: '600'
                  }}>{cases.length} of {casesTotal}</div>
                </div>
              </div> 
        
              <div style={{
                background: '#0b1c30',
                border: '1px solid rgba(140,144,159,0.2)',
                borderRadius: '12px',
                overflow: 'hidden',
                marginBottom: '24px'
              }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}> 
                  <thead> 
                    <tr style={{ background: 'rgba(27,43,63,0.5)' }}> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298', minWidth: '140px' }}>Case ID</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Employee</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Priority</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Status</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Days Open</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Alerts</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Window</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Assigned</th> 
                      <th style={{ padding: '14px 20px', textAlign: 'left', fontSize: '10px', fontWeight: '700', letterSpacing: '0.1em', textTransform: 'uppercase', color: '#879298' }}>Report</th>
                    </tr> 
                  </thead> 
                  <tbody> 
                    {casesLoading ? <tr><td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: '#879298' }}>Loading cases...</td></tr> : 
                     cases.map(c => ( 
                      <tr 
                        key={c.case_id} 
                        style={{ borderTop: '1px solid rgba(62,72,77,0.3)', transition: 'background 0.2s' }}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(38,54,74,0.3)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      > 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', fontSize: '13px', fontWeight: '700', color: '#adc6ff', fontFamily: "'JetBrains Mono', monospace", cursor: 'pointer', whiteSpace: 'nowrap' }}>{c.case_id}</td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', fontSize: '13px', fontWeight: '600', color: '#d3e4fe', fontFamily: "'JetBrains Mono', monospace", cursor: 'pointer' }}>EMP-{c.emp_id}</td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', cursor: 'pointer' }}>
                          <span style={{
                            padding: '4px 12px',
                            borderRadius: '20px',
                            fontSize: '11px',
                            fontWeight: '700',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            background: c.priority === 'Critical' ? '#f43f5e1a' : c.priority === 'High' ? '#f973161a' : '#3b82f61a',
                            color: c.priority === 'Critical' ? '#f43f5e' : c.priority === 'High' ? '#f97316' : '#3b82f6',
                            border: `1px solid ${c.priority === 'Critical' ? '#f43f5e33' : c.priority === 'High' ? '#f9731633' : '#3b82f633'}`
                          }}>{c.priority}</span>
                        </td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', cursor: 'pointer' }}> 
                          <span style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: '600', color: '#bdc8ce' }}> 
                            <span style={{ 
                              width: '8px', 
                              height: '8px', 
                              borderRadius: '50%', 
                              background: c.status === 'Open' ? '#14b8a6' : 
                                         (c.status === 'Under Investigation' || c.status === 'Pending HR' || c.status === 'In Review') ? '#f97316' : 
                                         c.status === 'Escalated' ? '#f43f5e' : 
                                         c.status === 'Resolved' ? '#64748b' : '#f97316'
                            }} /> 
                            {c.status} 
                          </span> 
                        </td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', fontSize: '13px', color: '#bdc8ce', fontFamily: "'JetBrains Mono', monospace", cursor: 'pointer' }}>{c.days_open || 0}d</td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', fontSize: '13px', color: '#bdc8ce', fontFamily: "'JetBrains Mono', monospace", cursor: 'pointer' }}>{Array.isArray(c.alert_ids) ? c.alert_ids.length : 0}</td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', fontSize: '11px', color: '#879298', fontFamily: "'JetBrains Mono', monospace", cursor: 'pointer' }}> 
                          {new Date(c.window_start).toLocaleDateString()}<br/> 
                          to {new Date(c.window_end).toLocaleDateString()} 
                        </td> 
                        <td onClick={() => {setSelectedCase(c.case_id); fetchCaseDetail(c.case_id)}} style={{ padding: '14px 20px', fontSize: '12px', color: '#879298', cursor: 'pointer' }}>{c.assigned_to_name || '—'}</td> 
                        <td style={{ padding: '14px 20px' }}>
                          <button 
                            onClick={(e) => { e.stopPropagation(); handleGenerateReport(c.case_id); }}
                            style={{ 
                              background: 'transparent', 
                              border: '1px solid rgba(140,144,159,0.2)', 
                              color: '#bdc8ce', 
                              borderRadius: '6px', 
                              padding: '6px 12px', 
                              cursor: 'pointer', 
                              fontSize: '11px',
                              fontWeight: '600',
                              display: 'flex', 
                              alignItems: 'center', 
                              gap: '6px',
                              transition: 'all 0.2s'
                            }}
                            onMouseEnter={e => {
                              e.currentTarget.style.borderColor = '#4a9eff';
                              e.currentTarget.style.color = '#4a9eff';
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.borderColor = '#3e484d';
                              e.currentTarget.style.color = '#bdc8ce';
                            }}
                          >
                            <FileText size={14} />
                            Report
                          </button>
                        </td>
                      </tr> 
                    ))} 
                  </tbody> 
                </table> 
                {casesTotal > LIMIT && ( 
                  <div style={{ padding: '16px 20px', borderTop: '1px solid rgba(62,72,77,0.3)', display: 'flex', gap: '12px', justifyContent: 'center' }}> 
                    <button onClick={() => setCasesOffset(Math.max(0, casesOffset - LIMIT))} disabled={casesOffset === 0} style={{ padding: '8px 16px', background: '#102034', border: '1px solid rgba(140,144,159,0.2)', color: '#d3e4fe', borderRadius: '6px', cursor: 'pointer', opacity: casesOffset === 0 ? 0.5 : 1, fontWeight: '600', fontSize: '12px' }}>Previous</button> 
                    <button onClick={() => setCasesOffset(casesOffset + LIMIT)} disabled={casesOffset + LIMIT >= casesTotal} style={{ padding: '8px 16px', background: '#102034', border: '1px solid rgba(140,144,159,0.2)', color: '#d3e4fe', borderRadius: '6px', cursor: 'pointer', opacity: casesOffset + LIMIT >= casesTotal ? 0.5 : 1, fontWeight: '600', fontSize: '12px' }}>Next</button> 
                  </div> 
                )} 
              </div> 
        
              {selectedCase && ( 
                <Drawer title="Case Investigation" id={selectedCase} onClose={handleCloseCaseDrawer} loading={!caseDetail} subtitle={caseDetail && <SeverityBadge severity={caseDetail.priority} />}> 
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
                                  <span style={{ color: 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: '10px' }}>{new Date(log.timestamp).toLocaleString()}</span> 
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
        
          {activeView === 'investigate' && ( 
            <InvestigateTab 
              investigateId={investigateId} 
              setInvestigateId={setInvestigateId} 
              handleInvestigate={handleInvestigate} 
              investigateResults={investigateResults} 
              investigating={investigating} 
            />
          )} 
        
          {activeView === 'settings' && (
            <SettingsView 
              thresholds={thresholds}
              setThresholds={setThresholds}
              handleSaveThresholds={handleSaveThresholds}
              savingThresholds={savingThresholds}
              thresholdMessage={thresholdMessage}
              userEmail={userEmail}
              userRole={userRole}
              token={token}
              authHeaders={authHeaders}
            />
          )}
        </div>
      </main>

      {/* Footer Strip */}
      <footer style={{
        position: 'fixed',
        bottom: 0,
        left: '260px',
        right: 0,
        height: '44px',
        background: '#060e20',
        borderTop: '1px solid rgba(140,144,159,0.2)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        zIndex: 30
      }}>
        {/* Left: Monitoring Window */}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#879298',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace"
          }}>MONITORING WINDOW: Jan 5 – Mar 31, 2026</span>
        </div>

        {/* Center: Stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <span style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#879298',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace"
          }}>{summary?.total_employees_monitored ?? 80} EMPLOYEES</span>
          <div style={{ width: '1px', height: '16px', background: 'rgba(255,255,255,0.08)' }} />
          <span style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#879298',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace"
          }}>{summary?.total_active ?? alertsTotal ?? 0} ACTIVE ALERTS</span>
        </div>

        {/* Right: LIVE Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '6px',
            height: '6px',
            background: '#10B981',
            borderRadius: '50%'
          }} />
          <span style={{
            fontSize: '11px',
            fontWeight: '600',
            color: '#10B981',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            fontFamily: "'JetBrains Mono', monospace"
          }}>LIVE</span>
        </div>
      </footer>

      <CaseReportModal report={caseReport} onClose={() => setCaseReport(null)} />

      {showLogoutConfirm && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.8)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#1e293b',
            border: '1px solid rgba(140,144,159,0.2)',
            borderRadius: '12px',
            padding: '32px',
            maxWidth: '400px',
            width: '90%',
            textAlign: 'center'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              background: 'rgba(244,63,94,0.1)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px'
            }}>
              <AlertTriangle size={20} style={{ color: '#f43f5e' }} />
            </div>
            <h3 style={{ fontSize: '20px', fontWeight: '700', color: '#d3e4fe', marginBottom: '12px' }}>Sign out of SentinelEHR?</h3>
            <p style={{ fontSize: '14px', color: '#94a3b8', lineHeight: '1.6', marginBottom: '32px' }}>Any unsaved investigation notes will be lost.</p>
            <div style={{ display: 'flex', gap: '16px' }}>
              <button 
                onClick={() => setShowLogoutConfirm(false)}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: 'transparent',
                  border: '1px solid rgba(140,144,159,0.2)',
                  borderRadius: '8px',
                  color: '#94a3b8',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#0f172a'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                Cancel
              </button>
              <button 
                onClick={() => {
                  handleLogout();
                  setShowLogoutConfirm(false);
                }}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#f43f5e',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#b91c1c'}
                 onMouseLeave={e => e.currentTarget.style.background = '#f43f5e'}
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {showUnsavedWarning && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.8)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#1e293b',
            border: '1px solid rgba(140,144,159,0.2)',
            borderRadius: '12px',
            padding: '32px',
            maxWidth: '400px',
            width: '90%',
            textAlign: 'center'
          }}>
            <div style={{
              width: '64px',
              height: '64px',
              background: 'rgba(249,115,22,0.1)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px'
            }}>
              <AlertTriangle size={20} style={{ color: '#f97316' }} />
            </div>
            <h3 style={{ fontSize: '18px', fontWeight: '700', color: '#d3e4fe', marginBottom: '12px' }}>Unsaved Changes</h3>
            <p style={{ fontSize: '14px', color: '#94a3b8', lineHeight: '1.6', marginBottom: '32px' }}>You have unsaved notes. Close anyway?</p>
            <div style={{ display: 'flex', gap: '16px' }}>
              <button 
                onClick={() => setShowUnsavedWarning(false)}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: 'transparent',
                  border: '1px solid rgba(140,144,159,0.2)',
                  borderRadius: '8px',
                  color: '#94a3b8',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#0f172a'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                No
              </button>
              <button 
                onClick={() => {
                  if (unsavedWarningType === 'alert') setSelectedAlert(null);
                  if (unsavedWarningType === 'case') setSelectedCase(null);
                  setShowUnsavedWarning(false);
                  setUnsavedWarningType(null);
                }}
                style={{
                  flex: 1,
                  padding: '12px',
                  background: '#f43f5e',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#b91c1c'}
                onMouseLeave={e => e.currentTarget.style.background = '#f43f5e'}
              >
                Yes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast.show && (
        <div style={{
          position: 'fixed',
          top: '24px',
          right: '24px',
          padding: '16px 24px',
          background: toast.type === 'success' ? '#10b981' : '#f43f5e',
          color: '#fff',
          borderRadius: '8px',
          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontWeight: '600',
          fontSize: '14px',
          animation: 'slideIn 0.3s ease-out'
        }}>
          {toast.type === 'success' ? <Bell size={20} /> : <AlertTriangle size={20} />}
          <span>{toast.message}</span>
          <button 
            onClick={() => setToast(prev => ({ ...prev, show: false }))}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: 'rgba(255,255,255,0.7)', 
              cursor: 'pointer',
              marginLeft: '8px',
              padding: '2px'
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        .tooltip {
          position: relative;
          display: inline-block;
        }
        .tooltip .tooltiptext {
          visibility: hidden;
          width: 160px;
          background-color: #1e293b;
          color: #fff;
          text-align: center;
          border-radius: 6px;
          padding: 6px 10px;
          position: absolute;
          z-index: 100;
          bottom: 130%;
          left: 50%;
          transform: translateX(-50%);
          opacity: 0;
          transition: opacity 0.2s;
          font-size: 11px;
          border: 1px solid rgba(140,144,159,0.3);
          pointer-events: none;
          box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
          white-space: nowrap;
        }
        .tooltip:hover .tooltiptext {
          visibility: visible;
          opacity: 1;
        }
        .tooltip .tooltiptext::after {
          content: "";
          position: absolute;
          top: 100%;
          left: 50%;
          margin-left: -5px;
          border-width: 5px;
          border-style: solid;
          border-color: #1e293b transparent transparent transparent;
        }
        .login-input::placeholder {
          color: #475569;
          opacity: 1;
        }

        input:-webkit-autofill,
        input:-webkit-autofill:hover,
        input:-webkit-autofill:focus {
          -webkit-box-shadow: 0 0 0px 1000px #000f21 inset !important;
          -webkit-text-fill-color: #d3e4fe !important;
          border-color: #334155 !important;
        }
        
        ::-webkit-scrollbar {
          width: 6px;
        }
        
        ::-webkit-scrollbar-track {
          background: #071a2e;
        }
        
        ::-webkit-scrollbar-thumb {
          background: #3e484d;
          border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
          background: #879298;
        }
        
        * {
          scrollbar-width: thin;
          scrollbar-color: #3e484d #071a2e;
        }
      `}</style>
    </div>
  );
}
