import json, os, sys, glob
from datetime import datetime
F=os.path.expanduser("~/soak113/logs/telemetry_soak.jsonl")
start=None
sp=os.path.expanduser("~/soak113/logs/soak_start.txt")
if os.path.exists(sp):
    start=open(sp).read().strip().split("=")[1]
rows=[]
for l in open(F):
    try:
        r=json.loads(l)
        if start and r["ts"]<start: continue
        rows.append(r)
    except: pass
if not rows: print("no rows"); sys.exit()
def col(k,f=None):
    if f is None: f=lambda r,k=k:r.get(k)
    v=[f(r) for r in rows if f(r) is not None]
    return v
def stat(v): return (min(v),sum(v)/len(v),max(v)) if v else (None,None,None)
def slope(v):  # per-hour drift (leak indicator), samples 5s
    if len(v)<10: return 0
    n=len(v); xbar=(n-1)/2; ybar=sum(v)/n
    num=sum((i-xbar)*(v[i]-ybar) for i in range(n)); den=sum((i-xbar)**2 for i in range(n))
    per_sample=num/den if den else 0
    return per_sample*(3600/5)  # per hour
mem=col("mem_used_mb"); avail=col("mem_avail_mb"); swap=col("swap_used_mb")
gpu=col("gpu_load_pct"); gt=col("temps_c",lambda r:r["temps_c"].get("gpu"))
vdd=col("power_mw",lambda r:r["power_mw"].get("VDD_IN")); lat=col("api_lat_ms")
swout=col("pswpout_s"); la=col("loadavg",lambda r:r["loadavg"][0])
dur_min=(datetime.fromisoformat(rows[-1]["ts"].replace("Z","+00:00"))-datetime.fromisoformat(rows[0]["ts"].replace("Z","+00:00"))).total_seconds()/60
out={
 "samples":len(rows),"duration_min":round(dur_min,1),
 "mem_used_mb":stat(mem),"mem_used_slope_mb_per_h":round(slope(mem),1),
 "mem_avail_mb":stat(avail),"swap_used_mb":stat(swap),"swap_out_per_s":stat(swout),
 "gpu_pct":stat(gpu),"gpu_temp_c":stat(gt),"vdd_in_mw":stat(vdd),
 "api_lat_ms":stat(lat),"loadavg1":stat(la),
}
print(json.dumps(out,indent=1,default=lambda x:round(x,1) if isinstance(x,float) else x))
