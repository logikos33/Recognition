"""task-113 embarque RVB: admin + 3 models + 28 cameras (module+model) + deployment_mode=dual.
Idempotente. Vincula cameras aos streams paced cam0..cam27 (local) para validar fim-a-fim."""
import psycopg2, bcrypt, uuid
RVB = "bb6757d9-c36d-41bd-a4df-353d004e6152"
cn = psycopg2.connect(host="127.0.0.1", port=5442, user="recognition", dbname="recognition")
cn.autocommit = True; cur = cn.cursor()

# tenant -> dual + ensure schema
cur.execute("UPDATE tenants SET deployment_mode='hybrid', schema_name='rvb' WHERE id=%s", (RVB,))

# admin
pw = bcrypt.hashpw(b"RvbSoak113!", bcrypt.gensalt()).decode()
uid = str(uuid.uuid5(uuid.UUID(RVB), "admin-user"))
cur.execute("""INSERT INTO users (id,email,password_hash,name,role,is_active,tenant_id)
  VALUES (%s,'admin@rvb.com.br',%s,'Admin RVB','admin',TRUE,%s)
  ON CONFLICT (email) DO UPDATE SET password_hash=EXCLUDED.password_hash, tenant_id=EXCLUDED.tenant_id, is_active=TRUE""",
  (uid, pw, RVB))

# 3 models (epi/quality/counting) in rvb.models
models = {}
for mod, nm in [("epi","PPE YOLOX INT8"),("quality","RF-DETR ROI Qualidade"),("counting","YOLOX COCO Contagem")]:
    mid = str(uuid.uuid5(uuid.UUID(RVB), f"model-{mod}"))
    cur.execute("""INSERT INTO rvb.models (id,name,module,version,active,created_at)
      VALUES (%s,%s,%s,'v1',TRUE,now()) ON CONFLICT (id) DO UPDATE SET active=TRUE""", (mid, nm, mod))
    models[mod] = mid

# 28 cameras -> module/model, rtsp -> paced streams cam0..cam27
# park/counting: 0-7 (8) | epi: 8-23 (16) | quality: 24-27 (4)
def module_for(i):
    if i < 8: return "counting"
    if i < 24: return "epi"
    return "quality"
GROUP_NAMES = {"counting":"Estacionamento/Carga","epi":"EPI/Segurança","quality":"Qualidade"}
n=0
for i in range(28):
    mod = module_for(i)
    cid = str(uuid.uuid5(uuid.UUID(RVB), f"cam-{i:03d}"))
    epi_id = models["epi"] if mod=="epi" else None
    qual_id = models["quality"] if mod=="quality" else None
    cnt_id = models["counting"] if mod=="counting" else None
    cur.execute("""INSERT INTO rvb.cameras (id,name,location,rtsp_url,status,active_module,model_epi_id,model_quality_id,model_counting_id,created_at,updated_at)
      VALUES (%s,%s,%s,%s,'active',%s,%s,%s,%s,now(),now())
      ON CONFLICT (id) DO UPDATE SET active_module=EXCLUDED.active_module,
        model_epi_id=EXCLUDED.model_epi_id, model_quality_id=EXCLUDED.model_quality_id,
        model_counting_id=EXCLUDED.model_counting_id, rtsp_url=EXCLUDED.rtsp_url, status='active'""",
      (cid, f"RVB Cam {i:02d} [{GROUP_NAMES[mod]}]", GROUP_NAMES[mod],
       f"rtsp://127.0.0.1:8554/cam{i}", mod, epi_id, qual_id, cnt_id))
    n+=1
print(f"OK admin=1 models={len(models)} cameras={n}")
cur.execute("SELECT active_module,count(*) FROM rvb.cameras GROUP BY active_module ORDER BY active_module")
for r in cur.fetchall(): print("  ", r[0], r[1])
