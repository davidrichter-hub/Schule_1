from flask import Flask, jsonify
from ping3 import ping
import time
import psycopg2
import psutil
import platform
import subprocess
import re

app = Flask(__name__)

# ── Config──────────────────────────────────────────────────────────────

HOSTS = {
    "frankfurt": {
        "ip":    "10.211.32.121",
        "label": "Frankfurt",
        "short": "FRA",
        "lat":   50.1109,
        "lon":   8.6821,
        "role":  "Primary Node",
    },
    "wien": {
        "ip":    "10.211.32.56",
        "label": "Wien",
        "short": "VIE",
        "lat":   48.2082,
        "lon":   16.3738,
        "role":  "Secondary Node",
    },
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def ping_host(host: str) -> dict:
    try:
        result = ping(host, timeout=2, unit="ms")
        if result is None or result is False:
            return {"online": False, "latency_ms": None}
        return {"online": True, "latency_ms": round(float(result), 2)}
    except Exception:
        return {"online": False, "latency_ms": None}


def get_cpu_name() -> str:
    """CPU-Modellname auslesen – funktioniert auf Linux, macOS und Windows."""
    system = platform.system()
    try:
        if system == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            return name.strip()
        elif system == "Darwin":
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            return out or platform.processor()
        else:  # Linux
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
            return platform.processor() or "Unknown CPU"
    except Exception:
        return platform.processor() or "Unknown CPU"


def get_sysinfo() -> dict:
    """RAM, Speicher und CPU-Info des lokalen Hosts auslesen."""
    # RAM
    ram = psutil.virtual_memory()
    ram_total_gb = round(ram.total / (1024 ** 3), 1)
    ram_used_gb  = round(ram.used  / (1024 ** 3), 1)
    ram_percent  = ram.percent

    # Primäre Disk (Root / C:)
    disk = psutil.disk_usage("/")
    disk_total_gb = round(disk.total / (1024 ** 3), 1)
    disk_used_gb  = round(disk.used  / (1024 ** 3), 1)
    disk_percent  = disk.percent

    # CPU
    cpu_name    = get_cpu_name()
    cpu_percent = psutil.cpu_percent(interval=0.3)
    cpu_cores   = psutil.cpu_count(logical=False)
    cpu_threads = psutil.cpu_count(logical=True)

    return {
        "ram_total_gb":  ram_total_gb,
        "ram_used_gb":   ram_used_gb,
        "ram_percent":   ram_percent,
        "disk_total_gb": disk_total_gb,
        "disk_used_gb":  disk_used_gb,
        "disk_percent":  disk_percent,
        "cpu_name":      cpu_name,
        "cpu_percent":   cpu_percent,
        "cpu_cores":     cpu_cores,
        "cpu_threads":   cpu_threads,
    }

def saveSysInfoToDb(sysinfo):
    print(sysinfo["cpu_cores"])
    con=psycopg2.connect("host='localhost' dbname='postgres' user='postgres' password='00000'")
    print("TEST")
    concursor=con.cursor()
   # concursor.execute("INSERT INTO Resourcen (ram_total_gb) VALUES ('test');")
    concursor.execute(f"INSERT INTO Resourcen (ram_total_gb, ram_used_gb, ram_percent, disk_total_gb, disk_used_gb, disk_percent, cpu_name, cpu_percent, cpu_cores, cpu_threads) VALUES ('{sysinfo["ram_total_gb"]}','{sysinfo["ram_used_gb"]}','{sysinfo["ram_percent"]}','{sysinfo["disk_total_gb"]}','{sysinfo["disk_used_gb"]}','{sysinfo["disk_percent"]}','{sysinfo["cpu_name"]}','{sysinfo["cpu_percent"]}','{sysinfo["cpu_cores"]}','{sysinfo["cpu_threads"]}');")
    con.commit()



# ── API ────────────────────────────────────────────────────────────────────────



@app.route("/status")
def status():
    sysinfo = get_sysinfo()
    
    saveSysInfoToDb(sysinfo)



    result = {}
    for key, cfg in HOSTS.items():
        ping_result = ping_host(cfg["ip"])
        result[key] = {
            **ping_result,
            **cfg,
            **sysinfo,          # gleiche Live-Daten für beide Shortcuts
            "checked_at": time.time(),
        }
    return jsonify(result)


@app.route("/sysinfo")
def sysinfo_route():
    return jsonify(get_sysinfo())


# ── Frontend ───────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>TEAM WIEN MONITOR</title>

  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet"/>

  <style>
    :root {
      --c-bg:          #05070d;
      --c-bg-2:        #080b14;
      --c-surface:     #0c1018;
      --c-surface-2:   #111620;
      --c-surface-3:   #161c28;
      --c-border:      rgba(255,255,255,0.06);
      --c-border-2:    rgba(255,255,255,0.10);
      --c-text:        #e2e8f5;
      --c-text-2:      #7d8fa8;
      --c-text-3:      #3d4f68;
      --c-accent:      #3b82f6;
      --c-accent-glow: rgba(59,130,246,0.35);
      --c-green:       #10b981;
      --c-green-bg:    rgba(16,185,129,0.10);
      --c-green-bdr:   rgba(16,185,129,0.25);
      --c-red:         #ef4444;
      --c-red-bg:      rgba(239,68,68,0.10);
      --c-red-bdr:     rgba(239,68,68,0.25);
      --c-amber:       #f59e0b;
      --c-amber-bg:    rgba(245,158,11,0.10);
      --c-blue:        #3b82f6;
      --c-blue-bg:     rgba(59,130,246,0.10);
      --f-ui:   'Space Grotesk', sans-serif;
      --f-mono: 'JetBrains Mono', monospace;
      --r-sm: 6px; --r-md: 10px; --r-lg: 14px;
      --sidebar-w: 340px;
      --header-h: 56px;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; overflow: hidden; background: var(--c-bg); color: var(--c-text); font-family: var(--f-ui); font-size: 14px; -webkit-font-smoothing: antialiased; }

    ::-webkit-scrollbar       { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--c-surface-3); border-radius: 2px; }

    #app {
      display: grid;
      grid-template-columns: var(--sidebar-w) 1fr;
      grid-template-rows: var(--header-h) 1fr;
      height: 100vh;
    }


    #header {
      grid-column: 1 / -1;
      background: var(--c-surface);
      border-bottom: 1px solid var(--c-border);
      display: flex;
      align-items: center;
      padding: 0 20px;
      gap: 14px;
      position: relative;
      z-index: 1001;
    }

    .logo { display: flex; align-items: center; gap: 10px; }
    .logo-icon {
      width: 30px; height: 30px;
      background: var(--c-accent);
      border-radius: 7px;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 0 16px var(--c-accent-glow);
    }
    .logo-icon svg { width: 16px; height: 16px; }
    .logo-wordmark { font-size: 15px; font-weight: 700; letter-spacing: 0.12em; color: #fff; text-transform: uppercase; }
    .logo-wordmark span { color: var(--c-accent); }
    .header-sep { width: 1px; height: 22px; background: var(--c-border-2); margin: 0 2px; }
    .header-breadcrumb { font-size: 11px; color: var(--c-text-2); font-family: var(--f-mono); }
    .header-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }

    .header-pill {
      display: flex; align-items: center; gap: 6px;
      padding: 5px 12px; border-radius: 20px;
      font-size: 11px; font-family: var(--f-mono); font-weight: 500; letter-spacing: 0.05em;
      transition: all 0.4s ease; border: 1px solid transparent;
    }
    .pill-green { background: var(--c-green-bg);  color: var(--c-green); border-color: var(--c-green-bdr); }
    .pill-red   { background: var(--c-red-bg);    color: var(--c-red);   border-color: var(--c-red-bdr);   }
    .pill-amber { background: var(--c-amber-bg);  color: var(--c-amber); border-color: rgba(245,158,11,.25); }
    .pill-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
    .pill-dot.pulse { animation: dot-pulse 2s infinite; }

    @keyframes dot-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.75)} }

    .header-time { font-size: 11px; font-family: var(--f-mono); color: var(--c-text-3); }
    .icon-btn {
      width: 28px; height: 28px; border-radius: var(--r-sm);
      background: var(--c-surface-2); border: 1px solid var(--c-border-2);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: background 0.2s;
    }
    .icon-btn:hover { background: var(--c-surface-3); }
    .icon-btn svg { width: 13px; height: 13px; stroke: var(--c-text-2); fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .icon-btn.spin svg { animation: spin 0.6s linear; }
    @keyframes spin { to { transform: rotate(360deg); } }


    #sidebar {
      background: var(--c-surface);
      border-right: 1px solid var(--c-border);
      display: flex; flex-direction: column;
      overflow: hidden;
    }
    .section-label {
      padding: 16px 16px 8px;
      font-size: 10px; font-weight: 600; letter-spacing: 0.14em;
      text-transform: uppercase; color: var(--c-text-3);
    }

    #stats-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 0 16px 14px; }
    .stat-box {
      background: var(--c-bg-2); border: 1px solid var(--c-border);
      border-radius: var(--r-md); padding: 12px 14px;
    }
    .stat-label { font-size: 10px; color: var(--c-text-3); margin-bottom: 5px; letter-spacing: 0.08em; text-transform: uppercase; }
    .stat-value { font-size: 24px; font-weight: 700; color: #fff; line-height: 1; }
    .stat-value small { font-size: 12px; color: var(--c-text-2); font-weight: 400; margin-left: 2px; }

    .divider { height: 1px; background: var(--c-border); margin: 0 16px; }

    #server-list { flex: 1; overflow-y: auto; padding: 0 16px 16px; display: flex; flex-direction: column; gap: 8px; }


    .server-card {
      background: var(--c-bg-2); border: 1px solid var(--c-border);
      border-radius: var(--r-lg); cursor: pointer;
      transition: border-color 0.2s, transform 0.15s, box-shadow 0.2s;
      overflow: hidden; position: relative;
    }
    .server-card:hover { border-color: rgba(59,130,246,0.3); transform: translateY(-1px); box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
    .server-card:active { transform: translateY(0); }
    .card-accent-bar { height: 3px; background: var(--c-text-3); transition: background 0.4s ease; }
    .server-card.online  .card-accent-bar { background: var(--c-green); box-shadow: 0 0 8px var(--c-green); }
    .server-card.offline .card-accent-bar { background: var(--c-red); }
    .card-body { padding: 14px 14px 12px; }
    .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
    .card-node { display: flex; align-items: center; gap: 10px; }
    .node-badge {
      width: 40px; height: 40px; border-radius: var(--r-sm);
      display: flex; align-items: center; justify-content: center;
      font-family: var(--f-mono); font-size: 11px; font-weight: 700;
      letter-spacing: 0.04em; flex-shrink: 0; transition: all 0.3s;
    }
    .server-card.online  .node-badge { background: var(--c-green-bg); color: var(--c-green); border: 1px solid var(--c-green-bdr); }
    .server-card.offline .node-badge { background: var(--c-red-bg);   color: var(--c-red);   border: 1px solid var(--c-red-bdr); }
    .server-card.loading .node-badge { background: var(--c-surface-3);color: var(--c-text-3);border: 1px solid var(--c-border); }
    .node-name { font-size: 15px; font-weight: 600; color: #fff; line-height: 1.2; }
    .node-role { font-size: 11px; color: var(--c-text-2); margin-top: 2px; }
    .status-chip {
      font-family: var(--f-mono); font-size: 10px; font-weight: 500;
      padding: 3px 9px; border-radius: 20px; letter-spacing: 0.06em;
      display: flex; align-items: center; gap: 5px; flex-shrink: 0;
      border: 1px solid transparent;
    }
    .chip-online  { background: var(--c-green-bg); color: var(--c-green); border-color: var(--c-green-bdr); }
    .chip-offline { background: var(--c-red-bg);   color: var(--c-red);   border-color: var(--c-red-bdr); }
    .chip-loading { background: var(--c-surface-3);color: var(--c-text-3);border: 1px solid var(--c-border); }
    .chip-led { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
    .chip-led.blink { animation: dot-pulse 1.5s infinite; }


    .card-metrics { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 10px; }
    .metric {
      background: var(--c-surface-2); border: 1px solid var(--c-border);
      border-radius: var(--r-sm); padding: 8px 10px;
    }
    .metric-k { font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--c-text-3); margin-bottom: 3px; }
    .metric-v { font-family: var(--f-mono); font-size: 12px; font-weight: 500; color: var(--c-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .metric-v.green { color: var(--c-green); }
    .metric-v.red   { color: var(--c-red); }
    .metric-v.amber { color: var(--c-amber); }


    .bar-section { margin-bottom: 8px; }
    .bar-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .bar-label { font-size: 10px; color: var(--c-text-3); display: flex; align-items: center; gap: 5px; }
    .bar-label-icon { font-size: 9px; }
    .bar-value { font-family: var(--f-mono); font-size: 10px; font-weight: 500; }
    .bar-value.good   { color: var(--c-green); }
    .bar-value.medium { color: var(--c-amber); }
    .bar-value.bad    { color: var(--c-red); }
    .bar-value.none   { color: var(--c-text-3); }
    .bar-track { height: 4px; background: var(--c-surface-3); border-radius: 2px; overflow: hidden; margin-bottom: 7px; }
    .bar-fill  { height: 100%; border-radius: 2px; transition: width 0.7s cubic-bezier(0.25,1,0.5,1), background 0.3s; }


    .cpu-name-row {
      display: flex; align-items: center; gap: 6px;
      background: var(--c-surface-2); border: 1px solid var(--c-border);
      border-radius: var(--r-sm); padding: 7px 10px; margin-bottom: 8px;
    }
    .cpu-icon { font-size: 11px; }
    .cpu-name-text { font-family: var(--f-mono); font-size: 10px; color: var(--c-text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }


    .lat-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .lat-label { font-size: 10px; color: var(--c-text-3); }
    .lat-value { font-family: var(--f-mono); font-size: 11px; font-weight: 500; }
    .lat-value.good   { color: var(--c-green); }
    .lat-value.medium { color: var(--c-amber); }
    .lat-value.bad    { color: var(--c-red); }
    .lat-value.none   { color: var(--c-text-3); }
    .lat-track { height: 3px; background: var(--c-surface-3); border-radius: 2px; overflow: hidden; }
    .lat-fill  { height: 100%; border-radius: 2px; transition: width 0.7s cubic-bezier(0.25,1,0.5,1), background 0.3s; }

    #sidebar-footer {
      border-top: 1px solid var(--c-border); padding: 10px 16px;
      display: flex; justify-content: space-between; align-items: center;
    }
    .footer-item { display: flex; align-items: center; gap: 6px; font-size: 10px; font-family: var(--f-mono); color: var(--c-text-3); }
    .footer-dot  { width: 5px; height: 5px; border-radius: 50%; background: var(--c-text-3); transition: background 0.3s; }
    .footer-dot.live { background: var(--c-green); animation: dot-pulse 2s infinite; }

    #map-wrap { position: relative; overflow: hidden; }
    #map      { width: 100%; height: 100%; }

    .map-overlay {
      position: absolute; top: 14px; right: 14px; z-index: 800;
      background: rgba(8,11,20,0.85); backdrop-filter: blur(14px);
      border: 1px solid rgba(255,255,255,0.1); border-radius: var(--r-md);
      padding: 12px 14px; font-family: var(--f-mono); font-size: 10px;
      color: var(--c-text-2); line-height: 1.8; min-width: 160px;
      pointer-events: none;
    }
    .map-overlay-title { font-size: 9px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--c-text-3); margin-bottom: 7px; }
    .overlay-row  { display: flex; justify-content: space-between; gap: 12px; }
    .overlay-key  { color: var(--c-text-3); }
    .overlay-val  { color: var(--c-text); font-weight: 500; }

    
    .marker-outer { position: relative; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; }
    .marker-dot {
      width: 14px; height: 14px; border-radius: 50%;
      border: 2px solid rgba(255,255,255,0.45);
      position: relative; z-index: 2; transition: all 0.4s ease;
    }
    .marker-ring {
      position: absolute; width: 34px; height: 34px; border-radius: 50%;
      top: -10px; left: -10px; border: 1.5px solid transparent;
      opacity: 0; pointer-events: none; z-index: 1;
    }
    .marker-dot.online  { background: var(--c-green); box-shadow: 0 0 10px var(--c-green); }
    .marker-dot.offline { background: var(--c-red);   box-shadow: 0 0 10px var(--c-red); }
    .marker-ring.online { border-color: var(--c-green); animation: ring 2.5s ease-out infinite; }
    @keyframes ring { 0%{transform:scale(.6);opacity:.8} 70%{transform:scale(1.6);opacity:0} 100%{opacity:0} }

    
    .leaflet-popup-content-wrapper {
      background: rgba(5,7,13,0.93) !important;
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255,255,255,0.11) !important;
      border-radius: 10px !important;
      box-shadow: 0 16px 48px rgba(0,0,0,0.7) !important;
      color: var(--c-text) !important;
    }
    .leaflet-popup-tip-container { display: none; }
    .leaflet-popup-content { margin: 0 !important; font-family: var(--f-ui) !important; }
    .leaflet-container a.leaflet-popup-close-button { color: var(--c-text-3) !important; top: 8px !important; right: 8px !important; font-size: 18px !important; }

    .popup-inner { padding: 16px 18px 14px; min-width: 230px; }
    .popup-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
    .popup-city { font-size: 16px; font-weight: 700; color: #fff; }
    .popup-role { font-size: 10px; color: var(--c-text-2); margin-top: 2px; font-family: var(--f-mono); }
    .popup-badge {
      font-family: var(--f-mono); font-size: 10px; font-weight: 500;
      padding: 3px 9px; border-radius: 20px;
      display: flex; align-items: center; gap: 5px;
      border: 1px solid transparent;
    }
    .popup-badge.online  { background: var(--c-green-bg); color: var(--c-green); border-color: var(--c-green-bdr); }
    .popup-badge.offline { background: var(--c-red-bg);   color: var(--c-red);   border-color: var(--c-red-bdr); }
    .popup-divider { height: 1px; background: rgba(255,255,255,0.07); margin-bottom: 10px; }
    .popup-row { display: flex; justify-content: space-between; margin-bottom: 5px; }
    .popup-key { font-family: var(--f-mono); font-size: 10px; color: var(--c-text-3); }
    .popup-val { font-family: var(--f-mono); font-size: 10px; color: var(--c-text); font-weight: 500; }
    .popup-bar-row { margin-bottom: 7px; }
    .popup-bar-top { display: flex; justify-content: space-between; margin-bottom: 3px; }
    .popup-bar-label { font-family: var(--f-mono); font-size: 9px; color: var(--c-text-3); }
    .popup-bar-val   { font-family: var(--f-mono); font-size: 9px; font-weight: 600; }
    .popup-track { height: 3px; background: rgba(255,255,255,0.07); border-radius: 2px; overflow: hidden; }
    .popup-fill  { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

   
    @media (max-width: 700px) {
      #app { grid-template-columns: 1fr; grid-template-rows: var(--header-h) 50vh 1fr; }
      #sidebar { border-right: none; border-bottom: 1px solid var(--c-border); }
      :root { --sidebar-w: 100%; }
    }
  </style>
</head>

<body>
<div id="app">

  <header id="header">
    <div class="logo">
      <div class="logo-icon">
        <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="8" cy="8" r="2.5" fill="white"/>
          <line x1="8" y1="1" x2="8" y2="3"   stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="8" y1="13" x2="8" y2="15"  stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="1" y1="8" x2="3" y2="8"    stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="13" y1="8" x2="15" y2="8"  stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="3.4" y1="3.4" x2="4.8" y2="4.8"  stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="11.2" y1="11.2" x2="12.6" y2="12.6" stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="11.2" y1="4.8" x2="12.6" y2="3.4"  stroke="white" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="3.4" y1="12.6" x2="4.8" y2="11.2"  stroke="white" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </div>
      <span class="logo-wordmark">TEAM<span>WIEN</span></span>
    </div>

    <div class="header-sep"></div>
    <span class="header-breadcrumb"> </span>

    <div class="header-right">
      <div id="global-pill" class="header-pill pill-amber">
        <span class="pill-dot" id="pill-dot"></span>
        <span id="pill-text">Connecting…</span>
      </div>
      <span class="header-time" id="clock">00:00:00</span>
      <div class="icon-btn" id="btn-refresh" title="Refresh" onclick="fetchStatus()">
        <svg viewBox="0 0 16 16"><polyline points="1 4 1 10 7 10"/><path d="M1 10A7 7 0 1 0 3.1 4.5"/></svg>
      </div>
    </div>
  </header>

  <aside id="sidebar">
    <div class="section-label">Overview</div>
    <div id="stats-row">
      <div class="stat-box">
        <div class="stat-label">Online</div>
        <div class="stat-value" id="stat-online">–</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Avg Latency</div>
        <div class="stat-value" id="stat-latency">–</div>
      </div>
    </div>

    <div class="divider"></div>
    <div class="section-label">Shortcuts</div>
    <div id="server-list"></div>

    <div id="sidebar-footer">
      <div class="footer-item">
        <span class="footer-dot" id="live-dot"></span>
        <span id="last-update">–</span>
      </div>
      <div class="footer-item">Auto 5s</div>
    </div>
  </aside>

  <!-- MAP -->
  <div id="map-wrap">
    <div id="map"></div>
    <div class="map-overlay">
      <div class="map-overlay-title">Region Info</div>
      <div class="overlay-row"><span class="overlay-key">Continent</span><span class="overlay-val">Europe</span></div>
      <div class="overlay-row"><span class="overlay-key">Nodes</span><span class="overlay-val" id="overlay-nodes">–</span></div>
      <div class="overlay-row"><span class="overlay-key">Provider</span><span class="overlay-val">Private</span></div>
    </div>
  </div>

</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const state   = {};
const markers = {};

// Clock
function tick() {
  const t = new Date();
  document.getElementById('clock').textContent =
    t.toLocaleTimeString('de-AT', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
setInterval(tick, 1000); tick();

// Map
const map = L.map('map', {
  minZoom:3, maxZoom:13,
  maxBounds:[[-85,-180],[85,180]],
  maxBoundsViscosity:1,
  zoomControl:false,
}).setView([49.5, 12.5], 5);
L.control.zoom({ position:'bottomright' }).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution:'&copy; OpenStreetMap &copy; CARTO', subdomains:'abcd', maxZoom:20
}).addTo(map);

// Helpers
const latClass  = ms => !ms && ms !== 0 ? 'none' : ms < 30 ? 'good' : ms < 100 ? 'medium' : 'bad';
const latPct    = ms => ms ? Math.min(100, (ms/150)*100) : 0;
const latColor  = c  => ({good:'var(--c-green)',medium:'var(--c-amber)',bad:'var(--c-red)',none:'var(--c-text-3)'}[c]);
const usageClass= p  => p == null ? 'none' : p < 60 ? 'good' : p < 85 ? 'medium' : 'bad';
const usageColor= c  => ({good:'var(--c-green)',medium:'var(--c-amber)',bad:'var(--c-red)',none:'var(--c-text-3)'}[c]);
const timeAgo   = ts => { const d=Math.round(Date.now()/1000-ts); return d<3?'just now':d<60?`${d}s ago`:`${Math.round(d/60)}min ago`; };

function shortCpuName(name) {
  if (!name) return '—';
  // Shorten long CPU names for cards
  return name
    .replace(/\(R\)/gi,'').replace(/\(TM\)/gi,'')
    .replace(/CPU/gi,'').replace(/Processor/gi,'')
    .replace(/\s+/g,' ').trim();
}

// Cards
function renderCards(data) {
  const list = document.getElementById('server-list');
  list.innerHTML = '';
  for (const [key, s] of Object.entries(data)) {
    const cls  = s.online ? 'online' : 'offline';
    const ms   = s.latency_ms;
    const lc   = latClass(ms);

    const ramPct  = s.ram_percent  ?? null;
    const diskPct = s.disk_percent ?? null;
    const cpuPct  = s.cpu_percent  ?? null;

    const ramRc  = usageClass(ramPct);
    const diskRc = usageClass(diskPct);
    const cpuRc  = usageClass(cpuPct);

    const ramLabel  = s.ram_used_gb  != null ? `${s.ram_used_gb} / ${s.ram_total_gb} GB` : '—';
    const diskLabel = s.disk_used_gb != null ? `${s.disk_used_gb} / ${s.disk_total_gb} GB` : '—';
    const cpuLabel  = cpuPct != null ? `${cpuPct}%` : '—';

    const card = document.createElement('div');
    card.className = `server-card ${cls}`;
    card.innerHTML = `
      <div class="card-accent-bar"></div>
      <div class="card-body">
        <div class="card-top">
          <div class="card-node">
            <div class="node-badge">${s.short}</div>
            <div>
              <div class="node-name">${s.label}</div>
              <div class="node-role">${s.role}</div>
            </div>
          </div>
          <div class="status-chip ${s.online?'chip-online':'chip-offline'}">
            <span class="chip-led${s.online?' blink':''}"></span>
            ${s.online?'Online':'Offline'}
          </div>
        </div>

        ${s.cpu_name ? `
        <div class="cpu-name-row">
          <span class="cpu-icon">⚙</span>
          <span class="cpu-name-text">${shortCpuName(s.cpu_name)}</span>
        </div>` : ''}

        <div class="bar-section">
          <div class="bar-row">
            <span class="bar-label">RAM</span>
            <span class="bar-value ${ramRc}">${ramLabel}${ramPct!=null?' ('+ramPct+'%)':''}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${ramPct??0}%;background:${usageColor(ramRc)}"></div></div>

          <div class="bar-row">
            <span class="bar-label">Disk</span>
            <span class="bar-value ${diskRc}">${diskLabel}${diskPct!=null?' ('+diskPct+'%)':''}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${diskPct??0}%;background:${usageColor(diskRc)}"></div></div>

          <div class="bar-row">
            <span class="bar-label">CPU Load</span>
            <span class="bar-value ${cpuRc}">${cpuLabel}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${cpuPct??0}%;background:${usageColor(cpuRc)}"></div></div>
        </div>

        <div class="lat-row">
          <span class="lat-label">Latency</span>
          <span class="lat-value ${lc}">${ms!=null?ms+' ms':'—'}</span>
        </div>
        <div class="lat-track"><div class="lat-fill" style="width:${latPct(ms)}%;background:${latColor(lc)}"></div></div>
      </div>`;
    card.addEventListener('click', () => { const m=markers[key]; if(m){map.flyTo(m.getLatLng(),9,{duration:1.2});m.openPopup();} });
    list.appendChild(card);
  }
}

// Markers
function ensureMarker(key, s) {
  if (markers[key]) return;
  const icon = L.divIcon({
    className:'',
    html:`<div class="marker-outer"><div id="mring-${key}" class="marker-ring"></div><div id="mdot-${key}" class="marker-dot"></div></div>`,
    iconSize:[20,20], iconAnchor:[10,10]
  });
  const m = L.marker([s.lat, s.lon], {icon}).addTo(map);
  m.bindPopup('', {offset:[0,-8], minWidth:230});
  markers[key] = m;
}

function barColor(pct) {
  if (pct == null) return 'var(--c-text-3)';
  if (pct < 60)   return 'var(--c-green)';
  if (pct < 85)   return 'var(--c-amber)';
  return 'var(--c-red)';
}

function updateMarker(key, s) {
  ensureMarker(key, s);
  const dot  = document.getElementById(`mdot-${key}`);
  const ring = document.getElementById(`mring-${key}`);
  if (!dot) return;
  dot.className  = `marker-dot  ${s.online?'online':'offline'}`;
  ring.className = `marker-ring ${s.online?'online':'offline'}`;
  const ms = s.latency_ms;

  const popupBar = (label, used, total, pct) => pct == null ? '' : `
    <div class="popup-bar-row">
      <div class="popup-bar-top">
        <span class="popup-bar-label">${label}</span>
        <span class="popup-bar-val" style="color:${barColor(pct)}">${used} / ${total} GB (${pct}%)</span>
      </div>
      <div class="popup-track"><div class="popup-fill" style="width:${pct}%;background:${barColor(pct)}"></div></div>
    </div>`;

  markers[key].setPopupContent(`
    <div class="popup-inner">
      <div class="popup-header">
        <div><div class="popup-city">${s.label}</div><div class="popup-role">${s.role}</div></div>
        <div class="popup-badge ${s.online?'online':'offline'}">
          <span class="chip-led${s.online?' blink':''}"></span>${s.online?'Online':'Offline'}
        </div>
      </div>
      <div class="popup-divider"></div>
      <div class="popup-row"><span class="popup-key">HOST</span><span class="popup-val">${s.ip}</span></div>
      <div class="popup-row"><span class="popup-key">LATENCY</span><span class="popup-val">${ms!=null?ms+' ms':'—'}</span></div>
      ${s.cpu_name ? `<div class="popup-row"><span class="popup-key">CPU</span><span class="popup-val" style="max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${shortCpuName(s.cpu_name)}</span></div>` : ''}
      ${s.cpu_cores ? `<div class="popup-row"><span class="popup-key">CORES</span><span class="popup-val">${s.cpu_cores}c / ${s.cpu_threads}t</span></div>` : ''}
      <div class="popup-divider"></div>
      ${popupBar('RAM',  s.ram_used_gb,  s.ram_total_gb,  s.ram_percent)}
      ${popupBar('DISK', s.disk_used_gb, s.disk_total_gb, s.disk_percent)}
      ${s.cpu_percent != null ? `
      <div class="popup-bar-row">
        <div class="popup-bar-top">
          <span class="popup-bar-label">CPU LOAD</span>
          <span class="popup-bar-val" style="color:${barColor(s.cpu_percent)}">${s.cpu_percent}%</span>
        </div>
        <div class="popup-track"><div class="popup-fill" style="width:${s.cpu_percent}%;background:${barColor(s.cpu_percent)}"></div></div>
      </div>` : ''}
    </div>`);
}

// Header
function updatePill(data) {
  const vals   = Object.values(data);
  const on     = vals.filter(s=>s.online).length;
  const total  = vals.length;
  const pill   = document.getElementById('global-pill');
  const dot    = document.getElementById('pill-dot');
  const txt    = document.getElementById('pill-text');
  pill.className = 'header-pill ' + (on===total?'pill-green':on===0?'pill-red':'pill-amber');
  dot.className  = 'pill-dot' + (on>0?' pulse':'');
  txt.textContent = on===total ? 'All Systems Operational' : on===0 ? 'All Systems Down' : `Partial Outage (${on}/${total})`;
}

// Stats
function updateStats(data) {
  const vals = Object.values(data);
  const on   = vals.filter(s=>s.online).length;
  const lats = vals.filter(s=>s.online&&s.latency_ms!=null).map(s=>s.latency_ms);
  const avg  = lats.length ? Math.round(lats.reduce((a,b)=>a+b,0)/lats.length) : null;
  document.getElementById('stat-online').innerHTML  = `${on}<small> / ${vals.length}</small>`;
  document.getElementById('stat-latency').innerHTML = avg!=null ? `${avg}<small>ms</small>` : `–<small>ms</small>`;
  document.getElementById('overlay-nodes').textContent = `${on} / ${vals.length}`;
}

// Fetch
async function fetchStatus() {
  const btn = document.getElementById('btn-refresh');
  const liveDot = document.getElementById('live-dot');
  btn.classList.add('spin');
  liveDot.classList.add('live');
  try {
    const res  = await fetch('/status');
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    for (const [k,s] of Object.entries(data)) { state[k]=s; updateMarker(k,s); }
    renderCards(data);
    updatePill(data);
    updateStats(data);
    const ts = Object.values(data)[0]?.checked_at;
    if (ts) document.getElementById('last-update').textContent = 'Updated ' + timeAgo(ts);
  } catch(e) {
    document.getElementById('pill-text').textContent = 'Connection Error';
    document.getElementById('global-pill').className = 'header-pill pill-red';
  } finally {
    setTimeout(()=>btn.classList.remove('spin'), 500);
    setTimeout(()=>liveDot.classList.remove('live'), 800);
  }
}

// Relative time updater
setInterval(()=>{
  const ts = Object.values(state)[0]?.checked_at;
  if (ts) document.getElementById('last-update').textContent = 'Updated ' + timeAgo(ts);
}, 1000);

fetchStatus();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)