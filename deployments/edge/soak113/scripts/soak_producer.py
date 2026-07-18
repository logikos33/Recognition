"""Produtor: 28 cams x ~5 det/s -> LPUSH redis soak:detections; pubsub detections:{cam};
a cada 30s um 'clipe' de evidencia ~5MB SETEX ttl 120s (churn de memoria -> testa LRU)."""
import json, time, os, random, redis
r = redis.Redis(host="127.0.0.1", port=6390, decode_responses=False)
CAMS = [f"cam{i}" for i in range(28)]
clip = os.urandom(5*1024*1024)
t0=time.time(); nclip=t0+30; n=0
while True:
    tick=time.time()
    for cam in CAMS:
        for _ in range(5):  # ~5 inf/s por cam
            det = json.dumps({"camera_id":cam,"cls":random.choice(["Vest","Helmet","Person","NoVest"]),
                "conf":round(random.uniform(0.5,0.99),3),"bbox":[round(random.random(),3) for _ in range(4)],
                "ts":time.time()}).encode()
            r.lpush("soak:detections", det); n+=1
            r.publish(f"detections:{cam}", det)
    r.ltrim("soak:detections", 0, 200000)  # safety bound
    if time.time()>=nclip:
        r.setex(f"soak:evidence:{int(time.time())}", 120, clip); nclip+=30
    if n % 2800 == 0:
        print(json.dumps({"produced":n,"qlen":r.llen("soak:detections"),"t":round(time.time()-t0)}), flush=True)
    time.sleep(max(0,1-(time.time()-tick)))
