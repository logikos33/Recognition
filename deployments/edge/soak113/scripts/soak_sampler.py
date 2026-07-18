"""task-113 soak sampler — memoria-centrico. JSONL 5s -> telemetry_soak.jsonl
Reusa paths sysfs validados do campaign sampler + adiciona PSI, swap in/out,
RSS por servico, latencia API, profundidade de fila redis."""
import json, os, time, glob, subprocess
from datetime import datetime, timezone

OUT = os.path.expanduser("~/soak113/logs/telemetry_soak.jsonl")
LABEL = os.path.expanduser("~/soak113/logs/phase.label")
REDIS_CLI = os.path.expanduser("~/soak113/redis/src/redis-cli")

def rd(p, cast=str):
    try:
        with open(p) as f: return cast(f.read().strip())
    except Exception: return None

def ina3221():
    out = {}
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        if rd(f"{hw}/name") != "ina3221": continue
        for i in (1,2,3):
            lab = rd(f"{hw}/in{i}_label"); v = rd(f"{hw}/in{i}_input", int); c = rd(f"{hw}/curr{i}_input", int)
            if lab and v is not None and c is not None: out[lab] = round(v*c/1000)
    return out

def temps():
    out = {}
    for tz in glob.glob("/sys/devices/virtual/thermal/thermal_zone*"):
        t = rd(f"{tz}/type"); v = rd(f"{tz}/temp", int)
        if t and v is not None: out[t.replace("-thermal","")] = round(v/1000,2)
    return out

def meminfo():
    d = {}
    for l in open("/proc/meminfo"):
        k,v = l.split(":"); d[k] = int(v.split()[0])
    return d

def psi():
    out = {}
    try:
        for l in open("/proc/pressure/memory"):
            parts = l.split()
            kind = parts[0]  # some|full
            vals = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in parts[1:]}
            out[kind] = vals
    except Exception: pass
    return out

def vmstat():
    d = {}
    for l in open("/proc/vmstat"):
        k,v = l.split(); d[k] = int(v)
    return d

# svc classification by cmdline substring
SVC = [("redis","redis-server"),("postgres","postgres"),("api","gunicorn"),
       ("deepstream","deepstream-app"),("mediamtx","mediamtx"),("pacer","pacer_"),
       ("producer","soak_producer"),("consumer","soak_consumer"),("sampler","soak_sampler")]
def per_svc_rss():
    agg = {k:0 for k,_ in SVC}; agg["other"]=0
    for p in glob.glob("/proc/[0-9]*"):
        try:
            cmd = open(f"{p}/cmdline").read().replace("\0"," ")
            rss = 0
            for l in open(f"{p}/status"):
                if l.startswith("VmRSS"): rss = int(l.split()[1]); break
            hit = False
            for k,sub in SVC:
                if sub in cmd: agg[k]+=rss; hit=True; break
        except Exception: pass
    return {k:round(v/1024) for k,v in agg.items() if v>0}  # MB

def api_latency_ms():
    try:
        t0=time.time()
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=3).read()
        return round((time.time()-t0)*1000,1)
    except Exception: return None

def redis_stat():
    try:
        q = subprocess.run([REDIS_CLI,"-p","6390","LLEN","soak:detections"],capture_output=True,text=True,timeout=3).stdout.strip()
        used = subprocess.run([REDIS_CLI,"-p","6390","INFO","memory"],capture_output=True,text=True,timeout=3).stdout
        um = next((l.split(":")[1].strip() for l in used.splitlines() if l.startswith("used_memory:")), None)
        return {"queue": int(q) if q.isdigit() else None, "used_bytes": int(um) if um else None}
    except Exception: return {}

prev_vm = vmstat(); prev_t = time.time()
while True:
    m = meminfo(); vm = vmstat(); now = time.time(); dt = max(1e-3, now-prev_t)
    la = os.getloadavg()
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "label": rd(LABEL) or "soak",
        "mem_used_mb": round((m["MemTotal"]-m["MemAvailable"])/1024),
        "mem_avail_mb": round(m["MemAvailable"]/1024),
        "mem_total_mb": round(m["MemTotal"]/1024),
        "swap_used_mb": round((m.get("SwapTotal",0)-m.get("SwapFree",0))/1024),
        "swap_free_mb": round(m.get("SwapFree",0)/1024),
        "pswpin_s": round((vm["pswpin"]-prev_vm["pswpin"])/dt,1),
        "pswpout_s": round((vm["pswpout"]-prev_vm["pswpout"])/dt,1),
        "psi_mem": psi(),
        "loadavg": [round(x,2) for x in la],
        "gpu_load_pct": (rd("/sys/devices/platform/17000000.gpu/load", int) or 0)/10,
        "gpu_freq_hz": rd("/sys/class/devfreq/17000000.gpu/cur_freq", int),
        "power_mw": ina3221(),
        "temps_c": temps(),
        "rss_mb": per_svc_rss(),
        "api_lat_ms": api_latency_ms(),
        "redis": redis_stat(),
    }
    with open(OUT,"a") as f: f.write(json.dumps(rec,separators=(",",":"))+"\n")
    prev_vm, prev_t = vm, now
    time.sleep(5)
