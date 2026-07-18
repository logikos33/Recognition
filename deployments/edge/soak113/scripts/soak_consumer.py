"""Consumidor (surrogate edge-sync + dashboard): BRPOP redis -> batch INSERT postgres;
a cada 10s roda queries de dashboard (agregacoes); a cada 60s poda linhas > 30min (retencao edge)."""
import json, time, redis, psycopg2, psycopg2.extras
r = redis.Redis(host="127.0.0.1", port=6390, decode_responses=True)
cn = psycopg2.connect(host="127.0.0.1", port=5442, user="recognition", dbname="recognition")
cn.autocommit=True; cur=cn.cursor()
buf=[]; last_dash=time.time(); last_prune=time.time(); ins=0
while True:
    item = r.brpop("soak:detections", timeout=2)
    if item:
        try:
            d=json.loads(item[1]); buf.append((d["camera_id"],d.get("cls"),d.get("conf"),json.dumps(d)))
        except Exception: pass
    if len(buf)>=200 or (buf and time.time()-last_dash>2):
        psycopg2.extras.execute_values(cur,
          "INSERT INTO soak_events (camera_id,cls,conf,payload) VALUES %s", buf); ins+=len(buf); buf=[]
    if time.time()-last_dash>10:
        cur.execute("SELECT camera_id,count(*),avg(conf) FROM soak_events WHERE ts>now()-interval '5 min' GROUP BY camera_id")
        _=cur.fetchall()
        cur.execute("SELECT cls,count(*) FROM soak_events WHERE ts>now()-interval '1 min' GROUP BY cls")
        _=cur.fetchall(); last_dash=time.time()
        print(json.dumps({"inserted":ins,"qlen":r.llen("soak:detections")}), flush=True)
    if time.time()-last_prune>60:
        cur.execute("DELETE FROM soak_events WHERE ts < now()-interval '30 min'"); last_prune=time.time()
