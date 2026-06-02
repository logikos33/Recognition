# DATABASE.md — EPI Monitor V2 Schema Reference

Cumulative schema produced by running all 13 migrations in order.
Migration runner: `backend/app/infrastructure/database/migrations/run_migrations.py`
Tracking table: `schema_migrations` (version VARCHAR(10) PRIMARY KEY, applied_at TIMESTAMPTZ)
Current migration count: 13 (001 through 013)
Next migration number: 014

---

## Multi-Tenant Pattern

Every major table carries `tenant_id UUID REFERENCES tenants(id)`. The default tenant
`00000000-0000-0000-0000-000000000001` (slug `default`) is seeded by migration 005 and used
as a fallback for all pre-existing rows. `get_tenant_id()` in `app/core/auth.py` extracts the
value from the JWT claim and defaults to that UUID when absent.

---

## Tables

### schema_migrations
Tracks which migrations have been applied. Created by `run_migrations.py` before any SQL file
is executed; also created inside `001_initial_schema.sql` as a safety net.

| Column | Type | Constraints |
|---|---|---|
| version | VARCHAR(10) | PRIMARY KEY |
| applied_at | TIMESTAMPTZ | DEFAULT NOW() |

---

### tenants
Seeded in migration 005. One row per organisation.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| name | VARCHAR(255) | NOT NULL |
| slug | VARCHAR(100) | UNIQUE NOT NULL |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

---

### users
Created in migration 001. `tenant_id` added in migration 005.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| email | VARCHAR(255) | UNIQUE NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| name | VARCHAR(200) | NOT NULL |
| role | VARCHAR(20) | NOT NULL DEFAULT 'operator', CHECK IN ('admin','operator') |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| tenant_id | UUID | REFERENCES tenants(id) |

Indexes: `idx_users_email`, `idx_users_role`, `idx_users_tenant`

---

### cameras
Canonical camera table. Originally created as `ip_cameras` in migration 002; migration 013
renames it to `cameras` (or merges and drops `ip_cameras` if both coexisted).
Columns added across migrations 005, 007, 010, 011, 012.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| name | VARCHAR(200) | NOT NULL |
| location | VARCHAR(300) | |
| description | TEXT | |
| manufacturer | VARCHAR(50) | NOT NULL DEFAULT 'generic' |
| host | VARCHAR(255) | NOT NULL |
| port | INTEGER | NOT NULL DEFAULT 554 |
| username | VARCHAR(100) | DEFAULT 'admin' |
| password_encrypted | TEXT | |
| channel | INTEGER | NOT NULL DEFAULT 1 |
| subtype | INTEGER | NOT NULL DEFAULT 0 |
| rtsp_url_override | TEXT | |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE |
| last_seen | TIMESTAMP | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| tenant_id | UUID | REFERENCES tenants(id) — added 005 |
| active_model_id | UUID | REFERENCES models(id) — added 007 |
| module_code | VARCHAR(50) | DEFAULT 'epi' — added 010 |
| last_error | TEXT | added 012 |
| last_tested_at | TIMESTAMPTZ | added 012 |
| updated_at | TIMESTAMPTZ | added 012 |

Indexes: `idx_cameras_user`, `idx_cameras_active`, `idx_cameras_tenant`,
`idx_cameras_module` (tenant_id, module_code), `idx_cameras_user_active` (user_id, is_active)

---

### camera_events
Created in migration 002.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| camera_id | UUID | NOT NULL REFERENCES cameras(id) ON DELETE CASCADE |
| event_type | VARCHAR(50) | NOT NULL |
| details | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |

Indexes: `idx_cam_events_camera`, `idx_cam_events_created`

---

### alerts
Created in migration 004. `tenant_id` added in 005; `module_code` added in 010.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| camera_id | UUID | NOT NULL REFERENCES cameras(id) ON DELETE CASCADE |
| timestamp | TIMESTAMP | NOT NULL DEFAULT NOW() |
| violations | JSONB | NOT NULL DEFAULT '[]' |
| confidence | FLOAT | NOT NULL DEFAULT 0.0 |
| evidence_key | VARCHAR(500) | |
| acknowledged | BOOLEAN | NOT NULL DEFAULT FALSE |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| tenant_id | UUID | REFERENCES tenants(id) — added 005 |
| module_code | VARCHAR(50) | DEFAULT 'epi' — added 010 |

Indexes: `idx_alerts_camera`, `idx_alerts_timestamp`, `idx_alerts_acknowledged`,
`idx_alerts_tenant`, `idx_alerts_module` (tenant_id, module_code)

---

### alert_rules
Created in migration 006. Seeds default `no_helmet` and `no_vest` rules for all tenants.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| tenant_id | UUID | NOT NULL |
| camera_id | UUID | NULL = applies to all cameras for tenant |
| violation_type | VARCHAR(50) | NOT NULL |
| min_duration_seconds | INTEGER | DEFAULT 3 |
| min_occurrences | INTEGER | |
| time_window_seconds | INTEGER | |
| create_alert | BOOLEAN | DEFAULT TRUE |
| enabled | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() |

Indexes: `idx_alert_rules_tenant`, `idx_alert_rules_camera` (WHERE camera_id IS NOT NULL),
`idx_alert_rules_enabled` (WHERE enabled = true)

---

### rules
Created in migration 004 (legacy rules engine, predates `alert_rules`).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| name | VARCHAR(200) | NOT NULL |
| trigger_type | VARCHAR(50) | NOT NULL DEFAULT 'detection' |
| trigger_class | VARCHAR(100) | |
| action_type | VARCHAR(50) | NOT NULL DEFAULT 'alert' |
| confidence_threshold | FLOAT | NOT NULL DEFAULT 0.5 |
| cooldown_seconds | INTEGER | NOT NULL DEFAULT 60 |
| camera_filter | UUID[] | |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |

Indexes: `idx_rules_user`, `idx_rules_active`

---

### dataset_versions
Created in migration 004.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| version | VARCHAR(20) | NOT NULL |
| frame_count | INTEGER | NOT NULL DEFAULT 0 |
| train_count | INTEGER | NOT NULL DEFAULT 0 |
| val_count | INTEGER | NOT NULL DEFAULT 0 |
| test_count | INTEGER | NOT NULL DEFAULT 0 |
| class_distribution | JSONB | DEFAULT '{}' |
| metadata_key | VARCHAR(500) | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |

Indexes: `idx_dataset_versions_user`

---

### training_videos
Created in migration 003. `module_code` added in 010.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| filename | VARCHAR(500) | NOT NULL |
| original_filename | VARCHAR(500) | |
| file_size | BIGINT | |
| duration_seconds | FLOAT | |
| status | VARCHAR(30) | NOT NULL DEFAULT 'uploaded', CHECK IN ('uploaded','extracting','extracted','error') |
| frame_count | INTEGER | DEFAULT 0 |
| error_message | TEXT | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| module_code | VARCHAR(50) | DEFAULT 'epi' — added 010 |

Indexes: `idx_videos_user`, `idx_videos_status`

---

### training_frames
Created in migration 003. Extended by migrations 010 and 011.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| video_id | UUID | NOT NULL REFERENCES training_videos(id) ON DELETE CASCADE |
| frame_number | INTEGER | NOT NULL |
| filename | VARCHAR(500) | NOT NULL |
| timestamp_seconds | FLOAT | |
| is_annotated | BOOLEAN | NOT NULL DEFAULT FALSE |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| module_code | VARCHAR(50) | DEFAULT 'epi' — added 010 |
| tenant_id | UUID | REFERENCES tenants(id) — added 011 |
| pre_annotations | JSONB | added 011 |
| pre_annotated_at | TIMESTAMPTZ | added 011 |
| uncertainty_score | FLOAT | active learning score — added 011 |
| priority_rank | INTEGER | active learning rank — added 011 |

Indexes: `idx_frames_video`, `idx_frames_annotated`, `idx_training_frames_module`,
`idx_frames_priority` (tenant_id, module_code, quality_status, priority_rank)

Note: `quality_status` is referenced in the `idx_frames_priority` index but not present in any
migration SQL. It must be added manually or via migration 014 before the index is usable.

---

### yolo_classes
Created in migration 003.

| Column | Type | Constraints |
|---|---|---|
| id | SERIAL | PRIMARY KEY |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| name | VARCHAR(100) | NOT NULL |
| color | VARCHAR(7) | DEFAULT '#3b82f6' |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| | | UNIQUE(user_id, name) |

---

### frame_annotations
Created in migration 003. Bounding boxes in YOLO normalised coordinates.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| frame_id | UUID | NOT NULL REFERENCES training_frames(id) ON DELETE CASCADE |
| class_id | INTEGER | NOT NULL REFERENCES yolo_classes(id) ON DELETE CASCADE |
| x_center | FLOAT | NOT NULL, CHECK BETWEEN 0 AND 1 |
| y_center | FLOAT | NOT NULL, CHECK BETWEEN 0 AND 1 |
| width | FLOAT | NOT NULL, CHECK > 0 AND <= 1 |
| height | FLOAT | NOT NULL, CHECK > 0 AND <= 1 |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |

Indexes: `idx_annotations_frame`

---

### training_jobs
Created in migration 003. `tenant_id` added in 005.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| preset | VARCHAR(20) | NOT NULL DEFAULT 'balanced', CHECK IN ('fast','balanced','quality') |
| model_size | VARCHAR(20) | NOT NULL DEFAULT 'yolov8n' |
| status | VARCHAR(20) | NOT NULL DEFAULT 'pending', CHECK IN ('pending','running','completed','failed','stopped') |
| progress | INTEGER | NOT NULL DEFAULT 0 |
| current_epoch | INTEGER | DEFAULT 0 |
| total_epochs | INTEGER | DEFAULT 100 |
| metrics | JSONB | DEFAULT '{}' |
| error_message | TEXT | |
| progress_file | VARCHAR(500) | |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |
| tenant_id | UUID | REFERENCES tenants(id) — added 005 |

Indexes: `idx_jobs_user`, `idx_jobs_status`, `idx_training_jobs_tenant`

---

### trained_models
Created in migration 003.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES users(id) ON DELETE CASCADE |
| job_id | UUID | REFERENCES training_jobs(id) |
| name | VARCHAR(200) | NOT NULL |
| model_path | VARCHAR(500) | NOT NULL |
| map50 | FLOAT | |
| precision | FLOAT | |
| recall | FLOAT | |
| is_active | BOOLEAN | NOT NULL DEFAULT FALSE |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() |

Indexes: `idx_models_user`, `idx_models_active`

---

### models
Created in migration 007. Tenant-scoped model registry (distinct from `trained_models`).
`module_code` added in migration 010.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| tenant_id | UUID | NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| model_key | VARCHAR(500) | NOT NULL |
| metrics | JSONB | DEFAULT '{}' |
| is_default | BOOLEAN | DEFAULT FALSE |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |
| module_code | VARCHAR(50) | DEFAULT 'epi' — added 010 |

Indexes: `idx_models_tenant`

---

### tenant_modules
Created in migration 008. Controls which feature modules a tenant has access to.
Seeds module `epi` as enabled for all existing tenants.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| tenant_id | UUID | NOT NULL REFERENCES tenants(id) ON DELETE CASCADE |
| module_code | VARCHAR(50) | NOT NULL |
| enabled | BOOLEAN | DEFAULT TRUE |
| config | JSONB | DEFAULT '{}' |
| activated_at | TIMESTAMPTZ | DEFAULT NOW() |
| expires_at | TIMESTAMPTZ | |
| | | UNIQUE(tenant_id, module_code) |

Indexes: `idx_tenant_modules_tenant`, `idx_tenant_modules_code`

---

### module_classes
Created in migration 009. Global lookup table — not tenant-scoped.
Pre-populated with EPI (8 classes) and Fueling (5 placeholder classes).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| module_code | VARCHAR(50) | NOT NULL |
| class_id | INTEGER | NOT NULL |
| class_name | VARCHAR(100) | NOT NULL |
| display_name | VARCHAR(100) | |
| icon | VARCHAR(50) | |
| is_violation | BOOLEAN | DEFAULT FALSE |
| color | VARCHAR(20) | |
| | | UNIQUE(module_code, class_name) |

Indexes: `idx_module_classes_code`

Seeded EPI classes: `helmet(0)`, `no_helmet(1)`, `vest(2)`, `no_vest(3)`,
`gloves(4)`, `no_gloves(5)`, `glasses(6)`, `no_glasses(7)`

---

## Edge Deployment Tables (Fase 1 — migrations 050-054)

### tenants (column added — migration 052)

| Column | Type | Constraints |
|---|---|---|
| deployment_mode | TEXT | NOT NULL DEFAULT 'cloud' CHECK IN ('cloud','edge','hybrid') |

---

### edge_sites (migration 050)
Sites físicos onde rodam Mini PCs de edge. Um tenant pode ter N sites.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| tenant_id | UUID | NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE |
| name | TEXT | NOT NULL |
| description | TEXT | |
| location | TEXT | |
| deployment_mode | TEXT | NOT NULL CHECK IN ('cloud','edge','hybrid') |
| status | TEXT | NOT NULL DEFAULT 'active' CHECK IN ('active','inactive','maintenance','provisioning') |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() (via trigger) |
| created_by | UUID | |

Indexes: `idx_edge_sites_tenant`, `uniq_edge_sites_tenant_name` (UNIQUE)

---

### enrollment_tokens (migration 051)
Tokens one-time para enrollment inicial de dispositivos edge.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| tenant_id | UUID | NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE |
| site_id | UUID | NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE |
| token_hash | TEXT | NOT NULL UNIQUE |
| expires_at | TIMESTAMPTZ | NOT NULL |
| used_at | TIMESTAMPTZ | |
| used_by_device_id | TEXT | |
| created_by | UUID | |
| created_at | TIMESTAMPTZ | DEFAULT now() |

Indexes: `idx_enrollment_tokens_tenant_site`, `idx_enrollment_tokens_pending` (partial, WHERE used_at IS NULL)

---

### device_tokens (migration 051)
Dispositivos edge registrados com chave pública RSA após enrollment.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| tenant_id | UUID | NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE |
| site_id | UUID | NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE |
| device_id | TEXT | NOT NULL |
| device_name | TEXT | |
| public_key_pem | TEXT | NOT NULL |
| fingerprint | TEXT | NOT NULL |
| revoked | BOOLEAN | NOT NULL DEFAULT false |
| revoked_at | TIMESTAMPTZ | |
| revoked_by | UUID | |
| revocation_reason | TEXT | |
| last_seen_at | TIMESTAMPTZ | |
| enrolled_at | TIMESTAMPTZ | DEFAULT now() |
| | | UNIQUE(tenant_id, device_id) |

Indexes: `idx_device_tokens_tenant_site`, `idx_device_tokens_active` (partial, WHERE revoked=false), `idx_device_tokens_fingerprint` (partial)

---

### edge_heartbeats (migration 053)
Telemetria time-series enviada pelos Mini PCs. Append-only, sem UPDATE/DELETE.

| Column | Type | Constraints |
|---|---|---|
| id | BIGSERIAL | PRIMARY KEY |
| tenant_id | UUID | NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE |
| site_id | UUID | NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE |
| device_id | TEXT | NOT NULL |
| received_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| cpu_pct | NUMERIC(5,2) | |
| mem_pct | NUMERIC(5,2) | |
| gpu_pct | NUMERIC(5,2) | |
| gpu_mem_pct | NUMERIC(5,2) | |
| disk_pct | NUMERIC(5,2) | |
| inference_fps | NUMERIC(6,2) | |
| inference_latency_ms | NUMERIC(8,2) | |
| cameras_online | INT | |
| cameras_total | INT | |
| queue_depth | INT | |
| upload_kbps | NUMERIC(10,2) | |
| download_kbps | NUMERIC(10,2) | |
| status | TEXT | CHECK IN ('healthy','degraded','critical','offline') |
| last_error | TEXT | |
| edge_version | TEXT | |

Indexes: `idx_edge_heartbeats_site_time` (site_id, received_at DESC), `idx_edge_heartbeats_tenant_time`, `idx_edge_heartbeats_status` (partial, status IN degraded/critical/offline)

---

### site_id column (migration 052)
Coluna `site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL` adicionada em:
- `public.cameras`, `public.alerts`, `public.counting_events`, `public.operations`
- `<tenant_schema>.quality_inspections`, `<tenant_schema>.quality_recording_segments` (loop sobre tenants ativos)

`create_tenant_schema()` atualizada em migration 054 para incluir `site_id` nas tabelas acima para novos tenants.

---

## Migration Runner Behaviour

`run_migrations.py` is called automatically by `railway_start.py` when `SERVICE_TYPE=api`.

1. Connects to `DATABASE_URL` (rewrites `postgres://` to `postgresql://` automatically).
2. Ensures `schema_migrations` table exists.
3. Reads all `*.sql` files in the migrations directory, sorted alphabetically.
4. Skips any file whose version prefix (e.g. `001`) is already in `schema_migrations`.
5. Executes each pending file in a transaction; records the version on success.
6. On `already exists` / `duplicate` errors, records the version as applied and continues
   (idempotent re-runs on fresh databases that already have objects from another source).
7. Any other psycopg2 error causes immediate failure with exit code 1.
