import psycopg2, uuid
RVB="bb6757d9-c36d-41bd-a4df-353d004e6152"
ADMIN=str(uuid.uuid5(uuid.UUID(RVB),"admin-user"))
cn=psycopg2.connect(host="127.0.0.1",port=5442,user="recognition",dbname="recognition");cn.autocommit=True;cur=cn.cursor()
# fetch model ids
cur.execute("SELECT module,id FROM rvb.models"); models={m:i for m,i in cur.fetchall()}
def mod(i): return "counting" if i<8 else ("epi" if i<24 else "quality")
GN={"counting":"Estacionamento/Carga","epi":"EPI/Segurança","quality":"Qualidade"}
n=0
for i in range(28):
    m=mod(i); cid=str(uuid.uuid5(uuid.UUID(RVB),f"cam-{i:03d}"))
    cur.execute("""INSERT INTO public.cameras
      (id,user_id,tenant_id,name,location,manufacturer,host,port,username,password_encrypted,
       channel,subtype,rtsp_url_override,is_active,module_code,active_module,
       model_epi_id,model_quality_id,model_counting_id,created_at)
      VALUES (%s,%s,%s,%s,%s,'intelbras',%s,554,'admin','PLACEHOLDER',1,0,%s,TRUE,%s,%s,%s,%s,%s,now())
      ON CONFLICT (id) DO UPDATE SET module_code=EXCLUDED.module_code,active_module=EXCLUDED.active_module,
        model_epi_id=EXCLUDED.model_epi_id,model_quality_id=EXCLUDED.model_quality_id,
        model_counting_id=EXCLUDED.model_counting_id,rtsp_url_override=EXCLUDED.rtsp_url_override,is_active=TRUE""",
      (cid,ADMIN,RVB,f"RVB Cam {i:02d} [{GN[m]}]",GN[m],f"192.168.1.{100+i}",
       f"rtsp://127.0.0.1:8554/cam{i}",m,m,
       models.get("epi") if m=="epi" else None,
       models.get("quality") if m=="quality" else None,
       models.get("counting") if m=="counting" else None))
    n+=1
cur.execute("SELECT module_code,count(*) FROM public.cameras WHERE tenant_id=%s GROUP BY module_code ORDER BY module_code",(RVB,))
print("public.cameras:",dict(cur.fetchall()),"inserted",n)
