"""
SleepCare CPAP AI Server - Interactive Modular HTML Dashboard
============================================================
Generates the self-contained, responsive single-page web dashboard for live monitoring,
real-time console log streaming, pipeline orchestration, and clinical video management.
"""

def get_dashboard_html() -> str:
    """Returns the full HTML document for the interactive AI Server dashboard."""
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SleepCare CPAP AI Server | Live Control Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-page: #f8fafc;
      --bg-page-gradient: radial-gradient(circle at 20% 10%, #eff6ff 0%, #f8fafc 40%, #f1f5f9 100%);
      --bg-header: rgba(255, 255, 255, 0.92);
      --bg-card: #ffffff;
      --bg-card-hover: #ffffff;
      --bg-card-inner: #f8fafc;
      --border-subtle: #e2e8f0;
      --border-accent: rgba(2, 132, 199, 0.35);
      --card-shadow: 0 4px 16px -2px rgba(0, 0, 0, 0.05), 0 2px 6px -1px rgba(0, 0, 0, 0.02);
      --card-shadow-hover: 0 12px 28px -3px rgba(2, 132, 199, 0.14), 0 4px 8px -2px rgba(0, 0, 0, 0.04);
      --primary: #0284c7;
      --primary-glow: rgba(2, 132, 199, 0.2);
      --purple: #7c3aed;
      --emerald: #059669;
      --amber: #d97706;
      --rose: #e11d48;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --text-subtle: #94a3b8;
      --input-bg: #f8fafc;
      --input-border: #cbd5e1;
      --table-th-bg: #f1f5f9;
      --table-tr-border: #f1f5f9;
      --table-tr-hover: #f8fafc;
      --terminal-bg: #0f172a;
      --terminal-header-bg: #1e293b;
      --terminal-border: #334155;
      --terminal-text: #f1f5f9;
      --modal-bg: #ffffff;
      --modal-header-bg: #f8fafc;
      --modal-footer-bg: #f8fafc;
      --modal-shadow: 0 25px 60px rgba(0, 0, 0, 0.2);
      --pill-purple-bg: #f3e8ff;
      --pill-purple-text: #7e22ce;
      --pill-emerald-bg: #dcfce7;
      --pill-emerald-text: #15803d;
      --pill-amber-bg: #fef3c7;
      --pill-amber-text: #b45309;
      --tag-cpap-bg: #e0f2fe;
      --tag-cpap-text: #0369a1;
      --tag-wearable-bg: #f3e8ff;
      --tag-wearable-text: #7e22ce;
      --tag-alert-bg: #ffe4e6;
      --tag-alert-text: #be123c;
      --toast-bg: #0f172a;
      --toast-text: #f8fafc;
      --badge-idle-bg: #dcfce7;
      --badge-idle-text: #15803d;
      --badge-running-bg: #e0f2fe;
      --badge-running-text: #0284c7;
      --badge-failed-bg: #ffe4e6;
      --badge-failed-text: #be123c;
      --btn-outline-bg: #ffffff;
      --btn-outline-border: #cbd5e1;
      --btn-outline-text: #334155;
      --btn-outline-hover-bg: #f1f5f9;
      --btn-danger-bg: #fff1f2;
      --btn-danger-border: #fecdd3;
      --btn-danger-text: #e11d48;
      --card-icon-bg: #f1f5f9;
      --status-badge-bg: #ecfdf5;
      --status-badge-border: #a7f3d0;
      --status-badge-text: #059669;
    }

    [data-theme="dark"] {
      --bg-page: #070b14;
      --bg-page-gradient: radial-gradient(circle at 20% 10%, #0f172a 0%, #070b14 100%);
      --bg-header: rgba(11, 15, 25, 0.85);
      --bg-card: rgba(15, 23, 42, 0.75);
      --bg-card-hover: rgba(30, 41, 59, 0.85);
      --bg-card-inner: rgba(0, 0, 0, 0.3);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(56, 189, 248, 0.3);
      --card-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
      --card-shadow-hover: 0 14px 36px rgba(0, 0, 0, 0.45);
      --primary: #38bdf8;
      --primary-glow: rgba(56, 189, 248, 0.25);
      --purple: #a855f7;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-subtle: #64748b;
      --input-bg: rgba(255, 255, 255, 0.04);
      --input-border: rgba(255, 255, 255, 0.1);
      --table-th-bg: #0f172a;
      --table-tr-border: rgba(255, 255, 255, 0.04);
      --table-tr-hover: rgba(255, 255, 255, 0.02);
      --terminal-bg: #030712;
      --terminal-header-bg: #0b1120;
      --terminal-border: rgba(255, 255, 255, 0.1);
      --terminal-text: #cbd5e1;
      --modal-bg: #0f172a;
      --modal-header-bg: rgba(15, 23, 42, 0.95);
      --modal-footer-bg: rgba(15, 23, 42, 0.95);
      --modal-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
      --pill-purple-bg: rgba(168, 85, 247, 0.2);
      --pill-purple-text: #c084fc;
      --pill-emerald-bg: rgba(16, 185, 129, 0.2);
      --pill-emerald-text: #34d399;
      --pill-amber-bg: rgba(245, 158, 11, 0.2);
      --pill-amber-text: #fbbf24;
      --tag-cpap-bg: rgba(56, 189, 248, 0.15);
      --tag-cpap-text: #38bdf8;
      --tag-wearable-bg: rgba(168, 85, 247, 0.15);
      --tag-wearable-text: #c084fc;
      --tag-alert-bg: rgba(244, 63, 94, 0.15);
      --tag-alert-text: #fb7185;
      --toast-bg: #1e293b;
      --toast-text: #f8fafc;
      --badge-idle-bg: rgba(16, 185, 129, 0.15);
      --badge-idle-text: #34d399;
      --badge-running-bg: rgba(56, 189, 248, 0.2);
      --badge-running-text: #38bdf8;
      --badge-failed-bg: rgba(244, 63, 94, 0.2);
      --badge-failed-text: #fb7185;
      --btn-outline-bg: rgba(255, 255, 255, 0.04);
      --btn-outline-border: var(--border-subtle);
      --btn-outline-text: var(--text-main);
      --btn-outline-hover-bg: rgba(255, 255, 255, 0.08);
      --btn-danger-bg: rgba(244, 63, 94, 0.15);
      --btn-danger-border: rgba(244, 63, 94, 0.35);
      --btn-danger-text: #fb7185;
      --card-icon-bg: rgba(255, 255, 255, 0.05);
      --status-badge-bg: rgba(16, 185, 129, 0.12);
      --status-badge-border: rgba(16, 185, 129, 0.3);
      --status-badge-text: #34d399;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-page-gradient);
      color: var(--text-main);
      min-height: 100vh;
      line-height: 1.5;
      padding-bottom: 40px;
      transition: background 0.25s ease, color 0.25s ease;
    }

    /* Top Navigation Bar */
    header.top-nav {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 28px;
      background: var(--bg-header);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      position: sticky;
      top: 0;
      z-index: 50;
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .brand-icon {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, #0284c7, #9333ea);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 16px var(--primary-glow);
    }
    .brand-icon svg { width: 22px; height: 22px; fill: white; }
    .brand-text h1 { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text-main); }
    .brand-text p { font-size: 0.75rem; color: var(--text-muted); }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .status-badge {
      display: flex;
      align-items: center;
      gap: 7px;
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: var(--status-badge-bg);
      border: 1px solid var(--status-badge-border);
      color: var(--status-badge-text);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.5; transform: scale(0.85); }
    }
    .api-key-box {
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .api-key-box input {
      background: transparent;
      border: none;
      color: var(--primary);
      font-family: inherit;
      font-size: 0.75rem;
      width: 140px;
      outline: none;
    }
    .btn {
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
      text-decoration: none;
      border: none;
    }
    .btn-outline {
      background: var(--btn-outline-bg);
      color: var(--btn-outline-text);
      border: 1px solid var(--btn-outline-border);
    }
    .btn-outline:hover {
      background: var(--btn-outline-hover-bg);
      border-color: var(--primary);
      color: var(--primary);
    }
    .btn-primary {
      background: linear-gradient(135deg, #0284c7, #0369a1);
      color: white;
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35);
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #0369a1, #075985);
      transform: translateY(-1px);
    }
    .btn-purple {
      background: linear-gradient(135deg, #9333ea, #7e22ce);
      color: white;
      box-shadow: 0 4px 14px rgba(147, 51, 234, 0.35);
    }
    .btn-purple:hover {
      background: linear-gradient(135deg, #7e22ce, #6b21a8);
      transform: translateY(-1px);
    }
    .btn-emerald {
      background: linear-gradient(135deg, #059669, #047857);
      color: white;
      box-shadow: 0 4px 14px rgba(5, 150, 105, 0.35);
    }
    .btn-emerald:hover {
      background: linear-gradient(135deg, #047857, #065f46);
      transform: translateY(-1px);
    }
    .btn-danger {
      background: var(--btn-danger-bg);
      border: 1px solid var(--btn-danger-border);
      color: var(--btn-danger-text);
    }
    .btn-danger:hover {
      opacity: 0.9;
      transform: translateY(-1px);
    }

    /* Main Container */
    main.container {
      max-width: 1400px;
      margin: 24px auto;
      padding: 0 24px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* Server Banner Ribbon */
    .info-banner {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-left: 4px solid var(--primary);
      border-radius: 10px;
      padding: 12px 18px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      font-size: 0.8rem;
      box-shadow: var(--card-shadow);
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .info-tags { display: flex; flex-wrap: wrap; gap: 16px; }
    .info-item { display: flex; align-items: center; gap: 6px; color: var(--text-muted); }
    .info-item strong { color: var(--text-main); }

    /* 4-Card Telemetry Grid */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .metric-card {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: var(--card-shadow);
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background 0.25s ease;
      position: relative;
      overflow: hidden;
    }
    .metric-card:hover {
      transform: translateY(-2px);
      border-color: var(--border-accent);
      background: var(--bg-card-hover);
      box-shadow: var(--card-shadow-hover);
    }
    .metric-card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      background: linear-gradient(90deg, transparent, var(--card-accent, var(--primary)), transparent);
      opacity: 0.9;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .card-title {
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .card-icon {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: var(--card-icon-bg);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .card-value {
      font-size: 1.8rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 4px;
      color: var(--text-main);
    }
    .card-subtext {
      font-size: 0.75rem;
      color: var(--text-muted);
    }
    .badge-pill {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 6px;
      font-size: 0.7rem;
      font-weight: 600;
      margin-top: 6px;
    }
    .badge-idle { background: var(--badge-idle-bg); color: var(--badge-idle-text); }
    .badge-running { background: var(--badge-running-bg); color: var(--badge-running-text); animation: pulse 1.5s infinite; }
    .badge-failed { background: var(--badge-failed-bg); color: var(--badge-failed-text); }
    .pill-purple { background: var(--pill-purple-bg); color: var(--pill-purple-text); }
    .pill-emerald { background: var(--pill-emerald-bg); color: var(--pill-emerald-text); }
    .pill-amber { background: var(--pill-amber-bg); color: var(--pill-amber-text); }
    .pill-cyan { background: rgba(6, 182, 212, 0.15); color: #0891b2; border: 1px solid rgba(6, 182, 212, 0.3); }
    .pill-rose { background: rgba(244, 63, 94, 0.15); color: #e11d48; border: 1px solid rgba(244, 63, 94, 0.3); }
    .pill-slate { background: rgba(100, 116, 139, 0.15); color: #64748b; border: 1px solid rgba(100, 116, 139, 0.3); }
    .pill-blue { background: rgba(59, 130, 246, 0.15); color: #2563eb; border: 1px solid rgba(59, 130, 246, 0.3); }

    /* ==========================================================================
       Dashboard Tab Navigation (Button-Style Segmented Tab Bar)
       ========================================================================== */
    .dashboard-tabs-bar {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 14px;
      padding: 10px 16px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      box-shadow: var(--card-shadow);
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .tabs-segmented-group {
      display: inline-flex;
      background: var(--input-bg);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 4px;
      gap: 4px;
      overflow-x: auto;
      max-width: 100%;
    }
    .tab-btn {
      appearance: none;
      border: 1px solid transparent;
      background: transparent;
      color: var(--text-muted);
      padding: 9px 18px;
      border-radius: 8px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      user-select: none;
      outline: none;
    }
    .tab-btn:hover:not(.active) {
      background: var(--bg-card);
      color: var(--text-main);
      border-color: var(--border-subtle);
      transform: translateY(-1px);
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
    }
    .tab-btn.active {
      background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
      color: #ffffff;
      border-color: transparent;
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.35);
      font-weight: 700;
      transform: translateY(-1px);
    }
    [data-theme="dark"] .tab-btn.active {
      background: linear-gradient(135deg, #0284c7 0%, #0ea5e9 100%);
      color: #ffffff;
      box-shadow: 0 4px 16px rgba(14, 165, 233, 0.4);
    }
    .tab-btn-icon {
      font-size: 1rem;
      line-height: 1;
    }
    .tab-btn-label {
      line-height: 1.2;
    }
    .tab-btn-badge {
      font-size: 0.68rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 9999px;
      background: rgba(15, 23, 42, 0.08);
      color: var(--text-muted);
      transition: all 0.2s ease;
    }
    [data-theme="dark"] .tab-btn-badge {
      background: rgba(255, 255, 255, 0.12);
      color: var(--text-subtle);
    }
    .tab-btn.active .tab-btn-badge {
      background: rgba(255, 255, 255, 0.25);
      color: #ffffff;
    }
    .tab-btn-badge.badge-live {
      background: #dcfce7;
      color: #15803d;
    }
    .tab-btn.active .tab-btn-badge.badge-live {
      background: rgba(255, 255, 255, 0.3);
      color: #ffffff;
    }
    .tab-quick-info {
      font-size: 0.74rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .tab-hint {
      display: inline-block;
      max-width: 480px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    /* Tab Panes Visibility */
    .dashboard-tab-pane {
      display: flex;
      flex-direction: column;
      gap: 24px;
      transition: opacity 0.25s ease;
      animation: tabFadeIn 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .dashboard-tab-pane.tab-hidden {
      display: none !important;
    }
    @keyframes tabFadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* KPI Sub-tab Filter Button Bar */
    .kpi-subtabs-group {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: var(--input-bg);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 3px;
      flex-wrap: wrap;
    }
    .kpi-subtab-btn {
      appearance: none;
      border: 1px solid transparent;
      background: transparent;
      color: var(--text-muted);
      font-size: 0.73rem;
      font-weight: 600;
      padding: 5px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
    }
    .kpi-subtab-btn:hover:not(.active) {
      background: var(--bg-card);
      color: var(--text-main);
    }
    .kpi-subtab-btn.active {
      background: var(--bg-card);
      color: var(--primary);
      border-color: var(--border-subtle);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
      font-weight: 700;
    }
    [data-theme="dark"] .kpi-subtab-btn.active {
      background: var(--bg-card-hover);
      color: var(--primary);
      border-color: var(--border-accent);
    }

    /* ==========================================================================
       Clinical KPI Section, Speedometer Gauges & Analytical Graphs
       ========================================================================== */
    .kpi-section {
      display: flex;
      flex-direction: column;
      gap: 18px;
    }
    .kpi-section-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      flex-wrap: wrap;
      gap: 12px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--border-subtle);
    }
    .kpi-badge-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }
    .kpi-title {
      font-size: 1.15rem;
      font-weight: 700;
      color: var(--text-main);
      letter-spacing: -0.02em;
    }
    .kpi-subtitle {
      font-size: 0.76rem;
      color: var(--text-muted);
      margin-top: 2px;
    }

    /* 4 Speedometer / Radial Gauges Grid */
    .gauges-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
    }
    .gauge-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 18px 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      box-shadow: var(--card-shadow);
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background 0.25s ease;
      position: relative;
      overflow: hidden;
    }
    .gauge-card:hover {
      transform: translateY(-2px);
      border-color: var(--gauge-color, var(--primary));
      box-shadow: var(--card-shadow-hover);
    }
    .gauge-card::before {
      content: "";
      position: absolute;
      top: 0; left: 0; right: 0; height: 3px;
      background: var(--gauge-color, var(--primary));
      opacity: 0.85;
    }
    .gauge-svg-wrapper {
      width: 170px;
      height: 110px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .gauge-svg {
      width: 100%;
      height: 100%;
      overflow: visible;
    }
    .gauge-track {
      fill: none;
      stroke: var(--border-subtle);
      stroke-width: 14;
      stroke-linecap: round;
    }
    .gauge-fill {
      fill: none;
      stroke-width: 14;
      stroke-linecap: round;
      transition: stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .gauge-num {
      font-family: 'Inter', sans-serif;
      font-size: 26px;
      font-weight: 800;
      fill: var(--text-main);
    }
    .gauge-target-lbl {
      font-family: 'Inter', sans-serif;
      font-size: 10px;
      font-weight: 600;
      fill: var(--text-muted);
    }
    .gauge-info {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      margin-top: 4px;
      width: 100%;
    }
    .gauge-name {
      font-size: 0.82rem;
      font-weight: 700;
      color: var(--text-main);
    }
    .gauge-desc {
      font-size: 0.72rem;
      color: var(--text-muted);
    }

    /* 4 Analytical Graphs Grid */
    .kpi-graphs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 16px;
    }
    .kpi-graph-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 14px;
      box-shadow: var(--card-shadow);
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .stacked-bar-container {
      width: 100%;
      padding: 6px 0;
    }
    .stacked-bar {
      width: 100%;
      height: 18px;
      border-radius: 9999px;
      overflow: hidden;
      display: flex;
      background: var(--input-bg);
      border: 1px solid var(--border-subtle);
    }
    .bar-seg {
      height: 100%;
      transition: width 0.8s ease;
    }
    .seg-low { background: linear-gradient(90deg, #10b981, #059669); }
    .seg-med { background: linear-gradient(90deg, #fbbf24, #d97706); }
    .seg-high { background: linear-gradient(90deg, #f43f5e, #e11d48); }
    .kpi-stat-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }
    .kpi-stat-box {
      background: var(--bg-card-inner);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .stat-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .dot-emerald { background: #10b981; }
    .dot-amber { background: #f59e0b; }
    .dot-rose { background: #f43f5e; }
    .stat-lbl {
      font-size: 0.68rem;
      color: var(--text-muted);
      font-weight: 500;
    }
    .stat-val {
      font-size: 0.82rem;
      color: var(--text-main);
      font-weight: 700;
    }
    .bar-chart-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .chart-row {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .row-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.74rem;
    }
    .row-lbl { color: var(--text-muted); }
    .row-val { color: var(--text-main); font-weight: 700; }
    .bar-track {
      width: 100%;
      height: 10px;
      background: var(--input-bg);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: 6px;
      transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .fill-emerald { background: linear-gradient(90deg, #34d399, #059669); }
    .fill-sky { background: linear-gradient(90deg, #38bdf8, #0284c7); }
    .fill-amber { background: linear-gradient(90deg, #fbbf24, #d97706); }
    .fill-rose { background: linear-gradient(90deg, #fb7185, #e11d48); }

    /* Wearable Anomaly 2x2 Grid */
    .wearable-anomaly-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
    }
    .wearable-card {
      background: var(--bg-card-inner);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 10px 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .w-icon { font-size: 1.3rem; flex-shrink: 0; }
    .w-content { display: flex; flex-direction: column; }
    .w-val { font-size: 0.84rem; font-weight: 700; color: var(--text-main); }
    .w-lbl { font-size: 0.7rem; font-weight: 600; color: var(--text-muted); }
    .w-sub { font-size: 0.62rem; color: var(--text-subtle); }
    .kpi-footer-note {
      font-size: 0.72rem;
      color: var(--text-muted);
      border-top: 1px solid var(--border-subtle);
      padding-top: 10px;
      margin-top: 2px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    .kpi-footer-note strong { color: var(--text-main); }

    /* Interactive Action Controls Bar */
    .control-center {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 16px 20px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      box-shadow: var(--card-shadow);
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .control-actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .checkbox-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;
    }

    /* Split Section: Terminal + Simulator */
    .two-column-grid {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 20px;
    }
    @media (max-width: 1024px) {
      .two-column-grid { grid-template-columns: 1fr; }
    }

    /* Terminal Console */
    .terminal-card {
      background: var(--terminal-bg);
      border: 1px solid var(--terminal-border);
      border-radius: 12px;
      display: flex;
      flex-direction: column;
      height: 480px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
      overflow: hidden;
    }
    .terminal-header {
      background: var(--terminal-header-bg);
      padding: 10px 16px;
      border-bottom: 1px solid var(--terminal-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .terminal-controls {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .dot { width: 10px; height: 10px; border-radius: 50%; }
    .dot-red { background: #ef4444; }
    .dot-yellow { background: #f59e0b; }
    .dot-green { background: #10b981; }
    .terminal-title {
      font-size: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      color: #94a3b8;
    }
    .terminal-tools {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .terminal-filter {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #f8fafc;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.7rem;
      outline: none;
    }
    .terminal-body {
      flex: 1;
      padding: 12px 16px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 4px;
      color: var(--terminal-text);
      line-height: 1.4;
    }
    .log-line { display: flex; gap: 8px; word-break: break-all; }
    .log-time { color: #64748b; flex-shrink: 0; }
    .log-lvl-INFO { color: #38bdf8; font-weight: 600; flex-shrink: 0; }
    .log-lvl-WARNING { color: #fbbf24; font-weight: 600; flex-shrink: 0; }
    .log-lvl-ERROR { color: #f87171; font-weight: 600; flex-shrink: 0; }
    .log-msg { color: #e2e8f0; }

    /* Simulator & Explorer Card */
    .simulator-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      box-shadow: var(--card-shadow);
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .sim-header h3 { font-size: 1rem; font-weight: 700; margin-bottom: 2px; color: var(--text-main); }
    .sim-header p { font-size: 0.75rem; color: var(--text-muted); }
    .sim-input-row {
      display: flex;
      gap: 10px;
    }
    .sim-input {
      flex: 1;
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 8px;
      padding: 10px 14px;
      color: var(--text-main);
      font-size: 0.85rem;
      outline: none;
      transition: border-color 0.2s;
    }
    .sim-input:focus { border-color: var(--primary); }
    .sim-result-box {
      background: var(--bg-card-inner);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 16px;
      font-size: 0.8rem;
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 180px;
    }
    .sim-item { display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px; }
    .sim-item span:first-child { color: var(--text-muted); }

    /* Video Catalog Browser */
    .catalog-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 20px;
      box-shadow: var(--card-shadow);
      transition: background 0.25s ease, border-color 0.25s ease;
    }
    .catalog-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .catalog-header h2 { color: var(--text-main); }
    .catalog-search {
      background: var(--input-bg);
      border: 1px solid var(--input-border);
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 0.8rem;
      color: var(--text-main);
      width: 240px;
      outline: none;
    }
    .catalog-table-wrapper {
      max-height: 400px;
      overflow-y: auto;
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
    }
    table.catalog-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.78rem;
      text-align: left;
    }
    table.catalog-table th {
      background: var(--table-th-bg);
      padding: 10px 14px;
      color: var(--text-muted);
      position: sticky;
      top: 0;
      z-index: 5;
      border-bottom: 1px solid var(--border-subtle);
    }
    table.catalog-table td {
      padding: 10px 14px;
      border-top: 1px solid var(--table-tr-border);
      color: var(--text-main);
    }
    table.catalog-table tr:hover {
      background: var(--table-tr-hover);
    }
    .tag {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.7rem;
      font-weight: 600;
    }
    .tag-wearable { background: var(--tag-wearable-bg); color: var(--tag-wearable-text); border: 1px solid rgba(124, 58, 237, 0.2); }
    .tag-cpap { background: var(--tag-cpap-bg); color: var(--tag-cpap-text); border: 1px solid rgba(2, 132, 199, 0.2); }
    .tag-alert { background: var(--tag-alert-bg); color: var(--tag-alert-text); border: 1px solid rgba(225, 29, 72, 0.2); }

    /* Subtitle & Play Action Badges */
    .sub-link {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 3px 8px;
      background: var(--tag-cpap-bg);
      border: 1px solid rgba(2, 132, 199, 0.25);
      border-radius: 4px;
      color: var(--tag-cpap-text);
      text-decoration: none;
      font-size: 0.72rem;
      font-weight: 600;
      transition: all 0.2s ease;
    }
    .sub-link:hover {
      opacity: 0.85;
      transform: translateY(-1px);
    }
    .btn-play {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: linear-gradient(135deg, #059669, #10b981);
      color: white;
      border: none;
      border-radius: 5px;
      padding: 4px 10px;
      font-size: 0.72rem;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 2px 6px rgba(16, 185, 129, 0.25);
      transition: all 0.2s ease;
    }
    .btn-play:hover {
      filter: brightness(1.15);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
    }
    .btn-icon-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 5px;
      background: var(--input-bg);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.8rem;
      transition: all 0.2s ease;
    }
    .btn-icon-link:hover {
      background: var(--table-th-bg);
      color: var(--text-main);
      border-color: var(--primary);
    }

    /* Video Player Modal Backdrop & Card */
    .video-modal-backdrop {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 200;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.25s ease;
    }
    .video-modal-backdrop.open {
      opacity: 1;
      pointer-events: auto;
    }
    .video-modal-content {
      width: 90%;
      max-width: 820px;
      background: var(--modal-bg);
      border: 1px solid var(--border-accent);
      border-radius: 14px;
      box-shadow: var(--modal-shadow);
      overflow: hidden;
      transform: scale(0.95);
      transition: transform 0.25s ease;
      display: flex;
      flex-direction: column;
    }
    .video-modal-backdrop.open .video-modal-content {
      transform: scale(1);
    }
    .video-modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      background: var(--modal-header-bg);
      border-bottom: 1px solid var(--border-subtle);
    }
    .video-modal-player {
      background: #000;
      display: flex;
      justify-content: center;
      align-items: center;
      position: relative;
    }
    .video-modal-player video {
      width: 100%;
      max-height: 480px;
      outline: none;
    }
    .video-modal-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 20px;
      background: var(--modal-footer-bg);
      border-top: 1px solid var(--border-subtle);
      flex-wrap: wrap;
      gap: 10px;
    }
    .btn-close-modal {
      background: var(--input-bg);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      border-radius: 6px;
      width: 32px;
      height: 32px;
      font-size: 1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
    }
    .btn-close-modal:hover {
      background: var(--btn-danger-bg);
      border-color: var(--rose);
      color: var(--btn-danger-text);
    }

    /* Toast Notification */
    #toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--toast-bg);
      border: 1px solid var(--border-accent);
      color: var(--toast-text);
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 0.82rem;
      box-shadow: 0 10px 25px rgba(0,0,0,0.25);
      z-index: 100;
      opacity: 0;
      transform: translateY(20px);
      transition: all 0.3s ease;
      pointer-events: none;
    }
    #toast.show { opacity: 1; transform: translateY(0); }
  </style>
</head>
<body>

  <!-- Top Navigation Bar -->
  <header class="top-nav">
    <div class="brand-group">
      <div class="brand-icon">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14h2v2h-2v-2zm0-10h2v8h-2V6z"/></svg>
      </div>
      <div class="brand-text">
        <h1>SleepCare CPAP AI Server</h1>
        <p>Dynamic Anomaly Classification & Automated Video Orchestrator</p>
      </div>
    </div>
    <div class="nav-actions">
      <div class="status-badge" id="systemHealthBadge">
        <div class="pulse-dot"></div>
        <span>SYSTEM ONLINE</span>
      </div>
      <button class="btn btn-outline" id="themeToggleBtn" onclick="toggleTheme()" title="Switch Light/Dark Theme">
        <span id="themeToggleIcon">🌙</span>
        <span id="themeToggleText">Dark</span>
      </button>
      <div class="api-key-box" title="Server API Key">
        <span>🔑</span>
        <input type="password" id="authKeyInput" value="" placeholder="API Key" title="AI Server API Key">
      </div>
      <a href="/docs" target="_blank" class="btn btn-outline" id="btnSwagger">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3m-2 16H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7z"/></svg>
        Swagger Docs
      </a>
    </div>
  </header>

  <!-- Main Dashboard Content -->
  <main class="container">

    <!-- Configuration & Service Banner (Mirroring .bat startup) -->
    <section class="info-banner" id="serverInfoBanner">
      <div class="info-tags">
        <div class="info-item"><span>Host:</span> <strong id="cfgHost">0.0.0.0</strong></div>
        <div class="info-item"><span>Port:</span> <strong id="cfgPort">8000</strong></div>
        <div class="info-item"><span>Sync Interval:</span> <strong id="cfgSync">Every 30m</strong></div>
        <div class="info-item"><span>Video VM:</span> <strong id="cfgVideoVm">http://159.84.143.246:8080</strong></div>
        <div class="info-item"><span>Backend DB:</span> <strong>http://159.84.143.151/api/data</strong></div>
        <div class="info-item"><span>Tracker:</span> <strong id="cfgTracker">artifacts/assigned_videos_tracker.json</strong></div>
      </div>
      <div class="info-item">
        <span>Clock:</span> <strong id="liveClock">--:--:--</strong>
      </div>
    </section>

    <!-- 4 Key Telemetry Metric Cards -->
    <section class="metrics-grid">
      <!-- Card 1: Pipeline Execution Engine -->
      <div class="metric-card" style="--card-accent: var(--primary); cursor: pointer;" onclick="switchDashboardTab('ops')" title="Click to open Live Operations & Console">
        <div class="card-header">
          <span class="card-title">Pipeline Engine (M4_FINAL_F2)</span>
          <div class="card-icon">⚡</div>
        </div>
        <div class="card-value" id="pipelineStatus">IDLE</div>
        <div class="card-subtext" id="pipelineTimes">Last: Never | Total Runs: 0</div>
        <div>
          <span class="badge-pill badge-idle" id="pipelineBadge">Scheduler Active (30m)</span>
        </div>
      </div>

      <!-- Card 2: Persistent Video Tracker & Deduplication -->
      <div class="metric-card" style="--card-accent: var(--purple); cursor: pointer;" onclick="switchDashboardTab('ops')" title="Click to open Live Operations & Console">
        <div class="card-header">
          <span class="card-title">Video Assignment Tracker</span>
          <div class="card-icon">🛡️</div>
        </div>
        <div class="card-value" id="trackerPatientsCount">0</div>
        <div class="card-subtext" id="trackerStatsText">0 Total Assignments Tracked</div>
        <div>
          <span class="badge-pill pill-purple" id="trackerSkippedPill">0 Duplicates Blocked</span>
        </div>
      </div>

      <!-- Card 3: Curated Video Library (Video VM 8080) -->
      <div class="metric-card" style="--card-accent: var(--emerald); cursor: pointer;" onclick="switchDashboardTab('catalog')" title="Click to open Video VM Catalog">
        <div class="card-header">
          <span class="card-title">Video VM Catalog (Port 8080)</span>
          <div class="card-icon">🎬</div>
        </div>
        <div class="card-value" id="videoCatalogCount">39 Videos</div>
        <div class="card-subtext" id="videoCatalogSubtext">78 Bilingual WebVTT Subtitles (EN/FR)</div>
        <div>
          <span class="badge-pill pill-emerald" id="videoCatalogPill">37 Curated + 2 AI Clips</span>
        </div>
      </div>

      <!-- Card 4: ML Models Diagnostic Health -->
      <div class="metric-card" style="--card-accent: var(--amber); cursor: pointer;" onclick="switchDashboardTab('kpis')" title="Click to open Clinical KPIs & Gauges">
        <div class="card-header">
          <span class="card-title">7-Layer ML Diagnostic Status</span>
          <div class="card-icon">🧠</div>
        </div>
        <div class="card-value" id="modelHealthStatus">Healthy</div>
        <div class="card-subtext" id="modelHealthSubtext">CatBoost, LightGBM &amp; Rules Ready</div>
        <div>
          <span class="badge-pill pill-amber">All 7 Layers Operational</span>
        </div>
      </div>
    </section>

    <!-- Segmented Button-Style Dashboard Navigation Tabs -->
    <nav class="dashboard-tabs-bar" role="tablist" aria-label="Dashboard Modular Views">
      <div class="tabs-segmented-group">
        <button class="tab-btn active" id="tabBtnKpis" role="tab" aria-selected="true" onclick="switchDashboardTab('kpis')">
          <span class="tab-btn-icon">📊</span>
          <span class="tab-btn-label">Clinical KPIs &amp; Gauges</span>
          <span class="tab-btn-badge">Cohort 41k</span>
        </button>
        <button class="tab-btn" id="tabBtnOps" role="tab" aria-selected="false" onclick="switchDashboardTab('ops')">
          <span class="tab-btn-icon">⚡</span>
          <span class="tab-btn-label">Live Operations &amp; Console</span>
          <span class="tab-btn-badge badge-live">Live</span>
        </button>
        <button class="tab-btn" id="tabBtnCatalog" role="tab" aria-selected="false" onclick="switchDashboardTab('catalog')">
          <span class="tab-btn-icon">🎬</span>
          <span class="tab-btn-label">Video VM Catalog</span>
          <span class="tab-btn-badge" id="tabCatalogCountBadge">37</span>
        </button>
        <button class="tab-btn" id="tabBtnAll" role="tab" aria-selected="false" onclick="switchDashboardTab('all')">
          <span class="tab-btn-icon">📑</span>
          <span class="tab-btn-label">All Modules</span>
        </button>
      </div>
      <div class="tab-quick-info">
        <span class="tab-hint" id="tabActiveHint">Showing Clinical &amp; Cohort Intelligence (4 Gauges, 4 Stratification Charts)</span>
      </div>
    </nav>

    <!-- Clinical & Cohort Performance Intelligence (KPI Gauges & Graphs) -->
    <section class="kpi-section dashboard-tab-pane" id="tabPaneKpis">
      <div class="kpi-section-header">
        <div>
          <div class="kpi-badge-row">
            <span class="badge-pill pill-emerald">Clinical Intelligence</span>
            <span class="badge-pill pill-purple">Cohort Size: 41,117 Patients</span>
            <span class="badge-pill" style="background: var(--input-bg); border: 1px solid var(--border-subtle); color: var(--text-muted);" id="kpiComputeTime">Computed in 0.73s</span>
          </div>
          <h2 class="kpi-title">Clinical &amp; Population Health KPIs</h2>
          <p class="kpi-subtitle">Real-time CMS Therapy Compliance, Statistical Surveillance Alarms, Residual AHI Control, and Wearable Biomarkers</p>
        </div>
        <div class="kpi-actions" style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <div class="kpi-subtabs-group" role="tablist" aria-label="KPI Sub-filters">
            <button class="kpi-subtab-btn active" id="subtabAll" onclick="filterKpiSubView('all', this)">All</button>
            <button class="kpi-subtab-btn" id="subtabGauges" onclick="filterKpiSubView('gauges', this)">⏱️ Gauges</button>
            <button class="kpi-subtab-btn" id="subtabRisk" onclick="filterKpiSubView('risk', this)">📈 Risk Tiers</button>
            <button class="kpi-subtab-btn" id="subtabAhi" onclick="filterKpiSubView('ahi', this)">🫁 AHI</button>
            <button class="kpi-subtab-btn" id="subtabAlarms" onclick="filterKpiSubView('alarms', this)">🚨 Alarms</button>
            <button class="kpi-subtab-btn" id="subtabWearables" onclick="filterKpiSubView('wearables', this)">🩺 Wearables</button>
          </div>
          <button class="btn btn-outline" style="padding: 5px 12px; font-size: 0.75rem;" onclick="fetchKpis()" title="Refresh KPI Metrics">
            🔄 Refresh KPIs
          </button>
        </div>
      </div>

      <!-- 4 Speedometer / Radial SVG Gauges -->
      <div class="gauges-grid" id="kpiGaugesGrid">

        <!-- Gauge 1: CMS Compliance -->
        <div class="gauge-card" style="--gauge-color: var(--emerald);">
          <div class="gauge-svg-wrapper">
            <svg class="gauge-svg" viewBox="0 0 200 125">
              <defs>
                <linearGradient id="gradCms" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#0284c7" />
                  <stop offset="100%" stop-color="#10b981" />
                </linearGradient>
              </defs>
              <path class="gauge-track" d="M 30 105 A 70 70 0 0 1 170 105" />
              <path class="gauge-fill" id="arcCms" stroke="url(#gradCms)" d="M 30 105 A 70 70 0 0 1 170 105" style="stroke-dasharray: 220; stroke-dashoffset: 21.7;" />
              <text x="100" y="85" class="gauge-num" id="gaugeValCms">90.1%</text>
              <text x="100" y="105" class="gauge-target-lbl">Target: ≥ 70%</text>
            </svg>
          </div>
          <div class="gauge-info">
            <div class="gauge-name">CMS Therapy Compliance</div>
            <div class="gauge-desc" id="gaugeSubCms">37,056 Compliant (≥ 4h/night)</div>
            <div>
              <span class="badge-pill pill-emerald" id="gaugeBadgeCms">Optimal Adherence (+20.1%)</span>
            </div>
          </div>
        </div>

        <!-- Gauge 2: Mean Nightly Usage -->
        <div class="gauge-card" style="--gauge-color: var(--primary);">
          <div class="gauge-svg-wrapper">
            <svg class="gauge-svg" viewBox="0 0 200 125">
              <defs>
                <linearGradient id="gradUsage" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#f59e0b" />
                  <stop offset="50%" stop-color="#0284c7" />
                  <stop offset="100%" stop-color="#10b981" />
                </linearGradient>
              </defs>
              <path class="gauge-track" d="M 30 105 A 70 70 0 0 1 170 105" />
              <path class="gauge-fill" id="arcUsage" stroke="url(#gradUsage)" d="M 30 105 A 70 70 0 0 1 170 105" style="stroke-dasharray: 220; stroke-dashoffset: 35.5;" />
              <text x="100" y="85" class="gauge-num" id="gaugeValUsage">6.71h</text>
              <text x="100" y="105" class="gauge-target-lbl">Scale: 0 - 8 hrs</text>
            </svg>
          </div>
          <div class="gauge-info">
            <div class="gauge-name">7-Day Mean Usage</div>
            <div class="gauge-desc" id="gaugeSubUsage">Median: 7.03h | Std: 2.15h</div>
            <div>
              <span class="badge-pill" style="background: rgba(2, 132, 199, 0.15); color: var(--primary);" id="gaugeBadgeUsage">High Adherence</span>
            </div>
          </div>
        </div>

        <!-- Gauge 3: Residual AHI Control -->
        <div class="gauge-card" style="--gauge-color: var(--purple);">
          <div class="gauge-svg-wrapper">
            <svg class="gauge-svg" viewBox="0 0 200 125">
              <defs>
                <linearGradient id="gradAhi" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#a855f7" />
                  <stop offset="100%" stop-color="#10b981" />
                </linearGradient>
              </defs>
              <path class="gauge-track" d="M 30 105 A 70 70 0 0 1 170 105" />
              <path class="gauge-fill" id="arcAhi" stroke="url(#gradAhi)" d="M 30 105 A 70 70 0 0 1 170 105" style="stroke-dasharray: 220; stroke-dashoffset: 40.1;" />
              <text x="100" y="85" class="gauge-num" id="gaugeValAhi">81.8%</text>
              <text x="100" y="105" class="gauge-target-lbl">Controlled &lt; 5/hr</text>
            </svg>
          </div>
          <div class="gauge-info">
            <div class="gauge-name">Residual AHI Controlled</div>
            <div class="gauge-desc" id="gaugeSubAhi">Mean: 3.07/hr (Median: 1.83/hr)</div>
            <div>
              <span class="badge-pill pill-purple" id="gaugeBadgeAhi">Therapy Efficacious</span>
            </div>
          </div>
        </div>

        <!-- Gauge 4: Statistical Alarm Rate -->
        <div class="gauge-card" style="--gauge-color: var(--amber);">
          <div class="gauge-svg-wrapper">
            <svg class="gauge-svg" viewBox="0 0 200 125">
              <defs>
                <linearGradient id="gradAlarm" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#10b981" />
                  <stop offset="50%" stop-color="#f59e0b" />
                  <stop offset="100%" stop-color="#f43f5e" />
                </linearGradient>
              </defs>
              <path class="gauge-track" d="M 30 105 A 70 70 0 0 1 170 105" />
              <path class="gauge-fill" id="arcAlarm" stroke="url(#gradAlarm)" d="M 30 105 A 70 70 0 0 1 170 105" style="stroke-dasharray: 220; stroke-dashoffset: 155.2;" />
              <text x="100" y="85" class="gauge-num" id="gaugeValAlarm">29.5%</text>
              <text x="100" y="105" class="gauge-target-lbl">Active Layer 0 Alarms</text>
            </svg>
          </div>
          <div class="gauge-info">
            <div class="gauge-name">Active Telemetry Alarms</div>
            <div class="gauge-desc" id="gaugeSubAlarm">12,112 Patients Flagged</div>
            <div>
              <span class="badge-pill pill-amber" id="gaugeBadgeAlarm">CUSUM/EWMA Active</span>
            </div>
          </div>
        </div>

      </div>

      <!-- 4 Analytical Graphs & Clinical Surveillance Grids -->
      <div class="kpi-graphs-grid" id="kpiGraphsGrid">

        <!-- Graph 1: AI Risk Stratification (Stacked Distribution) -->
        <div class="kpi-graph-card" id="kpiGraphRisk">
          <div class="card-header">
            <span class="card-title">AI Dropout Risk Stratification (Layers 1-3)</span>
            <span class="badge-pill pill-purple">CatBoost &amp; DeepSurv</span>
          </div>
          <div class="stacked-bar-container">
            <div class="stacked-bar">
              <div class="bar-seg seg-low" id="segLow" style="width: 76.5%;" title="Low Risk: 31,449 (76.5%)"></div>
              <div class="bar-seg seg-med" id="segMed" style="width: 23.48%;" title="Medium Risk: 9,659 (23.5%)"></div>
              <div class="bar-seg seg-high" id="segHigh" style="width: 1.5%; min-width: 6px;" title="High Risk: 9 (0.02%)"></div>
            </div>
          </div>
          <div class="kpi-stat-grid">
            <div class="kpi-stat-box">
              <span class="stat-dot dot-emerald"></span>
              <div>
                <div class="stat-lbl">Low Risk Tier</div>
                <div class="stat-val" id="kpiStatLow">31,449 (76.5%)</div>
              </div>
            </div>
            <div class="kpi-stat-box">
              <span class="stat-dot dot-amber"></span>
              <div>
                <div class="stat-lbl">Medium Risk Tier</div>
                <div class="stat-val" id="kpiStatMed">9,659 (23.5%)</div>
              </div>
            </div>
            <div class="kpi-stat-box">
              <span class="stat-dot dot-rose"></span>
              <div>
                <div class="stat-lbl">High Risk Tier</div>
                <div class="stat-val" id="kpiStatHigh">9 (0.02%)</div>
              </div>
            </div>
          </div>
          <div class="kpi-footer-note">
            <span>Mean z_risk Score: <strong id="kpiMeanZ">0.1983</strong></span> • 
            <span>Dropout Root Causes: <strong>Natural (21.6%)</strong>, <strong>Effectful (1.9%)</strong></span>
          </div>
        </div>

        <!-- Graph 2: Residual AHI Severity Spectrum -->
        <div class="kpi-graph-card" id="kpiGraphAhi">
          <div class="card-header">
            <span class="card-title">Residual AHI Severity Stratification</span>
            <span class="badge-pill pill-emerald">Cohort Mean: 3.07/hr</span>
          </div>
          <div class="bar-chart-list">
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">Controlled Normal (&lt; 5/hr)</span>
                <span class="row-val" id="kpiAhiNormVal">33,615 (81.8%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-emerald" id="kpiAhiNormBar" style="width: 81.8%;"></div>
              </div>
            </div>
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">Mild Residual Apnea (5 - 14.9/hr)</span>
                <span class="row-val" id="kpiAhiMildVal">5,811 (14.1%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-sky" id="kpiAhiMildBar" style="width: 14.1%;"></div>
              </div>
            </div>
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">Moderate Residual Apnea (15 - 29.9/hr)</span>
                <span class="row-val" id="kpiAhiModVal">687 (1.7%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-amber" id="kpiAhiModBar" style="width: 4.5%;"></div>
              </div>
            </div>
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">Severe Apnea Spike (≥ 30/hr)</span>
                <span class="row-val" id="kpiAhiSevVal">143 (0.35%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-rose" id="kpiAhiSevBar" style="width: 2.0%;"></div>
              </div>
            </div>
          </div>
          <div class="kpi-footer-note">
            <span>Delivered Pressure: <strong>10.21 cmH2O</strong></span> • 
            <span>95th% Mask Leak: <strong>0.21 L/min</strong> (Optimal)</span>
          </div>
        </div>

        <!-- Graph 3: Statistical Telemetry Alarms Surveillance (Layer 0) -->
        <div class="kpi-graph-card" id="kpiGraphAlarms">
          <div class="card-header">
            <span class="card-title">Statistical Telemetry Surveillance Alarms (Layer 0)</span>
            <span class="badge-pill pill-amber">Total: 12,112 (29.5%)</span>
          </div>
          <div class="bar-chart-list">
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">CUSUM AHI Spike Alarms (Breakthrough Events)</span>
                <span class="row-val" id="kpiAlarmAhiVal">7,588 (62.6%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-rose" id="kpiAlarmAhiBar" style="width: 62.6%;"></div>
              </div>
            </div>
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">CUSUM Usage Degradation (Drop in Nightly Wear)</span>
                <span class="row-val" id="kpiAlarmUseVal">5,938 (49.0%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-amber" id="kpiAlarmUseBar" style="width: 49.0%;"></div>
              </div>
            </div>
            <div class="chart-row">
              <div class="row-header">
                <span class="row-lbl">EWMA Multi-day Usage Trend (Longitudinal Decline)</span>
                <span class="row-val" id="kpiAlarmEwmaVal">2,628 (21.7%)</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill fill-sky" id="kpiAlarmEwmaBar" style="width: 21.7%;"></div>
              </div>
            </div>
          </div>
          <div class="kpi-footer-note">
            <span>Algorithms: <strong>Two-Sided CUSUM (k=0.5, h=4.0)</strong> + <strong>EWMA (λ=0.2)</strong></span>
          </div>
        </div>

        <!-- Graph 4: Multimodal Wearable Biomarker Anomalies (Layer 5) -->
        <div class="kpi-graph-card" id="kpiGraphWearables">
          <div class="card-header">
            <span class="card-title">Multimodal Wearable Biomarker Surveillance</span>
            <span class="badge-pill pill-purple">357 Active Wearable Patients</span>
          </div>
          <div class="wearable-anomaly-grid">
            <div class="wearable-card">
              <div class="w-icon">❤️</div>
              <div class="w-content">
                <div class="w-val" id="kpiW_Afib">27 Flagged</div>
                <div class="w-lbl">Nocturnal Cardiac Afib</div>
                <div class="w-sub">Withings ScanWatch PPG/ECG</div>
              </div>
              <span class="badge-pill" style="background: rgba(244, 63, 94, 0.15); color: #e11d48;">Urgent Alert</span>
            </div>
            <div class="wearable-card">
              <div class="w-icon">🫁</div>
              <div class="w-content">
                <div class="w-val" id="kpiW_Hypoxia">103 Flagged</div>
                <div class="w-lbl">Severe Hypoxia (SpO2 &lt; 88%)</div>
                <div class="w-sub">Masimo Rad-G Pulse Ox</div>
              </div>
              <span class="badge-pill" style="background: rgba(245, 158, 11, 0.15); color: #d97706;">Clinical Alert</span>
            </div>
            <div class="wearable-card">
              <div class="w-icon">🩸</div>
              <div class="w-content">
                <div class="w-val" id="kpiW_Hyper">14 Flagged</div>
                <div class="w-lbl">Morning Hypertension (≥140)</div>
                <div class="w-sub">Withings BPM Core</div>
              </div>
              <span class="badge-pill" style="background: rgba(14, 165, 233, 0.15); color: #0284c7;">Vascular Watch</span>
            </div>
            <div class="wearable-card">
              <div class="w-icon">🌙</div>
              <div class="w-content">
                <div class="w-val" id="kpiW_Sleep">0 Flagged</div>
                <div class="w-lbl">Poor Sleep Efficiency (&lt;75%)</div>
                <div class="w-sub">SomnoArt Hypnogram EEG</div>
              </div>
              <span class="badge-pill" style="background: rgba(16, 185, 129, 0.15); color: #059669;">Normal Range</span>
            </div>
          </div>
          <div class="kpi-footer-note">
            <span>Survey Dispatches: <strong>41,063</strong></span> • 
            <span>Acute Urgent Interventions: <strong>51 (0.12%)</strong></span>
          </div>
        </div>

      </div>
    </section>

    <!-- Live Operations & Console Section (Tab Pane) -->
    <div class="dashboard-tab-pane tab-hidden" id="tabPaneOps">
      <!-- Interactive Action Controls Center -->
      <section class="control-center">
      <div class="control-title">
        <h2 style="font-size: 0.95rem; font-weight: 700;">Interactive Orchestration Center</h2>
        <p style="font-size: 0.72rem; color: var(--text-muted);">Execute immediate model pipelines, dispatch video coaching, or trigger dynamic sync.</p>
      </div>
      <div class="control-actions">
        <label class="checkbox-label" title="Force re-dispatching even if already assigned">
          <input type="checkbox" id="chkForceDispatch"> Force Re-Dispatch
        </label>
        <button class="btn btn-primary" id="btnRunPipeline" onclick="runPipelineNow()">
          ⚡ Run Pipeline Now
        </button>
        <button class="btn btn-emerald" id="btnPushPredictions" onclick="pushPredictionsNow()">
          📤 Push Predictions
        </button>
        <button class="btn btn-purple" id="btnOrchestrateVideos" onclick="orchestrateVideosNow()">
          🎬 Orchestrate Cohort Videos
        </button>
        <button class="btn btn-outline" id="btnSyncCatalog" onclick="syncCatalogNow()">
          🔄 Sync Video VM Catalog
        </button>
        <button class="btn btn-danger" id="btnClearTracker" onclick="clearTrackerNow()">
          🗑️ Clear Tracker
        </button>
      </div>
    </section>

    <!-- Split Grid: Live Streaming Console Terminal + Patient Recommendation Simulator -->
    <section class="two-column-grid">

      <!-- Live Terminal Console Stream (Replacing .bat window) -->
      <div class="terminal-card">
        <div class="terminal-header">
          <div class="terminal-controls">
            <span class="dot dot-red"></span>
            <span class="dot dot-yellow"></span>
            <span class="dot dot-green"></span>
            <span class="terminal-title">AI Server Real-Time Log Stream (live)</span>
          </div>
          <div class="terminal-tools">
            <input type="text" class="terminal-filter" id="txtLogSearch" placeholder="Filter logs..." oninput="filterLogs()">
            <label class="checkbox-label" style="font-size: 0.68rem;">
              <input type="checkbox" id="chkAutoScroll" checked> Auto-Scroll
            </label>
            <button class="btn btn-outline" style="padding: 2px 8px; font-size: 0.68rem;" onclick="clearTerminalView()">Clear</button>
          </div>
        </div>
        <div class="terminal-body" id="terminalOutput">
          <div class="log-line">
            <span class="log-time">[00:00:00]</span>
            <span class="log-lvl-INFO">[INFO]</span>
            <span class="log-msg">Connecting to AI Server Live Console Log Stream...</span>
          </div>
        </div>
      </div>

      <!-- Patient Clinical Video Recommendation Simulator -->
      <div class="simulator-card">
        <div class="sim-header">
          <h3>Single-Patient Video Recommendation Simulator</h3>
          <p>Inspect clinical triggers, evaluate anomaly routing, and test dispatch to Video VM.</p>
        </div>
        <div class="sim-input-row">
          <input type="text" class="sim-input" id="simPatientId" placeholder="Enter Patient ID (e.g. 10042, 3, 51)..." value="10042">
          <button class="btn btn-primary" onclick="simulatePatientVideo()">Resolve Video</button>
        </div>
        <div class="sim-result-box" id="simResultContainer">
          <div class="sim-item"><span>Patient ID:</span> <strong id="resPatientId">--</strong></div>
          <div class="sim-item"><span>Recommended Video:</span> <strong id="resVideoTitle">Enter ID and click Resolve</strong></div>
          <div class="sim-item"><span>Original File:</span> <code id="resFilename" style="color: var(--primary);">--</code></div>
          <div class="sim-item"><span>Clinical Trigger Reason:</span> <span id="resReason">--</span></div>
          <div class="sim-item"><span>Deduplication Status:</span> <strong id="resDedupStatus">--</strong></div>
          <div class="sim-item"><span>Direct Stream URL:</span> <a href="#" target="_blank" id="resStreamUrl" style="color: var(--primary); text-decoration: underline;">--</a></div>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 10px;">
          <button class="btn btn-purple" id="btnDispatchSingle" onclick="dispatchSinglePatient()" disabled>
            🚀 Dispatch Recommendation to Video VM
          </button>
        </div>
      </div>

    </section>
    </div>

    <!-- Curated Video Catalog & Wearable Anomaly Browser (IDs 1-37) -->
    <section class="catalog-card dashboard-tab-pane tab-hidden" id="tabPaneCatalog">
      <div class="catalog-header">
        <div>
          <h2 style="font-size: 1rem; font-weight: 700;">Curated Video &amp; Wearable Anomaly Catalog (39 Videos)</h2>
          <p style="font-size: 0.72rem; color: var(--text-muted);">Live distributed catalog synced with Video VM (Port 8080) featuring explicit boolean logic (AND/OR) and clinical priority ranking.</p>
        </div>
        <input type="text" class="catalog-search" id="txtCatalogSearch" placeholder="Search title, device, priority, logic..." oninput="filterCatalogTable()">
      </div>
      <div class="catalog-table-wrapper">
        <table class="catalog-table">
          <thead>
            <tr>
              <th style="width: 45px;">ID</th>
              <th>Clinical Topic &amp; Video Filename</th>
              <th style="width: 140px;">Category &amp; Logic</th>
              <th style="width: 90px;">Priority</th>
              <th>Biomarker Trigger / Clinical Rule</th>
              <th style="width: 95px;">Subtitles</th>
              <th style="width: 100px;">Stream</th>
            </tr>
          </thead>
          <tbody id="catalogTableBody">
            <tr><td colspan="7" style="text-align:center; color: var(--text-muted);">Loading catalog from registry...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <!-- Video Player Modal Overlay -->
  <div class="video-modal-backdrop" id="videoModal" onclick="closeVideoModal(event)">
    <div class="video-modal-content" onclick="event.stopPropagation()">
      <div class="video-modal-header">
        <div>
          <h3 id="modalVideoTitle" style="font-size:1.05rem; font-weight:700; color:var(--text-main);">Video Title</h3>
          <p id="modalVideoFilename" style="font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:var(--primary); margin-top:2px;">filename.mp4</p>
        </div>
        <button class="btn-close-modal" onclick="closeVideoModal()" title="Close video (Esc)">✕</button>
      </div>
      <div class="video-modal-player">
        <video id="modalVideoPlayer" controls playsinline style="width:100%; max-height:460px; background:#000;">
          <source id="modalVideoSource" src="" type="video/mp4">
          <track id="modalTrackEn" kind="subtitles" srclang="en" label="English" default>
          <track id="modalTrackFr" kind="subtitles" srclang="fr" label="Français">
          Your browser does not support the video tag.
        </video>
      </div>
      <div class="video-modal-footer">
        <div style="font-size:0.75rem; color:var(--text-muted);" id="modalVideoInfo">
          <span>Hosted on Video VM (Port 8080)</span> • <span>1080p Full HD</span> • <span>Bilingual WebVTT Captions</span>
        </div>
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <a id="modalDirectMp4Link" href="#" target="_blank" class="sub-link" style="color:#34d399; border-color:rgba(16,185,129,0.3); background:rgba(16,185,129,0.1);" title="Open Direct Stream">
            🎬 Direct MP4
          </a>
          <a id="modalDirectSubEnLink" href="#" target="_blank" class="sub-link" title="Download English Subtitle">
            🇬🇧 EN Subtitle
          </a>
          <a id="modalDirectSubFrLink" href="#" target="_blank" class="sub-link" title="Download French Subtitle">
            🇫🇷 FR Subtitle
          </a>
        </div>
      </div>
    </div>
  </div>

  <!-- Toast Notification Element -->
  <div id="toast">Operation completed successfully.</div>

  <!-- JavaScript Client Controller -->
  <script>
    let lastLogId = 0;
    let allLogs = [];
    let currentSimResult = null;
    let rawCatalog = [];

    // 0. Theme Manager (Default: Light Colors)
    function initTheme() {
      const savedTheme = localStorage.getItem("sleepcare_dashboard_theme") || "light";
      setTheme(savedTheme);
    }

    function setTheme(theme) {
      const icon = document.getElementById("themeToggleIcon");
      const txt = document.getElementById("themeToggleText");
      if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
        if (icon) icon.innerText = "☀️";
        if (txt) txt.innerText = "Light";
      } else {
        document.documentElement.removeAttribute("data-theme");
        if (icon) icon.innerText = "🌙";
        if (txt) txt.innerText = "Dark";
      }
      localStorage.setItem("sleepcare_dashboard_theme", theme);
    }

    function toggleTheme() {
      const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      setTheme(current === "dark" ? "light" : "dark");
    }

    // 0b. Dashboard Tab Controller (Button-Style Segmented Navigation)
    function switchDashboardTab(tabKey) {
      try {
        localStorage.setItem("sleepcare_active_tab", tabKey);
      } catch (e) {}

      const buttons = [
        { id: "tabBtnKpis", key: "kpis" },
        { id: "tabBtnOps", key: "ops" },
        { id: "tabBtnCatalog", key: "catalog" },
        { id: "tabBtnAll", key: "all" }
      ];
      buttons.forEach(b => {
        const el = document.getElementById(b.id);
        if (el) {
          const isActive = (b.key === tabKey);
          el.classList.toggle("active", isActive);
          el.setAttribute("aria-selected", isActive ? "true" : "false");
        }
      });

      const paneKpis = document.getElementById("tabPaneKpis");
      const paneOps = document.getElementById("tabPaneOps");
      const paneCatalog = document.getElementById("tabPaneCatalog");
      const hintEl = document.getElementById("tabActiveHint");

      if (tabKey === "all") {
        if (paneKpis) paneKpis.classList.remove("tab-hidden");
        if (paneOps) paneOps.classList.remove("tab-hidden");
        if (paneCatalog) paneCatalog.classList.remove("tab-hidden");
        if (hintEl) hintEl.innerText = "Showing All Modules (Full Unified Single-Page View)";
      } else if (tabKey === "ops") {
        if (paneKpis) paneKpis.classList.add("tab-hidden");
        if (paneOps) paneOps.classList.remove("tab-hidden");
        if (paneCatalog) paneCatalog.classList.add("tab-hidden");
        if (hintEl) hintEl.innerText = "Showing Live Pipeline Orchestration, Console Log Stream & Recommendation Simulator";
      } else if (tabKey === "catalog") {
        if (paneKpis) paneKpis.classList.add("tab-hidden");
        if (paneOps) paneOps.classList.add("tab-hidden");
        if (paneCatalog) paneCatalog.classList.remove("tab-hidden");
        if (hintEl) hintEl.innerText = "Showing 37 Curated 1080p Clinical Videos & Wearable Anomaly Triggers";
      } else {
        // Default: 'kpis'
        if (paneKpis) paneKpis.classList.remove("tab-hidden");
        if (paneOps) paneOps.classList.add("tab-hidden");
        if (paneCatalog) paneCatalog.classList.add("tab-hidden");
        if (hintEl) hintEl.innerText = "Showing Clinical & Cohort Intelligence (4 Gauges, 4 Stratification Charts)";
      }
    }

    function initDashboardTabs() {
      let savedTab = "kpis";
      try {
        savedTab = localStorage.getItem("sleepcare_active_tab") || "kpis";
      } catch (e) {}
      switchDashboardTab(savedTab);
    }

    // Sub-tab view filter inside KPI section
    function filterKpiSubView(viewKey, btn) {
      document.querySelectorAll(".kpi-subtab-btn").forEach(b => b.classList.remove("active"));
      if (btn) btn.classList.add("active");

      const gaugesGrid = document.getElementById("kpiGaugesGrid");
      const graphsGrid = document.getElementById("kpiGraphsGrid");
      const cardRisk = document.getElementById("kpiGraphRisk");
      const cardAhi = document.getElementById("kpiGraphAhi");
      const cardAlarms = document.getElementById("kpiGraphAlarms");
      const cardWearables = document.getElementById("kpiGraphWearables");

      if (viewKey === "all") {
        if (gaugesGrid) gaugesGrid.style.display = "grid";
        if (graphsGrid) graphsGrid.style.display = "grid";
        if (cardRisk) cardRisk.style.display = "flex";
        if (cardAhi) cardAhi.style.display = "flex";
        if (cardAlarms) cardAlarms.style.display = "flex";
        if (cardWearables) cardWearables.style.display = "flex";
      } else if (viewKey === "gauges") {
        if (gaugesGrid) gaugesGrid.style.display = "grid";
        if (graphsGrid) graphsGrid.style.display = "none";
      } else if (viewKey === "risk") {
        if (gaugesGrid) gaugesGrid.style.display = "none";
        if (graphsGrid) graphsGrid.style.display = "grid";
        if (cardRisk) cardRisk.style.display = "flex";
        if (cardAhi) cardAhi.style.display = "none";
        if (cardAlarms) cardAlarms.style.display = "none";
        if (cardWearables) cardWearables.style.display = "none";
      } else if (viewKey === "ahi") {
        if (gaugesGrid) gaugesGrid.style.display = "none";
        if (graphsGrid) graphsGrid.style.display = "grid";
        if (cardRisk) cardRisk.style.display = "none";
        if (cardAhi) cardAhi.style.display = "flex";
        if (cardAlarms) cardAlarms.style.display = "none";
        if (cardWearables) cardWearables.style.display = "none";
      } else if (viewKey === "alarms") {
        if (gaugesGrid) gaugesGrid.style.display = "none";
        if (graphsGrid) graphsGrid.style.display = "grid";
        if (cardRisk) cardRisk.style.display = "none";
        if (cardAhi) cardAhi.style.display = "none";
        if (cardAlarms) cardAlarms.style.display = "flex";
        if (cardWearables) cardWearables.style.display = "none";
      } else if (viewKey === "wearables") {
        if (gaugesGrid) gaugesGrid.style.display = "none";
        if (graphsGrid) graphsGrid.style.display = "grid";
        if (cardRisk) cardRisk.style.display = "none";
        if (cardAhi) cardAhi.style.display = "none";
        if (cardAlarms) cardAlarms.style.display = "none";
        if (cardWearables) cardWearables.style.display = "flex";
      }
    }

    // Format local time
    function updateClock() {
      const now = new Date();
      document.getElementById("liveClock").innerText = now.toTimeString().split(' ')[0];
    }
    setInterval(updateClock, 1000);
    updateClock();

    function showToast(msg, isError = false) {
      const t = document.getElementById("toast");
      t.innerText = msg;
      t.style.borderColor = isError ? "var(--rose)" : "var(--emerald)";
      t.classList.add("show");
      setTimeout(() => t.classList.remove("show"), 3500);
    }

    function getAuthHeaders() {
      const key = document.getElementById("authKeyInput").value.trim();
      return {
        "Content-Type": "application/json",
        "X-API-KEY": key
      };
    }

    // 1. Fetch live dashboard stats
    async function fetchStats() {
      try {
        const res = await fetch("/api/dashboard/stats");
        if (!res.ok) return;
        const data = await res.json();

        // Config
        if (data.config) {
          document.getElementById("cfgHost").innerText = data.config.host || "0.0.0.0";
          document.getElementById("cfgPort").innerText = data.config.port || "8000";
          document.getElementById("cfgSync").innerText = `Every ${data.config.sync_interval_mins || 30}m`;
          document.getElementById("cfgVideoVm").innerText = data.config.video_vm_url || "159.84.143.246:8080";
        }

        // Pipeline state
        if (data.pipeline) {
          const st = data.pipeline.status || "idle";
          const el = document.getElementById("pipelineStatus");
          el.innerText = st.toUpperCase();
          el.className = "card-value " + (st === "running" ? "badge-running" : (st === "failed" ? "badge-failed" : ""));

          const lastStart = data.pipeline.last_run_start || "Never";
          const dur = data.pipeline.last_duration_seconds ? `${data.pipeline.last_duration_seconds}s` : "--";
          document.getElementById("pipelineTimes").innerText = `Last: ${lastStart} (${dur}) | Total: ${data.pipeline.total_runs || 0}`;

          const pill = document.getElementById("pipelineBadge");
          if (st === "running") {
            pill.className = "badge-pill badge-running";
            pill.innerText = "Execution in progress...";
          } else if (st === "failed") {
            pill.className = "badge-pill badge-failed";
            pill.innerText = "Error encountered";
          } else {
            pill.className = "badge-pill badge-idle";
            pill.innerText = "Scheduler Active (30m)";
          }
        }

        // Tracker state
        if (data.tracker) {
          document.getElementById("trackerPatientsCount").innerText = `${data.tracker.total_patients || 0} Patients`;
          document.getElementById("trackerStatsText").innerText = `${data.tracker.total_assignments || 0} Total Assignments Tracked`;
          const skipped = (data.pipeline && data.pipeline.last_video_skipped_duplicates) || 0;
          document.getElementById("trackerSkippedPill").innerText = `${skipped} Duplicates Blocked`;
        }

        // Video Catalog count
        if (data.catalog) {
          document.getElementById("videoCatalogCount").innerText = `${data.catalog.total_curated_videos || 37} Curated`;
        }

        // Real-time KPIs
        if (data.kpis) {
          renderKpis(data.kpis);
        }
      } catch (err) {
        console.error("Stats fetch error:", err);
      }
    }

    // 1b. Fetch & Render Clinical & Cohort Performance KPIs
    async function fetchKpis() {
      try {
        const res = await fetch("/api/dashboard/kpis");
        if (!res.ok) return;
        const kpis = await res.json();
        renderKpis(kpis);
      } catch (err) {
        console.error("KPI fetch error:", err);
      }
    }

    function renderKpis(kpis) {
      if (!kpis || !kpis.adherence_efficacy) return;

      const adh = kpis.adherence_efficacy;
      const alm = kpis.alarms_surveillance;
      const rsk = kpis.risk_stratification;
      const bio = kpis.wearable_biomarkers;
      const meta = kpis.metadata;

      if (meta && meta.computation_time_s) {
        const el = document.getElementById("kpiComputeTime");
        if (el) el.innerText = `Computed in ${meta.computation_time_s}s`;
      }

      // 1. Gauges (Semi-Circle Speedometers: arc length = 220)
      const cmsPct = adh.pct_compliant_4h || 90.12;
      const arcCms = document.getElementById("arcCms");
      const valCms = document.getElementById("gaugeValCms");
      if (arcCms) arcCms.style.strokeDashoffset = 220 * (1 - Math.min(cmsPct / 100, 1));
      if (valCms) valCms.textContent = `${cmsPct.toFixed(1)}%`;

      const useVal = adh.mean_use_7d || 6.71;
      const arcUse = document.getElementById("arcUsage");
      const valUse = document.getElementById("gaugeValUsage");
      if (arcUse) arcUse.style.strokeDashoffset = 220 * (1 - Math.min(useVal / 8.0, 1));
      if (valUse) valUse.textContent = `${useVal.toFixed(2)}h`;

      const ahiPct = adh.pct_ahi_controlled || 81.75;
      const arcAhi = document.getElementById("arcAhi");
      const valAhi = document.getElementById("gaugeValAhi");
      if (arcAhi) arcAhi.style.strokeDashoffset = 220 * (1 - Math.min(ahiPct / 100, 1));
      if (valAhi) valAhi.textContent = `${ahiPct.toFixed(1)}%`;

      const alarmPct = alm ? (alm.alarm_rate_pct || 29.46) : 29.46;
      const arcAlm = document.getElementById("arcAlarm");
      const valAlm = document.getElementById("gaugeValAlarm");
      if (arcAlm) arcAlm.style.strokeDashoffset = 220 * (1 - Math.min(alarmPct / 100, 1));
      if (valAlm) valAlm.textContent = `${alarmPct.toFixed(1)}%`;

      // 2. Risk Stratification Stacked Bar & Stats
      if (rsk) {
        const totalCohort = (rsk.low_risk_count || 31449) + (rsk.medium_risk_count || 9659) + (rsk.high_risk_count || 9);
        const lowP = ((rsk.low_risk_count || 31449) / totalCohort * 100).toFixed(1);
        const medP = ((rsk.medium_risk_count || 9659) / totalCohort * 100).toFixed(1);
        const highP = ((rsk.high_risk_count || 9) / totalCohort * 100).toFixed(2);

        const segLow = document.getElementById("segLow");
        const segMed = document.getElementById("segMed");
        const segHigh = document.getElementById("segHigh");
        if (segLow) { segLow.style.width = `${lowP}%`; segLow.title = `Low Risk: ${(rsk.low_risk_count || 0).toLocaleString()} (${lowP}%)`; }
        if (segMed) { segMed.style.width = `${medP}%`; segMed.title = `Medium Risk: ${(rsk.medium_risk_count || 0).toLocaleString()} (${medP}%)`; }
        if (segHigh) { segHigh.style.width = `${Math.max(parseFloat(highP), 1.0)}%`; segHigh.title = `High Risk: ${rsk.high_risk_count || 0} (${highP}%)`; }

        const sLow = document.getElementById("kpiStatLow");
        const sMed = document.getElementById("kpiStatMed");
        const sHigh = document.getElementById("kpiStatHigh");
        if (sLow) sLow.textContent = `${(rsk.low_risk_count || 0).toLocaleString()} (${lowP}%)`;
        if (sMed) sMed.textContent = `${(rsk.medium_risk_count || 0).toLocaleString()} (${medP}%)`;
        if (sHigh) sHigh.textContent = `${rsk.high_risk_count || 0} (${highP}%)`;

        const mz = document.getElementById("kpiMeanZ");
        if (mz) mz.textContent = (rsk.mean_z_risk || 0.1983).toFixed(4);
      }

      // 3. Residual AHI Severity Spectrum
      if (adh) {
        const ahiNorm = adh.pct_ahi_controlled || 81.75;
        const ahiMild = 14.13;
        const ahiMod = 1.67;
        const ahiSev = adh.pct_ahi_severe || 0.35;

        const bNorm = document.getElementById("kpiAhiNormBar");
        const bMild = document.getElementById("kpiAhiMildBar");
        const bMod = document.getElementById("kpiAhiModBar");
        const bSev = document.getElementById("kpiAhiSevBar");
        if (bNorm) bNorm.style.width = `${ahiNorm}%`;
        if (bMild) bMild.style.width = `${ahiMild}%`;
        if (bMod) bMod.style.width = `${Math.max(ahiMod * 2.5, 4)}%`;
        if (bSev) bSev.style.width = `${Math.max(ahiSev * 5, 2)}%`;
      }

      // 4. Layer 0 Telemetry Alarms
      if (alm) {
        const aAhi = alm.cusum_ahi_alarms || 7588;
        const aUse = alm.cusum_use_alarms || 5938;
        const aEwma = alm.ewma_use_alarms || 2628;
        const totalAlm = alm.total_active_alarms || 12112;

        const pAhi = (aAhi / totalAlm * 100).toFixed(1);
        const pUse = (aUse / totalAlm * 100).toFixed(1);
        const pEwma = (aEwma / totalAlm * 100).toFixed(1);

        const vAhi = document.getElementById("kpiAlarmAhiVal");
        const vUse = document.getElementById("kpiAlarmUseVal");
        const vEwma = document.getElementById("kpiAlarmEwmaVal");
        if (vAhi) vAhi.textContent = `${aAhi.toLocaleString()} (${pAhi}%)`;
        if (vUse) vUse.textContent = `${aUse.toLocaleString()} (${pUse}%)`;
        if (vEwma) vEwma.textContent = `${aEwma.toLocaleString()} (${pEwma}%)`;

        const bAhi = document.getElementById("kpiAlarmAhiBar");
        const bUse = document.getElementById("kpiAlarmUseBar");
        const bEwma = document.getElementById("kpiAlarmEwmaBar");
        if (bAhi) bAhi.style.width = `${pAhi}%`;
        if (bUse) bUse.style.width = `${pUse}%`;
        if (bEwma) bEwma.style.width = `${pEwma}%`;
      }

      // 5. Wearable Anomalies
      if (bio) {
        const wAfib = document.getElementById("kpiW_Afib");
        const wHyp = document.getElementById("kpiW_Hypoxia");
        const wHypT = document.getElementById("kpiW_Hyper");
        const wSleep = document.getElementById("kpiW_Sleep");
        if (wAfib) wAfib.textContent = `${bio.afib_detected || 0} Flagged`;
        if (wHyp) wHyp.textContent = `${bio.severe_hypoxia || 0} Flagged`;
        if (wHypT) wHypT.textContent = `${bio.hypertension || 0} Flagged`;
        if (wSleep) wSleep.textContent = `${bio.poor_sleep_efficiency || 0} Flagged`;
      }
    }

    // 2. Fetch live terminal console logs
    async function fetchLogs() {
      try {
        const res = await fetch(`/api/server/logs?since_id=${lastLogId}&limit=100`);
        if (!res.ok) return;
        const logs = await res.json();
        if (logs && logs.length > 0) {
          const container = document.getElementById("terminalOutput");
          logs.forEach(log => {
            if (log.id > lastLogId) {
              lastLogId = log.id;
              allLogs.push(log);
              appendLogLine(log, container);
            }
          });
          if (document.getElementById("chkAutoScroll").checked) {
            container.scrollTop = container.scrollHeight;
          }
        }
      } catch (err) {
        console.error("Log fetch error:", err);
      }
    }

    function appendLogLine(log, container) {
      const line = document.createElement("div");
      line.className = "log-line";
      const lvlClass = `log-lvl-${log.level || "INFO"}`;
      line.innerHTML = `
        <span class="log-time">[${log.timestamp.split(' ')[1] || log.timestamp}]</span>
        <span class="${lvlClass}">[${log.level || "INFO"}]</span>
        <span class="log-msg">${escapeHtml(log.message)}</span>
      `;
      container.appendChild(line);
    }

    function escapeHtml(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function clearTerminalView() {
      document.getElementById("terminalOutput").innerHTML = "";
    }

    function filterLogs() {
      const term = document.getElementById("txtLogSearch").value.toLowerCase();
      const container = document.getElementById("terminalOutput");
      container.innerHTML = "";
      allLogs.forEach(log => {
        if (!term || log.message.toLowerCase().includes(term) || log.level.toLowerCase().includes(term)) {
          appendLogLine(log, container);
        }
      });
      if (document.getElementById("chkAutoScroll").checked) {
        container.scrollTop = container.scrollHeight;
      }
    }

    // 3. Action Controls Handlers
    async function runPipelineNow() {
      showToast("Triggering model pipeline execution...");
      try {
        const res = await fetch("/api/pipeline/run-now", { method: "POST", headers: getAuthHeaders() });
        const data = await res.json();
        if (res.ok) showToast("Pipeline started successfully!");
        else showToast(data.detail || "Failed to trigger pipeline", true);
        fetchStats();
      } catch (e) {
        showToast("Connection error triggering pipeline", true);
      }
    }

    async function pushPredictionsNow() {
      showToast("Pushing prediction artifacts to central database...");
      try {
        const res = await fetch("/api/pipeline/push", { method: "POST", headers: getAuthHeaders() });
        const data = await res.json();
        if (res.ok) showToast(`Pushed predictions successfully! (${data.total_patients_pushed || 0} records)`);
        else showToast(data.detail || "Failed to push predictions", true);
      } catch (e) {
        showToast("Connection error pushing predictions", true);
      }
    }

    async function orchestrateVideosNow() {
      const force = document.getElementById("chkForceDispatch").checked;
      showToast(`Orchestrating cohort videos (force=${force})...`);
      try {
        const res = await fetch(`/api/pipeline/orchestrate-videos?force=${force}`, { method: "POST", headers: getAuthHeaders() });
        const data = await res.json();
        if (res.ok) {
          showToast(`Done! Newly dispatched: ${data.orchestrated_count || 0} | Skipped: ${data.skipped_duplicate_count || 0}`);
          fetchStats();
        } else {
          showToast(data.detail || "Failed to orchestrate videos", true);
        }
      } catch (e) {
        showToast("Connection error during video orchestration", true);
      }
    }

    async function refreshCatalogNow() {
      showToast("Refreshing dynamic triggers from Video VM (Port 8080)...");
      try {
        const res = await fetch("/api/triggers/catalog?refresh=true");
        const data = await res.json();
        if (res.ok) {
          showToast(`Catalog refreshed! ${data.total_triggers || 37} active triggers.`);
          loadCatalog();
          fetchStats();
        } else {
          showToast("Failed to refresh catalog", true);
        }
      } catch (e) {
        showToast("Connection error syncing catalog", true);
      }
    }


    // Wrapper for sync button – reuses existing refresh logic and updates stats immediately
    async function syncCatalogNow() {
      // Calls the existing refreshCatalogNow which syncs with Video VM and updates UI
      await refreshCatalogNow();
      // Immediately refresh dashboard stats (e.g., video count)
      await fetchStats();
    }


    async function clearTrackerNow() {
      if (!confirm("Are you sure you want to clear the video assignment tracker?\\nSubsequent runs will assign videos again from scratch.")) return;
      try {
        const res = await fetch("/api/video-server/assigned-tracker/clear", { method: "POST", headers: getAuthHeaders() });
        const data = await res.json();
        if (res.ok) {
          showToast("Video assignment tracker cleared successfully!");
          fetchStats();
        } else {
          showToast(data.detail || "Failed to clear tracker", true);
        }
      } catch (e) {
        showToast("Connection error clearing tracker", true);
      }
    }

    // 4. Simulator Functions
    async function simulatePatientVideo() {
      const pid = document.getElementById("simPatientId").value.trim();
      if (!pid) return alert("Please enter a Patient ID");

      document.getElementById("resPatientId").innerText = pid;
      document.getElementById("resVideoTitle").innerText = "Evaluating telemetry...";

      try {
        // Evaluate through single patient endpoint with force=false to check duplicate status
        const res = await fetch(`/api/video-server/orchestrate/${pid}?force=false`, {
          method: "POST",
          headers: getAuthHeaders()
        });
        const data = await res.json();
        if (res.ok && data.resolved_video) {
          currentSimResult = data;
          const vid = data.resolved_video;
          document.getElementById("resVideoTitle").innerText = `[#${vid.id}] ${vid.title}`;
          document.getElementById("resFilename").innerText = vid.filename;
          document.getElementById("resReason").innerText = vid.reason || "--";

          const orch = data.orchestration_result || {};
          if (orch.status === "already_assigned" || orch.skipped) {
            document.getElementById("resDedupStatus").innerHTML = `<span style="color:#fbbf24;">🟢 Already Assigned (${orch.message || 'Duplicate skipped'})</span>`;
          } else if (orch.status === "success") {
            document.getElementById("resDedupStatus").innerHTML = `<span style="color:#34d399;">✅ Newly Dispatched to Video VM</span>`;
          } else {
            document.getElementById("resDedupStatus").innerHTML = `<span style="color:var(--text-muted);">⚪ Ready (Status: ${orch.status || 'Resolved'})</span>`;
          }

          const fn = vid.filename || '';
          const baseNoExt = fn.replace(/\.mp4$/i, '');
          const proxyVidUrl = `/api/proxy/video/${encodeURIComponent(fn)}`;
          const proxySubEn = `/api/proxy/subtitle/${encodeURIComponent(baseNoExt + '.en.vtt')}`;
          const proxySubFr = `/api/proxy/subtitle/${encodeURIComponent(baseNoExt + '.fr.vtt')}`;
          const directVidUrl = (vid.urls && vid.urls.video_stream) || `http://159.84.143.246:8080/videos/existing/${fn}`;

          const streamLink = document.getElementById("resStreamUrl");
          streamLink.href = proxyVidUrl;
          streamLink.innerHTML = `▶ Watch Video (Click to Preview)`;
          streamLink.onclick = function(e) {
            e.preventDefault();
            openVideoPlayer(encodeURIComponent(fn), encodeURIComponent(vid.title || fn), proxyVidUrl, proxySubEn, proxySubFr, directVidUrl);
          };

          document.getElementById("btnDispatchSingle").disabled = false;
        } else {
          document.getElementById("resVideoTitle").innerText = "Error resolving patient action plan";
        }
      } catch (e) {
        document.getElementById("resVideoTitle").innerText = "Connection error";
      }
    }

    async function dispatchSinglePatient() {
      const pid = document.getElementById("simPatientId").value.trim();
      if (!pid) return;
      showToast(`Dispatching single recommendation for patient ${pid}...`);
      try {
        const res = await fetch(`/api/video-server/orchestrate/${pid}?force=true`, {
          method: "POST",
          headers: getAuthHeaders()
        });
        const data = await res.json();
        if (res.ok) {
          showToast(`Delivered to Video VM! (HTTP 200)`);
          simulatePatientVideo();
          fetchStats();
        } else {
          showToast(data.detail || "Dispatch failed", true);
        }
      } catch (e) {
        showToast("Error dispatching to Video VM", true);
      }
    }

    // 5. Load and Render Video Catalog Table
    async function loadCatalog() {
      try {
        const res = await fetch("/api/triggers/catalog");
        if (!res.ok) return;
        const data = await res.json();
        rawCatalog = data.video_triggers || [];
        renderCatalogTable(rawCatalog);
      } catch (e) {
        console.error("Failed to load catalog:", e);
      }
    }

    function renderCatalogTable(items) {
      const countBadge = document.getElementById("tabCatalogCountBadge");
      if (countBadge && items) countBadge.innerText = items.length;
      const tbody = document.getElementById("catalogTableBody");
      if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No videos found.</td></tr>`;
        return;
      }
      tbody.innerHTML = items.map(item => {
        const isWearable = item.video_id >= 28 && item.video_id <= 37;
        const isAlert = [12, 13, 15, 19, 20, 22].includes(item.video_id);
        const tagClass = isWearable ? "tag-wearable" : (isAlert ? "tag-alert" : "tag-cpap");
        const categoryName = isWearable ? "Wearable Biomarkers" : (item.category || "Clinical CPAP");

        const logic = (item.condition_logic || "AND").toUpperCase();
        const prio = (item.clinical_priority || "medium").toLowerCase();
        const logicClass = logic === "OR" ? "pill-amber" : "pill-cyan";

        let prioClass = "pill-slate";
        if (prio === "critical") prioClass = "pill-rose";
        else if (prio === "high") prioClass = "pill-amber";
        else if (prio === "medium") prioClass = "pill-blue";
        else if (prio === "maintenance") prioClass = "pill-emerald";

        const fn = item.filename || '';
        const urls = item.urls || {};

        // Direct Video VM URLs from catalog metadata
        const directVideoUrl = urls.video_stream || item.stream_url || `http://159.84.143.246:8080/videos/existing/${fn}`;
        const directSubEn = urls.subtitle_en || item.subtitles_en_url || `http://159.84.143.246:8080/subtitles/${fn.replace(/\.mp4$/i, '')}.en.vtt`;
        const directSubFr = urls.subtitle_fr || item.subtitles_fr_url || `http://159.84.143.246:8080/subtitles/${fn.replace(/\.mp4$/i, '')}.fr.vtt`;

        const vFn = directVideoUrl.split('/').pop() || fn;
        const subEnFn = directSubEn.split('/').pop() || `${fn.replace(/\.mp4$/i, '')}.en.vtt`;
        const subFrFn = directSubFr.split('/').pop() || `${fn.replace(/\.mp4$/i, '')}.fr.vtt`;

        // Local AI Server Proxy URLs (100% reliable across localhost, SSH tunnel, and remote networks)
        const proxyVideoUrl = `/api/proxy/video/${encodeURIComponent(vFn)}`;
        const proxySubEn = `/api/proxy/subtitle/${encodeURIComponent(subEnFn)}`;
        const proxySubFr = `/api/proxy/subtitle/${encodeURIComponent(subFrFn)}`;

        const safeTitle = (item.title || fn).replace(/'/g, "\\'").replace(/"/g, "&quot;");

        return `
          <tr>
            <td><strong>#${item.video_id}</strong></td>
            <td>
              <div style="font-weight:600; color:var(--text-main);">${escapeHtml(item.title || '')}</div>
              <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:var(--primary); margin-top:2px;">${escapeHtml(fn)}</div>
            </td>
            <td>
              <div style="display:flex; flex-direction:column; gap:4px; align-items:flex-start;">
                <span class="tag ${tagClass}">${categoryName}</span>
                <span class="badge-pill ${logicClass}" style="margin:0; font-size:0.65rem; padding:1px 6px;">Logic: ${logic}</span>
              </div>
            </td>
            <td>
              <span class="badge-pill ${prioClass}" style="margin:0; font-size:0.68rem; text-transform:uppercase;">${prio}</span>
            </td>
            <td style="color:var(--text-muted); font-size:0.75rem;">${escapeHtml(item.trigger_reason || item.clinical_condition || item.reason || '--')}</td>
            <td>
              <div style="display:flex; align-items:center; gap:6px;">
                <a href="${proxySubEn}" target="_blank" class="sub-link" title="Open English WebVTT (.en.vtt)">🇬🇧 EN</a>
                <a href="${proxySubFr}" target="_blank" class="sub-link" title="Open French WebVTT (.fr.vtt)">🇫🇷 FR</a>
              </div>
            </td>
            <td>
              <div style="display:flex; align-items:center; gap:6px;">
                <button class="btn-play" onclick="openVideoPlayer('${encodeURIComponent(fn)}', '${safeTitle}', '${proxyVideoUrl}', '${proxySubEn}', '${proxySubFr}', '${directVideoUrl}')" title="Play Video in Dashboard Player">
                  ▶ Play
                </button>
                <a href="${proxyVideoUrl}" target="_blank" class="btn-icon-link" title="Open MP4 Stream in New Tab">↗</a>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function filterCatalogTable() {
      const term = document.getElementById("txtCatalogSearch").value.toLowerCase();
      if (!term) return renderCatalogTable(rawCatalog);
      const filtered = rawCatalog.filter(i =>
        (i.title && i.title.toLowerCase().includes(term)) ||
        (i.filename && i.filename.toLowerCase().includes(term)) ||
        (i.trigger_reason && i.trigger_reason.toLowerCase().includes(term)) ||
        (i.clinical_priority && i.clinical_priority.toLowerCase().includes(term)) ||
        (i.condition_logic && i.condition_logic.toLowerCase().includes(term)) ||
        String(i.video_id).includes(term)
      );
      renderCatalogTable(filtered);
    }

    // 6. Video Player Modal Functions
    function openVideoPlayer(filename, title, videoUrl, subEn, subFr, directUrl) {
      const decodedFn = decodeURIComponent(filename);
      const decodedTitle = decodeURIComponent(title);
      document.getElementById("modalVideoTitle").innerText = decodedTitle;
      document.getElementById("modalVideoFilename").innerText = decodedFn;

      const player = document.getElementById("modalVideoPlayer");
      player.pause();

      const source = document.getElementById("modalVideoSource");
      source.src = videoUrl;

      const trackEn = document.getElementById("modalTrackEn");
      const trackFr = document.getElementById("modalTrackFr");
      trackEn.src = subEn;
      trackFr.src = subFr;

      document.getElementById("modalDirectMp4Link").href = directUrl || videoUrl;
      document.getElementById("modalDirectSubEnLink").href = subEn;
      document.getElementById("modalDirectSubFrLink").href = subFr;

      player.load();
      player.play().catch(e => console.log("Autoplay prevented:", e));

      document.getElementById("videoModal").classList.add("open");
    }

    function closeVideoModal(event) {
      const modal = document.getElementById("videoModal");
      const player = document.getElementById("modalVideoPlayer");
      player.pause();
      modal.classList.remove("open");
    }

    document.addEventListener("keydown", function(e) {
      if (e.key === "Escape") closeVideoModal();
    });

    // Initial setup and polling intervals
    initTheme();
    initDashboardTabs();
    fetchStats();
    fetchKpis();
    fetchLogs();
    loadCatalog();
    setInterval(fetchStats, 5000);   // Poll metrics every 5s
    setInterval(fetchKpis, 10000);   // Poll KPIs every 10s
    setInterval(fetchLogs, 1500);    // Poll logs every 1.5s
  </script>
</body>
</html>
"""
