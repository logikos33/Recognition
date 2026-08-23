# Inventário de endpoints — gerado por `tools/api_inventory.py`

- HEAD: `98bff30e51283399c0d70554be760b56824af12e`
- Regras (método×path): **421** · paths únicos: **353**
- Blueprints registrados: 55 · sem regra: ['tenant_branding']

> Colunas `auth`/`envelope`/`tenant` são marcadores estáticos do corpo da view (heurística).
> A coluna verificada fica no mapa-contrato (`docs/migration/MAPA-MIGRACAO-FRONTEND.md`).

| Método | Path | Blueprint | Função | Arquivo:linha | Auth (decorators/body) | Envelope | Tenant |
|---|---|---|---|---|---|---|---|
| GET | `/` | (app) | `serve_frontend` | `services/api/app/__init__.py:592` | NONE(verificar) | jsonify, raw:file | — |
| GET | `/<path:path>` | (app) | `serve_frontend` | `services/api/app/__init__.py:592` | NONE(verificar) | jsonify, raw:file | — |
| GET | `/api/admin/demo-videos` | demo_videos | `list_demo_videos` | `services/api/app/api/v1/admin/demo_videos_routes.py:82` | superadmin | success(), error() | — |
| DELETE | `/api/admin/demo-videos/<int:video_id>` | demo_videos | `delete_demo_video` | `services/api/app/api/v1/admin/demo_videos_routes.py:107` | superadmin | success(), error() | — |
| POST | `/api/admin/demo-videos/upload` | demo_videos | `upload_demo_video` | `services/api/app/api/v1/admin/demo_videos_routes.py:27` | superadmin | success(), error() | — |
| GET | `/api/admin/roles` | roles | `list_roles` | `services/api/app/api/v1/roles/routes.py:58` | admin | success(), error() | tenant_id |
| POST | `/api/admin/roles` | roles | `create_role` | `services/api/app/api/v1/roles/routes.py:89` | admin | success(), error() | tenant_id |
| DELETE | `/api/admin/roles/<role_id>` | roles | `delete_role` | `services/api/app/api/v1/roles/routes.py:198` | admin | success(), error() | tenant_id |
| PUT | `/api/admin/roles/<role_id>` | roles | `update_role` | `services/api/app/api/v1/roles/routes.py:141` | admin | success(), error() | tenant_id |
| GET | `/api/admin/users/<user_id>/role` | roles | `get_user_role` | `services/api/app/api/v1/roles/routes.py:246` | admin | success(), error() | tenant_id |
| PUT | `/api/admin/users/<user_id>/role` | roles | `set_user_role` | `services/api/app/api/v1/roles/routes.py:281` | admin | success(), error() | tenant_id |
| GET | `/api/alerts` | alerts | `list_alerts` | `services/api/app/api/v1/alerts/routes.py:48` | jwt | success(), error() | tenant_id |
| POST | `/api/alerts/<alert_id>/acknowledge` | alerts | `acknowledge_alert` | `services/api/app/api/v1/alerts/routes.py:127` | jwt | success(), error() | — |
| GET | `/api/alerts/<alert_id>/snapshot` | alerts | `alert_snapshot` | `services/api/app/api/v1/alerts/routes.py:143` | jwt | success(), error() | tenant_id |
| GET | `/api/alerts/export` | alerts | `export_alerts` | `services/api/app/api/v1/alerts/routes.py:84` | jwt | error(), raw:Response | tenant_id |
| GET | `/api/alerts/stats` | alerts | `alert_stats` | `services/api/app/api/v1/alerts/routes.py:174` | jwt | success(), error() | tenant_id |
| POST | `/api/auth/forgot-password` | auth | `forgot_password` | `services/api/app/api/v1/auth/routes.py:311` | NONE(verificar) | success(), error() | — |
| POST | `/api/auth/login` | auth | `login` | `services/api/app/api/v1/auth/routes.py:88` | NONE(verificar) | success(), error() | tenant_schema, tenant_id |
| GET | `/api/auth/me` | auth | `me` | `services/api/app/api/v1/auth/routes.py:276` | jwt | success(), error() | — |
| POST | `/api/auth/register` | auth | `register` | `services/api/app/api/v1/auth/routes.py:47` | NONE(verificar) | success(), error() | — |
| POST | `/api/auth/reset-password` | auth | `reset_password` | `services/api/app/api/v1/auth/routes.py:343` | NONE(verificar) | success(), error() | — |
| GET | `/api/cameras` | cameras | `list_cameras` | `services/api/app/api/v1/cameras/crud_handlers.py:66` | jwt | success(), error() | tenant_id |
| POST | `/api/cameras` | cameras | `create_camera` | `services/api/app/api/v1/cameras/crud_handlers.py:100` | jwt | success(), error() | tenant_id |
| DELETE | `/api/cameras/<camera_id>` | cameras | `delete_camera` | `services/api/app/api/v1/cameras/crud_handlers.py:207` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>` | cameras | `get_camera` | `services/api/app/api/v1/cameras/crud_handlers.py:141` | jwt | success(), error() | tenant_id |
| PUT | `/api/cameras/<camera_id>` | cameras | `update_camera` | `services/api/app/api/v1/cameras/crud_handlers.py:167` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/alerts` | training | `get_alerts` | `services/api/app/api/v1/training/routes.py:454` | jwt | success(), error() | — |
| POST | `/api/cameras/<camera_id>/archive` | cameras | `archive_camera` | `services/api/app/api/v1/cameras/crud_handlers.py:231` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/available-models` | cameras | `get_available_models` | `services/api/app/api/v1/cameras/model_handlers.py:279` | jwt | success(), error() | tenant_id |
| PATCH | `/api/cameras/<camera_id>/config` | cameras | `patch_camera_config` | `services/api/app/api/v1/cameras/config_handler.py:80` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/effective-model` | cameras | `get_effective_model` | `services/api/app/api/v1/cameras/model_handlers.py:319` | jwt | success(), error() | tenant_schema, tenant_id |
| GET | `/api/cameras/<camera_id>/health-context` | cameras | `get_camera_health_context` | `services/api/app/api/v1/cameras/health_context_handler.py:57` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/model` | cameras | `get_camera_model` | `services/api/app/api/v1/cameras/model_handlers.py:87` | jwt | success(), error() | — |
| PUT | `/api/cameras/<camera_id>/model` | cameras | `set_camera_model` | `services/api/app/api/v1/cameras/model_handlers.py:106` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/model-config` | cameras | `get_camera_model_config` | `services/api/app/api/v1/cameras/model_config_handlers.py:91` | jwt | success(), error() | tenant_id |
| POST | `/api/cameras/<camera_id>/model-config` | cameras | `post_camera_model_config` | `services/api/app/api/v1/cameras/model_config_handlers.py:112` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/model-config/history` | cameras | `get_camera_model_config_history` | `services/api/app/api/v1/cameras/model_config_handlers.py:173` | jwt | success(), error() | tenant_id |
| POST | `/api/cameras/<camera_id>/model-config/rollback` | cameras | `post_camera_model_config_rollback` | `services/api/app/api/v1/cameras/model_config_handlers.py:197` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/models` | cameras | `get_camera_models` | `services/api/app/api/v1/cameras/model_handlers.py:178` | jwt | success(), error() | tenant_id |
| PUT | `/api/cameras/<camera_id>/models` | cameras | `put_camera_models` | `services/api/app/api/v1/cameras/model_handlers.py:206` | jwt | success(), error() | tenant_id |
| PATCH | `/api/cameras/<camera_id>/module` | cameras | `patch_camera_module` | `services/api/app/api/v1/cameras/module_handler.py:83` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/module/current` | cameras | `get_camera_module_current` | `services/api/app/api/v1/cameras/module_handler.py:171` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/operations` | operations | `list_camera_operations` | `services/api/app/api/v1/operations/routes.py:70` | jwt | success() | tenant_id |
| POST | `/api/cameras/<camera_id>/operations` | operations | `create_operation` | `services/api/app/api/v1/operations/routes.py:86` | jwt | success(), error() | tenant_id |
| POST | `/api/cameras/<camera_id>/restore` | cameras | `restore_camera` | `services/api/app/api/v1/cameras/crud_handlers.py:258` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/retention` | cameras | `get_camera_retention` | `services/api/app/api/v1/cameras/retention_handler.py:51` | jwt | success(), error() | tenant_id |
| PUT | `/api/cameras/<camera_id>/retention` | cameras | `put_camera_retention` | `services/api/app/api/v1/cameras/retention_handler.py:75` | jwt | success(), error() | tenant_id |
| PUT | `/api/cameras/<camera_id>/schedule` | cameras | `put_camera_schedule` | `services/api/app/api/v1/cameras/module_handler.py:135` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/snapshot` | cameras | `get_camera_snapshot` | `services/api/app/api/v1/cameras/snapshot_handlers.py:98` | jwt | success(), error() | tenant_id |
| POST | `/api/cameras/<camera_id>/snapshot/refresh` | cameras | `refresh_camera_snapshot` | `services/api/app/api/v1/cameras/snapshot_handlers.py:146` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/stream/<path:filename>` | cameras | `serve_hls` | `services/api/app/api/v1/cameras/stream_handlers.py:403` | playback_token(inline) | error(), raw:file, raw:stream, raw:Response | — |
| GET | `/api/cameras/<camera_id>/stream/info` | cameras | `stream_info` | `services/api/app/api/v1/cameras/stream_handlers.py:673` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/<camera_id>/stream/s/<token>/<path:filename>` | cameras | `serve_hls` | `services/api/app/api/v1/cameras/stream_handlers.py:403` | playback_token(inline) | error(), raw:file, raw:stream, raw:Response | — |
| POST | `/api/cameras/<camera_id>/stream/start` | cameras | `start_stream` | `services/api/app/api/v1/cameras/stream_handlers.py:191` | jwt | success(), error() | — |
| GET | `/api/cameras/<camera_id>/stream/status` | cameras | `stream_status` | `services/api/app/api/v1/cameras/stream_handlers.py:322` | jwt | success(), error() | — |
| POST | `/api/cameras/<camera_id>/stream/stop` | cameras | `stop_stream` | `services/api/app/api/v1/cameras/stream_handlers.py:305` | jwt | success(), error() | — |
| POST | `/api/cameras/<camera_id>/test` | cameras | `test_camera` | `services/api/app/api/v1/cameras/test_handler.py:21` | jwt | success(), error() | — |
| POST | `/api/cameras/probe` | cameras | `probe_camera` | `services/api/app/api/v1/cameras/probe_handler.py:171` | jwt | success(), error() | tenant_id |
| GET | `/api/cameras/tenant/retention` | cameras | `get_tenant_retention` | `services/api/app/api/v1/cameras/tenant_retention_handler.py:29` | jwt | success(), error() | tenant_id, public.* |
| PUT | `/api/cameras/tenant/retention` | cameras | `put_tenant_retention` | `services/api/app/api/v1/cameras/tenant_retention_handler.py:59` | jwt | success(), error() | tenant_id, public.* |
| POST | `/api/chat` | chat | `chat` | `services/api/app/api/v1/chat/routes.py:16` | jwt | error(), raw:stream, raw:Response | — |
| GET | `/api/chat/health` | chat | `chat_health` | `services/api/app/api/v1/chat/routes.py:62` | NONE(verificar) | raw:Response | — |
| GET | `/api/classes` | training | `get_classes` | `services/api/app/api/v1/training/routes.py:172` | jwt | error(), jsonify | tenant_id |
| POST | `/api/classes` | training | `create_class` | `services/api/app/api/v1/training/routes.py:178` | jwt | success(), error() | tenant_id |
| DELETE | `/api/classes/<int:class_id>` | training | `delete_class` | `services/api/app/api/v1/training/routes.py:199` | jwt | success(), error() | tenant_id |
| PATCH | `/api/classes/<int:class_id>` | training | `patch_class` | `services/api/app/api/v1/training/routes.py:192` | jwt | success(), error() | tenant_id |
| PUT | `/api/classes/<int:class_id>` | training | `update_class` | `services/api/app/api/v1/training/routes.py:185` | jwt | success(), error() | tenant_id |
| GET | `/api/counting/sessions` | counting | `list_sessions` | `services/api/app/api/v1/counting/routes.py:78` | jwt | success(), error() | tenant_id |
| POST | `/api/counting/sessions` | counting | `start_session` | `services/api/app/api/v1/counting/routes.py:51` | jwt | success(), error() | tenant_id |
| DELETE | `/api/counting/sessions/<session_id>` | counting | `stop_session` | `services/api/app/api/v1/counting/routes.py:125` | jwt | success(), error() | tenant_id |
| PATCH | `/api/counting/sessions/<session_id>` | counting | `update_session` | `services/api/app/api/v1/counting/routes.py:92` | jwt | success(), error() | tenant_id |
| PATCH | `/api/counting/sessions/<session_id>/plate` | counting | `update_plate` | `services/api/app/api/v1/counting/routes.py:167` | jwt | success(), error() | tenant_id |
| GET | `/api/counting/sessions/<session_id>/stats` | counting | `session_stats` | `services/api/app/api/v1/counting/routes.py:144` | jwt | success(), error() | tenant_id |
| GET | `/api/counting/sessions/plates` | counting | `list_sessions_with_plates` | `services/api/app/api/v1/counting/routes.py:240` | jwt | success(), error() | tenant_id |
| GET | `/api/counting/sessions/validation-report` | counting | `validation_report` | `services/api/app/api/v1/counting/routes.py:267` | jwt | success(), error() | tenant_id |
| POST | `/api/devices/claim` | devices | `claim_device` | `services/api/app/api/v1/devices/routes.py:97` | enrollment_token(inline) | success(), error() | tenant_id |
| POST | `/api/devices/claim-codes` | devices | `create_claim_code` | `services/api/app/api/v1/devices/routes.py:47` | jwt | success(), error() | tenant_id |
| GET | `/api/fueling/bays` | fueling | `fueling_bays` | `services/api/app/api/v1/fueling/routes.py:218` | jwt | success(), error() | tenant_id |
| GET | `/api/fueling/bays/<int:bay_id>` | fueling | `fueling_bay_detail` | `services/api/app/api/v1/fueling/routes.py:248` | jwt | success(), error() | tenant_id |
| GET | `/api/fueling/dashboard` | fueling | `fueling_dashboard` | `services/api/app/api/v1/fueling/routes.py:175` | jwt | success(), error() | tenant_id |
| GET | `/api/fueling/events` | fueling | `fueling_events` | `services/api/app/api/v1/fueling/routes.py:123` | jwt | success(), error() | tenant_id |
| GET | `/api/fueling/stats` | fueling | `fueling_stats` | `services/api/app/api/v1/fueling/routes.py:83` | jwt | success(), error() | tenant_id |
| GET | `/api/modules/` | modules | `list_modules` | `services/api/app/api/v1/modules/routes.py:26` | jwt | success(), error() | tenant_id |
| GET | `/api/modules/<module_code>` | modules | `get_module` | `services/api/app/api/v1/modules/routes.py:39` | jwt | success(), error() | tenant_id |
| GET | `/api/modules/<module_code>/classes` | modules | `get_module_classes` | `services/api/app/api/v1/modules/routes.py:54` | jwt | success(), error() | tenant_id |
| PATCH | `/api/modules/<module_code>/classes/<class_id>` | modules | `toggle_module_class` | `services/api/app/api/v1/modules/routes.py:98` | jwt | success(), error() | tenant_id |
| GET | `/api/modules/<module_code>/stats` | modules | `get_module_stats` | `services/api/app/api/v1/modules/routes.py:83` | jwt | success(), error() | tenant_id |
| GET | `/api/modules/<module_id>/operation-types` | operations | `list_operation_types` | `services/api/app/api/v1/operations/routes.py:55` | jwt | success() | — |
| DELETE | `/api/operations/<int:operation_id>` | operations | `delete_operation` | `services/api/app/api/v1/operations/routes.py:165` | jwt | success(), error() | tenant_id |
| PUT | `/api/operations/<int:operation_id>` | operations | `update_operation` | `services/api/app/api/v1/operations/routes.py:126` | jwt | success(), error() | tenant_id |
| GET | `/api/operations/<int:operation_id>/results` | operations | `get_operation_results` | `services/api/app/api/v1/operations/routes.py:196` | jwt | success(), error() | tenant_id |
| POST | `/api/operations/<int:operation_id>/test` | operations | `test_operation` | `services/api/app/api/v1/operations/routes.py:212` | jwt | success(), error() | tenant_id |
| GET | `/api/reports/compliance` | reports | `compliance_report` | `services/api/app/api/v1/reports/routes.py:35` | jwt | success(), error() | tenant_id |
| GET | `/api/reports/home` | reports | `home_reports` | `services/api/app/api/v1/reports/routes.py:22` | jwt | success(), error() | tenant_id |
| GET | `/api/rules` | rules | `list_rules` | `services/api/app/api/v1/rules/routes.py:50` | jwt | success(), error() | tenant_id |
| POST | `/api/rules` | rules | `create_rule` | `services/api/app/api/v1/rules/routes.py:66` | jwt | success(), error() | tenant_id |
| DELETE | `/api/rules/<rule_id>` | rules | `delete_rule` | `services/api/app/api/v1/rules/routes.py:172` | jwt | success(), error() | tenant_id |
| GET | `/api/rules/<rule_id>` | rules | `get_rule` | `services/api/app/api/v1/rules/routes.py:110` | jwt | success(), error() | tenant_id |
| PUT | `/api/rules/<rule_id>` | rules | `update_rule` | `services/api/app/api/v1/rules/routes.py:127` | jwt | success(), error() | tenant_id |
| POST | `/api/rules/<rule_id>/toggle` | rules | `toggle_rule` | `services/api/app/api/v1/rules/routes.py:196` | jwt | success(), error() | tenant_id |
| GET | `/api/streams/status` | streams | `streams_status` | `services/api/app/api/v1/streams/routes.py:29` | jwt | error(), jsonify | — |
| GET | `/api/training/active-learning/queue` | training | `active_learning_queue` | `services/api/app/api/v1/training/routes.py:378` | jwt | success(), error() | tenant_id |
| GET | `/api/training/coverage-matrix` | training | `get_training_coverage_matrix` | `services/api/app/api/v1/training/routes.py:361` | jwt | success(), error() | tenant_id |
| POST | `/api/training/frames/<frame_id>/accept-suggestions` | training | `accept_suggestions` | `services/api/app/api/v1/training/routes.py:154` | jwt | success(), error() | tenant_id |
| GET | `/api/training/frames/<frame_id>/annotations` | training | `get_annotations` | `services/api/app/api/v1/training/routes.py:133` | jwt | error(), jsonify | tenant_id |
| POST | `/api/training/frames/<frame_id>/annotations` | training | `save_annotations` | `services/api/app/api/v1/training/routes.py:139` | jwt | error(), jsonify | tenant_id |
| GET | `/api/training/frames/<frame_id>/image` | training | `get_frame_image` | `services/api/app/api/v1/training/routes.py:125` | jwt | error(), raw:file, raw:make_response | tenant_id |
| POST | `/api/training/frames/<frame_id>/pre-annotate` | training | `pre_annotate_frame` | `services/api/app/api/v1/training/routes.py:147` | jwt | success(), error() | tenant_id |
| POST | `/api/training/frames/<frame_id>/pre-annotation-review` | training | `pre_annotation_review` | `services/api/app/api/v1/training/routes.py:163` | jwt | success(), error() | tenant_id |
| POST | `/api/training/frames/<frame_id>/validate` | training | `validate_frame` | `services/api/app/api/v1/training/routes.py:328` | jwt | error(), jsonify | tenant_id |
| POST | `/api/training/frames/curation` | training | `curate_frames` | `services/api/app/api/v1/training/routes.py:369` | jwt | success(), error() | tenant_id |
| GET | `/api/training/images` | training | `list_training_images` | `services/api/app/api/v1/training/routes.py:342` | jwt | success(), error() | tenant_id |
| GET | `/api/training/images/facets` | training | `get_training_images_facets` | `services/api/app/api/v1/training/routes.py:355` | jwt | success(), error() | tenant_id |
| POST | `/api/training/images/upload` | training | `upload_training_images` | `services/api/app/api/v1/training/routes.py:348` | jwt | success(), error() | tenant_id |
| GET | `/api/training/jobs` | training | `list_jobs` | `services/api/app/api/v1/training/routes.py:215` | jwt | success(), error() | — |
| POST | `/api/training/jobs` | training | `create_job` | `services/api/app/api/v1/training/routes.py:208` | jwt | success(), error() | tenant_id |
| GET | `/api/training/jobs/<job_id>/progress` | training | `get_job_progress` | `services/api/app/api/v1/training/routes.py:412` | jwt | success() | — |
| GET | `/api/training/jobs/<job_id>/status` | training | `get_job_status` | `services/api/app/api/v1/training/routes.py:221` | jwt | success(), error() | — |
| POST | `/api/training/jobs/<job_id>/stop` | training | `stop_job` | `services/api/app/api/v1/training/routes.py:392` | jwt | success(), error() | — |
| GET | `/api/training/jobs/current/status` | training | `get_current_job_status` | `services/api/app/api/v1/training/routes.py:386` | jwt | success(), error() | — |
| GET | `/api/training/models` | training | `list_models` | `services/api/app/api/v1/training/routes.py:314` | jwt | success(), error() | — |
| POST | `/api/training/models/<model_id>/activate` | training | `activate_model` | `services/api/app/api/v1/training/routes.py:320` | jwt | success(), error() | — |
| GET | `/api/training/scenarios/<model_id>/config` | training | `get_scenario_config` | `services/api/app/api/v1/training/routes.py:446` | jwt | success(), error() | tenant_id |
| PUT | `/api/training/scenarios/<model_id>/config` | training | `upsert_scenario_config` | `services/api/app/api/v1/training/routes.py:440` | jwt | success(), error() | tenant_id |
| GET | `/api/training/videos` | training | `list_videos` | `services/api/app/api/v1/training/routes.py:105` | jwt | success(), error() | — |
| POST | `/api/training/videos` | training | `create_video` | `services/api/app/api/v1/training/routes.py:111` | jwt | success(), error() | — |
| GET | `/api/training/videos/<video_id>/frames` | training | `get_video_frames` | `services/api/app/api/v1/training/routes.py:119` | jwt | error(), jsonify | — |
| GET | `/api/training/videos/<video_id>/validation-stats` | training | `get_validation_stats` | `services/api/app/api/v1/training/routes.py:334` | jwt | error(), jsonify | — |
| GET | `/api/v1/admin/announcements` | admin | `list_announcements` | `services/api/app/api/v1/admin/routes.py:2330` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/announcements` | admin | `create_announcement` | `services/api/app/api/v1/admin/routes.py:2351` | superadmin | success(), error() | tenant_id, public.* |
| DELETE | `/api/v1/admin/announcements/<announcement_id>` | admin | `delete_announcement` | `services/api/app/api/v1/admin/routes.py:2423` | superadmin | success(), error() | public.* |
| PATCH | `/api/v1/admin/announcements/<announcement_id>` | admin | `update_announcement` | `services/api/app/api/v1/admin/routes.py:2398` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/audit-log` | admin | `list_audit_log` | `services/api/app/api/v1/admin/routes.py:2202` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/audit-log/export` | admin | `export_audit_log` | `services/api/app/api/v1/admin/routes.py:2264` | superadmin | error(), raw:Response | tenant_id, public.* |
| PUT | `/api/v1/admin/branding` | branding | `update_branding` | `services/api/app/api/v1/branding/routes.py:182` | admin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/branding/logo` | branding | `upload_logo` | `services/api/app/api/v1/branding/routes.py:230` | admin | success(), error() | tenant_id |
| GET | `/api/v1/admin/branding/tenant/<tenant_id>` | branding | `get_branding_by_tenant` | `services/api/app/api/v1/branding/routes.py:146` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/branding/tenants` | branding | `list_tenants_branding` | `services/api/app/api/v1/branding/routes.py:115` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/cameras/<camera_id>/probe` | admin | `probe_camera` | `services/api/app/api/v1/admin/routes.py:2730` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/cameras/import` | admin | `import_cameras` | `services/api/app/api/v1/admin/routes.py:2623` | superadmin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/cameras/probe-batch` | admin | `probe_cameras_batch` | `services/api/app/api/v1/admin/routes.py:2858` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/changelog` | admin_versions | `list_changelog` | `services/api/app/api/v1/admin/routes_versions.py:372` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/changelog` | admin_versions | `create_changelog_entry` | `services/api/app/api/v1/admin/routes_versions.py:437` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/dashboard` | admin | `get_dashboard` | `services/api/app/api/v1/admin/routes.py:181` | superadmin | success(), error() | tenant_id, public.* |
| DELETE | `/api/v1/admin/demo-events` | demo_events | `remove_demo_events` | `services/api/app/api/v1/admin/demo_events_routes.py:76` | superadmin | success(), error() | tenant_id |
| GET | `/api/v1/admin/demo-events` | demo_events | `demo_events_status` | `services/api/app/api/v1/admin/demo_events_routes.py:30` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/demo-events/seed` | demo_events | `seed_demo_events` | `services/api/app/api/v1/admin/demo_events_routes.py:48` | superadmin | success(), error() | tenant_id |
| GET | `/api/v1/admin/feature-flags` | admin | `list_feature_flags` | `services/api/app/api/v1/admin/routes.py:1893` | superadmin | success(), error() | public.* |
| PATCH | `/api/v1/admin/feature-flags/<flag_key>` | admin | `update_feature_flag` | `services/api/app/api/v1/admin/routes.py:1908` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/feature-flags/tenant/<tenant_id>` | admin | `get_tenant_feature_flags` | `services/api/app/api/v1/admin/routes.py:1981` | superadmin | success(), error() | tenant_id |
| PATCH | `/api/v1/admin/feature-flags/tenant/<tenant_id>` | admin | `update_tenant_feature_flag` | `services/api/app/api/v1/admin/routes.py:2002` | superadmin | success(), error() | tenant_id |
| GET | `/api/v1/admin/health/metrics` | admin | `health_metrics` | `services/api/app/api/v1/admin/routes.py:2510` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/health/platform` | admin | `platform_health` | `services/api/app/api/v1/admin/routes.py:2445` | superadmin | success() | — |
| GET | `/api/v1/admin/integrations/` | admin_integrations | `list_integrations` | `services/api/app/api/v1/admin/integration_routes.py:126` | jwt | success(), error() | tenant_id |
| DELETE | `/api/v1/admin/integrations/<string:integration_type>` | admin_integrations | `delete_integration` | `services/api/app/api/v1/admin/integration_routes.py:220` | jwt | success(), error() | tenant_id |
| PUT | `/api/v1/admin/integrations/<string:integration_type>` | admin_integrations | `upsert_integration` | `services/api/app/api/v1/admin/integration_routes.py:148` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/admin/integrations/<string:integration_type>/test` | admin_integrations | `test_connection` | `services/api/app/api/v1/admin/integration_routes.py:188` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/admin/introspection` | admin_introspection | `introspection` | `services/api/app/api/v1/admin/introspection_routes.py:181` | admin | success(), error() | — |
| GET | `/api/v1/admin/inventory` | admin | `get_inventory` | `services/api/app/api/v1/admin/routes.py:2542` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/modules-registry` | admin | `get_modules_registry` | `services/api/app/api/v1/admin/routes.py:1711` | superadmin | success() | — |
| GET | `/api/v1/admin/modules/catalog` | admin | `modules_catalog` | `services/api/app/api/v1/admin/routes.py:1229` | superadmin | success() | — |
| POST | `/api/v1/admin/observability/collect` | admin_observability | `observability_collect` | `services/api/app/api/v1/admin/observability_routes.py:96` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/observability/edge-fleet` | admin_observability | `observability_edge_fleet` | `services/api/app/api/v1/admin/observability_routes.py:74` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/observability/streams` | admin_observability | `observability_streams` | `services/api/app/api/v1/admin/observability_routes.py:85` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/observability/summary` | admin_observability | `observability_summary` | `services/api/app/api/v1/admin/observability_routes.py:29` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/observability/timeseries` | admin_observability | `observability_timeseries` | `services/api/app/api/v1/admin/observability_routes.py:40` | superadmin | success(), error() | tenant_id |
| GET | `/api/v1/admin/permissions/matrix` | admin | `permissions_matrix` | `services/api/app/api/v1/admin/routes.py:1219` | superadmin | success() | — |
| GET | `/api/v1/admin/permissions/registry` | admin_permissions | `get_permissions_registry` | `services/api/app/api/v1/admin/permission_routes.py:87` | superadmin | success() | — |
| GET | `/api/v1/admin/plans` | admin | `list_plans` | `services/api/app/api/v1/admin/routes.py:1722` | superadmin | success(), error() | — |
| POST | `/api/v1/admin/plans` | admin | `create_plan` | `services/api/app/api/v1/admin/routes.py:1754` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/plans/<plan_id>` | admin | `get_plan` | `services/api/app/api/v1/admin/routes.py:1737` | superadmin | success(), error() | — |
| PATCH | `/api/v1/admin/plans/<plan_id>` | admin | `update_plan` | `services/api/app/api/v1/admin/routes.py:1819` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/plans/<plan_id>/tenants` | admin | `get_plan_tenants` | `services/api/app/api/v1/admin/routes.py:1865` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/software-channels` | admin | `list_software_channels` | `services/api/app/api/v1/admin/routes.py:1937` | superadmin | success(), error() | — |
| PUT | `/api/v1/admin/software-channels/<channel>` | admin | `set_software_channel_target` | `services/api/app/api/v1/admin/routes.py:1950` | superadmin | success(), error() | — |
| POST | `/api/v1/admin/tenant-context/renew` | admin_tenant_context | `renew_tenant_context` | `services/api/app/api/v1/admin/tenant_context_routes.py:225` | superadmin(404) | success(), error() | tenant_schema, tenant_id |
| GET | `/api/v1/admin/tenant-context/tenants` | admin_tenant_context | `list_available_tenants` | `services/api/app/api/v1/admin/tenant_context_routes.py:98` | superadmin(404) | success(), error() | public.* |
| POST | `/api/v1/admin/tenant-context/tenants/<tenant_id>/assume` | admin_tenant_context | `assume_tenant_context` | `services/api/app/api/v1/admin/tenant_context_routes.py:130` | superadmin(404) | success(), error() | tenant_schema, tenant_id, public.* |
| GET | `/api/v1/admin/tenants` | admin | `list_tenants` | `services/api/app/api/v1/admin/routes.py:263` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/tenants` | admin | `create_tenant` | `services/api/app/api/v1/admin/routes.py:300` | superadmin | success(), error() | tenant_schema, tenant_id, public.* |
| GET | `/api/v1/admin/tenants/<tenant_id>` | admin | `get_tenant` | `services/api/app/api/v1/admin/routes.py:371` | superadmin | success(), error() | tenant_id, public.* |
| PATCH | `/api/v1/admin/tenants/<tenant_id>` | admin | `update_tenant` | `services/api/app/api/v1/admin/routes.py:461` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/tenants/<tenant_id>/branding` | admin_branding | `get_tenant_branding` | `services/api/app/api/v1/admin/branding_routes.py:74` | superadmin | success(), error() | tenant_id, public.* |
| PUT | `/api/v1/admin/tenants/<tenant_id>/branding` | admin_branding | `update_tenant_branding` | `services/api/app/api/v1/admin/branding_routes.py:105` | superadmin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/tenants/<tenant_id>/branding/logo` | admin_branding | `upload_tenant_branding_logo` | `services/api/app/api/v1/admin/branding_routes.py:147` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/tenants/<tenant_id>/overview` | admin | `tenant_overview` | `services/api/app/api/v1/admin/routes.py:633` | superadmin | success(), error() | tenant_id |
| GET | `/api/v1/admin/tenants/<tenant_id>/plan-history` | admin | `tenant_plan_history` | `services/api/app/api/v1/admin/routes.py:695` | superadmin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/tenants/<tenant_id>/reactivate` | admin | `reactivate_tenant` | `services/api/app/api/v1/admin/routes.py:607` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/tenants/<tenant_id>/suspend` | admin | `suspend_tenant` | `services/api/app/api/v1/admin/routes.py:554` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/test-console/evidence` | test_console | `list_evidence` | `services/api/app/api/v1/admin/test_console_routes.py:386` | jwt+admin | success(), error() | — |
| POST | `/api/v1/admin/test-console/harness/start` | test_console | `harness_start` | `services/api/app/api/v1/admin/test_console_routes.py:202` | jwt+admin | success(), error() | tenant_id |
| GET | `/api/v1/admin/test-console/harness/status` | test_console | `harness_status` | `services/api/app/api/v1/admin/test_console_routes.py:321` | jwt+admin | success() | tenant_id |
| POST | `/api/v1/admin/test-console/harness/stop` | test_console | `harness_stop` | `services/api/app/api/v1/admin/test_console_routes.py:285` | jwt+admin | success(), error() | — |
| GET | `/api/v1/admin/test-console/models` | test_console | `list_models` | `services/api/app/api/v1/admin/test_console_routes.py:372` | jwt+admin | success(), error() | — |
| POST | `/api/v1/admin/test-console/seed` | test_console | `seed_test_tenant` | `services/api/app/api/v1/admin/test_console_routes.py:411` | jwt+admin | success() | tenant_id |
| POST | `/api/v1/admin/test-console/start` | admin_test_console | `test_console_start` | `services/api/app/api/v1/admin/routes_test_console.py:125` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/test-console/status` | admin_test_console | `test_console_status` | `services/api/app/api/v1/admin/routes_test_console.py:81` | superadmin | success(), error() | — |
| POST | `/api/v1/admin/test-console/stop` | admin_test_console | `test_console_stop` | `services/api/app/api/v1/admin/routes_test_console.py:300` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/tickets` | admin | `list_tickets` | `services/api/app/api/v1/admin/routes.py:2039` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/tickets/<ticket_id>` | admin | `get_ticket` | `services/api/app/api/v1/admin/routes.py:2106` | superadmin | success(), error() | tenant_id, public.* |
| PATCH | `/api/v1/admin/tickets/<ticket_id>` | admin | `update_ticket` | `services/api/app/api/v1/admin/routes.py:2173` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/tickets/<ticket_id>/reply` | admin | `reply_ticket` | `services/api/app/api/v1/admin/routes.py:2139` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/tickets/stats` | admin | `ticket_stats` | `services/api/app/api/v1/admin/routes.py:2083` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/training-approvals` | admin | `list_training_approvals` | `services/api/app/api/v1/admin/routes.py:1244` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/training-approvals/<approval_id>` | admin | `get_training_approval` | `services/api/app/api/v1/admin/routes.py:1295` | superadmin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/training-approvals/<approval_id>/approve` | admin | `approve_training` | `services/api/app/api/v1/admin/routes.py:1341` | superadmin | success(), error() | tenant_schema, tenant_id, public.* |
| POST | `/api/v1/admin/training-approvals/<approval_id>/reject` | admin | `reject_training` | `services/api/app/api/v1/admin/routes.py:1392` | superadmin | success(), error() | tenant_schema, tenant_id, public.* |
| GET | `/api/v1/admin/users` | admin | `list_users` | `services/api/app/api/v1/admin/routes.py:719` | superadmin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/users` | admin | `create_user` | `services/api/app/api/v1/admin/routes.py:818` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/users/<user_id>` | admin | `get_user` | `services/api/app/api/v1/admin/routes.py:779` | superadmin | success(), error() | tenant_id, public.* |
| PATCH | `/api/v1/admin/users/<user_id>` | admin | `update_user` | `services/api/app/api/v1/admin/routes.py:909` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/users/<user_id>/deactivate` | admin | `deactivate_user` | `services/api/app/api/v1/admin/routes.py:955` | superadmin | success(), error() | tenant_id, public.* |
| POST | `/api/v1/admin/users/<user_id>/force-password-reset` | admin | `force_password_reset` | `services/api/app/api/v1/admin/routes.py:1058` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/users/<user_id>/impersonate` | admin_impersonation | `impersonate_user` | `services/api/app/api/v1/admin/impersonation_routes.py:106` | superadmin | success(), error() | tenant_schema, tenant_id |
| GET | `/api/v1/admin/users/<user_id>/permissions` | admin_permissions | `get_user_permissions` | `services/api/app/api/v1/admin/permission_routes.py:97` | superadmin | success(), error() | — |
| PUT | `/api/v1/admin/users/<user_id>/permissions` | admin_permissions | `put_user_permissions` | `services/api/app/api/v1/admin/permission_routes.py:113` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/users/<user_id>/reactivate` | admin | `reactivate_user` | `services/api/app/api/v1/admin/routes.py:1011` | superadmin | success(), error() | tenant_id |
| POST | `/api/v1/admin/users/<user_id>/reset-password` | admin | `reset_password` | `services/api/app/api/v1/admin/routes.py:1096` | superadmin | success(), error() | tenant_id |
| DELETE | `/api/v1/admin/users/<user_id>/sessions` | admin | `revoke_user_sessions` | `services/api/app/api/v1/admin/routes.py:1170` | superadmin | success(), error() | tenant_id, public.* |
| GET | `/api/v1/admin/users/<user_id>/sessions` | admin | `get_user_sessions` | `services/api/app/api/v1/admin/routes.py:1150` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/versions` | admin_versions | `list_versions` | `services/api/app/api/v1/admin/routes_versions.py:85` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/versions` | admin_versions | `create_version` | `services/api/app/api/v1/admin/routes_versions.py:119` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/versions/<version_id>` | admin_versions | `get_version` | `services/api/app/api/v1/admin/routes_versions.py:218` | superadmin | success(), error() | public.* |
| POST | `/api/v1/admin/versions/<version_id>/rollback` | admin_versions | `rollback_version` | `services/api/app/api/v1/admin/routes_versions.py:261` | superadmin | success(), error() | public.* |
| GET | `/api/v1/admin/workers` | admin | `list_workers` | `services/api/app/api/v1/admin/routes.py:1445` | superadmin | success(), error() | — |
| GET | `/api/v1/admin/workers/<tenant_schema>` | admin | `get_worker_detail` | `services/api/app/api/v1/admin/routes.py:1460` | superadmin | success(), error() | tenant_schema, tenant_id, public.* |
| GET | `/api/v1/admin/workers/<tenant_schema>/metrics` | admin | `get_worker_metrics_history` | `services/api/app/api/v1/admin/routes.py:1520` | superadmin | success(), error() | tenant_schema, public.* |
| POST | `/api/v1/admin/workers/<tenant_schema>/restart` | admin | `restart_worker` | `services/api/app/api/v1/admin/routes.py:1500` | superadmin | success(), error() | tenant_schema |
| POST | `/api/v1/admin/workers/heartbeat` | admin | `worker_heartbeat` | `services/api/app/api/v1/admin/routes.py:1557` | worker_secret(inline) | success(), error() | tenant_schema, tenant_id |
| GET | `/api/v1/announcements` | client_announcements | `get_client_announcements` | `services/api/app/api/v1/admin/routes.py:2981` | jwt | success(), error() | tenant_id, public.* |
| POST | `/api/v1/announcements/<announcement_id>/read` | client_announcements | `mark_announcement_read` | `services/api/app/api/v1/admin/routes.py:3011` | jwt | success(), error() | tenant_id, public.* |
| PATCH | `/api/v1/cameras/<camera_id>/config` | cameras_v1 | `patch_camera_config` | `services/api/app/api/v1/cameras/config_handler.py:80` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/cameras/<camera_id>/effective-model` | cameras_v1 | `get_effective_model` | `services/api/app/api/v1/cameras/model_handlers.py:319` | jwt | success(), error() | tenant_schema, tenant_id |
| GET | `/api/v1/cameras/<camera_id>/health-context` | cameras_v1 | `get_camera_health_context` | `services/api/app/api/v1/cameras/health_context_handler.py:57` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/cameras/<camera_id>/model-config` | cameras_v1 | `get_camera_model_config` | `services/api/app/api/v1/cameras/model_config_handlers.py:91` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/cameras/<camera_id>/model-config` | cameras_v1 | `post_camera_model_config` | `services/api/app/api/v1/cameras/model_config_handlers.py:112` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/cameras/<camera_id>/model-config/history` | cameras_v1 | `get_camera_model_config_history` | `services/api/app/api/v1/cameras/model_config_handlers.py:173` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/cameras/<camera_id>/model-config/rollback` | cameras_v1 | `post_camera_model_config_rollback` | `services/api/app/api/v1/cameras/model_config_handlers.py:197` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/cameras/<camera_id>/scenario` | scenarios | `get_camera_scenario` | `services/api/app/api/v1/scenarios/routes.py:44` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/cameras/probe` | cameras_v1 | `probe_camera` | `services/api/app/api/v1/cameras/probe_handler.py:171` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/counting/sessions` | counting_v1 | `list_sessions` | `services/api/app/api/v1/counting/routes.py:78` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/counting/sessions` | counting_v1 | `start_session` | `services/api/app/api/v1/counting/routes.py:51` | jwt | success(), error() | tenant_id |
| DELETE | `/api/v1/counting/sessions/<session_id>` | counting_v1 | `stop_session` | `services/api/app/api/v1/counting/routes.py:125` | jwt | success(), error() | tenant_id |
| PATCH | `/api/v1/counting/sessions/<session_id>` | counting_v1 | `update_session` | `services/api/app/api/v1/counting/routes.py:92` | jwt | success(), error() | tenant_id |
| PATCH | `/api/v1/counting/sessions/<session_id>/plate` | counting_v1 | `update_plate` | `services/api/app/api/v1/counting/routes.py:167` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/counting/sessions/<session_id>/stats` | counting_v1 | `session_stats` | `services/api/app/api/v1/counting/routes.py:144` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/counting/sessions/plates` | counting_v1 | `list_sessions_with_plates` | `services/api/app/api/v1/counting/routes.py:240` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/counting/sessions/validation-report` | counting_v1 | `validation_report` | `services/api/app/api/v1/counting/routes.py:267` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/dashboard/detections` | dashboard | `get_detection_stats` | `services/api/app/api/v1/dashboard/routes.py:164` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/dashboard/edge-telemetry` | dashboard_edge | `get_edge_telemetry` | `services/api/app/api/v1/dashboard_edge/routes.py:154` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/dashboard/edge-telemetry` | dashboard_edge | `ingest_edge_telemetry` | `services/api/app/api/v1/dashboard_edge/routes.py:105` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/dashboard/stats` | dashboard | `get_stats` | `services/api/app/api/v1/dashboard/routes.py:31` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/dashboard/training-metrics` | dashboard_edge | `get_training_metrics` | `services/api/app/api/v1/dashboard_edge/routes.py:132` | jwt | success() | tenant_id |
| POST | `/api/v1/dashboard/training-metrics` | dashboard_edge | `ingest_training_metrics` | `services/api/app/api/v1/dashboard_edge/routes.py:64` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/dashboard/training-metrics/models` | dashboard_edge | `list_training_models` | `services/api/app/api/v1/dashboard_edge/routes.py:143` | jwt | success() | tenant_id |
| GET | `/api/v1/dataset-versions/<version_id>` | datasets | `get_dataset_version` | `services/api/app/api/v1/datasets/routes.py:185` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/datasets` | datasets | `list_datasets` | `services/api/app/api/v1/datasets/routes.py:46` | jwt | success() | tenant_id |
| POST | `/api/v1/datasets` | datasets | `create_dataset` | `services/api/app/api/v1/datasets/routes.py:57` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/datasets/<dataset_id>` | datasets | `get_dataset` | `services/api/app/api/v1/datasets/routes.py:82` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/datasets/<dataset_id>/versions` | datasets | `create_dataset_version` | `services/api/app/api/v1/datasets/routes.py:104` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/edge/cameras/<camera_id>/snapshot` | edge | `upload_camera_snapshot` | `services/api/app/api/v1/edge/routes.py:786` | device_scope:'snapshot:write' | success(), error() | tenant_id |
| GET | `/api/v1/edge/commands` | edge_commands | `list_commands` | `services/api/app/api/v1/edge_commands/routes.py:174` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/edge/commands` | edge_commands | `create_command` | `services/api/app/api/v1/edge_commands/routes.py:103` | jwt | success(), error() | tenant_id |
| PATCH | `/api/v1/edge/commands/<command_id>` | edge_commands | `update_command_status` | `services/api/app/api/v1/edge_commands/routes.py:148` | device_scope:'commands:write' | success(), error() | tenant_id |
| GET | `/api/v1/edge/commands/pending` | edge_commands | `poll_pending_commands` | `services/api/app/api/v1/edge_commands/routes.py:134` | device_scope:'commands:read' | success(), error() | — |
| GET | `/api/v1/edge/config/poll` | edge | `poll_edge_config` | `services/api/app/api/v1/edge/routes.py:567` | device_scope:'config:read' | success(), error(), jsonify, raw:make_response | tenant_id |
| POST | `/api/v1/edge/devices/<device_pk>/revoke` | edge | `revoke_device` | `services/api/app/api/v1/edge/routes.py:1535` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/edge/enroll` | edge | `enroll_device` | `services/api/app/api/v1/edge/routes.py:1345` | enrollment_token(inline) | success(), error() | tenant_id |
| POST | `/api/v1/edge/enrollment-tokens/<token_id>/revoke` | edge | `revoke_enrollment_token` | `services/api/app/api/v1/edge/routes.py:1304` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/events` | edge_events | `list_events` | `services/api/app/api/v1/edge_events/routes.py:74` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/edge/events/ingest` | edge_events | `ingest_events` | `services/api/app/api/v1/edge_events/routes.py:32` | device_scope:'events:write' | success(), error() | tenant_id |
| POST | `/api/v1/edge/frames` | edge | `upload_edge_frame` | `services/api/app/api/v1/edge/routes.py:666` | device_scope:'frames:write' | success(), error() | tenant_id |
| POST | `/api/v1/edge/heartbeat` | edge | `ingest_heartbeat` | `services/api/app/api/v1/edge/routes.py:451` | device_token(inline) | success(), error() | tenant_id |
| POST | `/api/v1/edge/live-view/<camera_id>/segment` | edge | `upload_live_view_segment` | `services/api/app/api/v1/edge/routes.py:867` | device_scope:'stream:write' | success(), error() | tenant_id |
| GET | `/api/v1/edge/live-view/wanted` | edge | `list_live_view_wanted` | `services/api/app/api/v1/edge/routes.py:932` | device_scope:'stream:write' | success(), error() | tenant_id |
| GET | `/api/v1/edge/overview` | edge | `get_fleet_overview` | `services/api/app/api/v1/edge/routes.py:1027` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites` | edge | `list_sites` | `services/api/app/api/v1/edge/routes.py:1114` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/edge/sites` | edge | `create_site` | `services/api/app/api/v1/edge/routes.py:1085` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites/<site_id>` | edge | `get_site_detail` | `services/api/app/api/v1/edge/routes.py:1132` | jwt | success(), error() | tenant_id |
| PATCH | `/api/v1/edge/sites/<site_id>` | edge | `update_site` | `services/api/app/api/v1/edge/routes.py:1166` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites/<site_id>/devices` | edge | `list_site_devices` | `services/api/app/api/v1/edge/routes.py:1503` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites/<site_id>/enrollment-tokens` | edge | `list_enrollment_tokens` | `services/api/app/api/v1/edge/routes.py:1272` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/edge/sites/<site_id>/enrollment-tokens` | edge | `create_enrollment_token` | `services/api/app/api/v1/edge/routes.py:1224` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites/<site_id>/heartbeat-summary` | edge | `get_heartbeat_summary` | `services/api/app/api/v1/edge/routes.py:1440` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites/<site_id>/heartbeats` | edge | `list_site_heartbeats` | `services/api/app/api/v1/edge/routes.py:1400` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/sites/health` | edge | `get_sites_health` | `services/api/app/api/v1/edge/routes.py:971` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/edge/software/target` | edge | `get_software_target` | `services/api/app/api/v1/edge/routes.py:630` | device_scope:'config:read' | success(), error() | tenant_id |
| GET | `/api/v1/events/search` | events | `search_events` | `services/api/app/api/v1/events/routes.py:105` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/events/summary` | events | `events_summary` | `services/api/app/api/v1/events/routes.py:204` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/events/timeline` | events | `events_timeline` | `services/api/app/api/v1/events/routes.py:156` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/feedback` | feedback | `list_feedback` | `services/api/app/api/v1/feedback/routes.py:54` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/feedback` | feedback | `create_feedback` | `services/api/app/api/v1/feedback/routes.py:28` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/feedback/summary` | feedback | `feedback_summary` | `services/api/app/api/v1/feedback/routes.py:77` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/health` | health | `health_check` | `services/api/app/api/v1/health/routes.py:34` | NONE(verificar) | jsonify | — |
| GET | `/api/v1/health/metrics` | health | `health_metrics` | `services/api/app/api/v1/health/routes.py:293` | jwt | jsonify | tenant_schema |
| POST | `/api/v1/impersonation/stop` | impersonation | `stop_impersonation` | `services/api/app/api/v1/admin/impersonation_routes.py:218` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/models` | models_rollout | `list_registry_models` | `services/api/app/api/v1/models/registry_handlers.py:141` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/models/<model_id>` | models_rollout | `get_registry_model` | `services/api/app/api/v1/models/registry_handlers.py:176` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/models/<model_id>/activate` | models_rollout | `activate_registry_model` | `services/api/app/api/v1/models/registry_handlers.py:242` | jwt | success(), error() | tenant_schema, tenant_id |
| GET | `/api/v1/models/<model_id>/drift` | models_rollout | `get_registry_model_drift` | `services/api/app/api/v1/models/registry_handlers.py:420` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/models/<model_id>/eval` | models_rollout | `get_registry_model_eval` | `services/api/app/api/v1/models/registry_handlers.py:344` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/models/<model_id>/evaluate` | models_rollout | `evaluate_registry_model` | `services/api/app/api/v1/models/registry_handlers.py:374` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/models/<model_id>/pin` | models_rollout | `pin_model_version` | `services/api/app/api/v1/models/handlers.py:53` | jwt | success(), error() | tenant_schema |
| GET | `/api/v1/models/active` | models_rollout | `get_active_manifest` | `services/api/app/api/v1/models/handlers.py:28` | jwt | success(), error() | tenant_schema |
| GET | `/api/v1/monitoring/commands/<command_id>` | monitoring | `get_command` | `services/api/app/api/v1/monitoring/routes.py:343` | jwt+superadmin(404) | success(), error() | — |
| GET | `/api/v1/monitoring/sites` | monitoring | `list_sites` | `services/api/app/api/v1/monitoring/routes.py:205` | jwt+superadmin(404) | success(), error() | public.* |
| GET | `/api/v1/monitoring/sites/<site_id>/detections` | monitoring | `site_detections` | `services/api/app/api/v1/monitoring/routes.py:423` | jwt+superadmin(404) | success(), error() | — |
| POST | `/api/v1/monitoring/sites/<site_id>/logtail` | monitoring | `logtail_site` | `services/api/app/api/v1/monitoring/routes.py:305` | jwt+superadmin(404) | success(), error() | tenant_id |
| POST | `/api/v1/monitoring/sites/<site_id>/query` | monitoring | `query_site` | `services/api/app/api/v1/monitoring/routes.py:237` | jwt+superadmin(404) | success(), error() | tenant_id |
| POST | `/api/v1/monitoring/sites/<site_id>/snapshot` | monitoring | `snapshot_site` | `services/api/app/api/v1/monitoring/routes.py:285` | jwt+superadmin(404) | success(), error() | tenant_id |
| GET | `/api/v1/monitoring/sites/<site_id>/thresholds` | monitoring | `get_thresholds` | `services/api/app/api/v1/monitoring/routes.py:365` | jwt+superadmin(404) | success(), error() | — |
| PUT | `/api/v1/monitoring/sites/<site_id>/thresholds` | monitoring | `put_thresholds` | `services/api/app/api/v1/monitoring/routes.py:385` | jwt+superadmin(404) | success(), error() | tenant_id |
| POST | `/api/v1/monofatura/pieces/<piece_id>/scan` | monofatura | `scan_piece` | `services/api/app/api/v1/monofatura/routes.py:37` | jwt | success(), error() | tenant_schema |
| POST | `/api/v1/monofatura/pieces/<piece_id>/stages/<stage>/complete` | monofatura | `complete_stage` | `services/api/app/api/v1/monofatura/routes.py:52` | jwt | success(), error() | tenant_schema |
| GET | `/api/v1/monofatura/sessions` | monofatura | `list_sessions` | `services/api/app/api/v1/monofatura/routes.py:77` | jwt | success(), error() | tenant_schema |
| GET | `/api/v1/notifications/channels` | notifications | `list_channels` | `services/api/app/api/v1/notifications/routes.py:33` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/notifications/channels` | notifications | `create_channel` | `services/api/app/api/v1/notifications/routes.py:45` | jwt | success(), error() | tenant_id |
| DELETE | `/api/v1/notifications/channels/<channel_id>` | notifications | `delete_channel` | `services/api/app/api/v1/notifications/routes.py:95` | jwt | success(), error() | tenant_id |
| PATCH | `/api/v1/notifications/channels/<channel_id>` | notifications | `update_channel` | `services/api/app/api/v1/notifications/routes.py:72` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/permissions/mine` | my_permissions | `get_my_permissions` | `services/api/app/api/v1/admin/permission_routes.py:200` | jwt | success() | tenant_id |
| GET | `/api/v1/quality/andon/<camera_id>` | quality | `get_andon_data` | `services/api/app/api/v1/quality/routes.py:703` | ip_allowlist(inline) | success(), error() | tenant_schema, public.* |
| PUT | `/api/v1/quality/annotation-frames/<frame_id>/annotations` | quality | `save_annotations` | `services/api/app/api/v1/quality/routes.py:924` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/annotation-frames/<frame_id>/url` | quality | `get_frame_url` | `services/api/app/api/v1/quality/routes.py:887` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/cameras` | quality | `list_quality_cameras` | `services/api/app/api/v1/quality/routes.py:134` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/cameras/<camera_id>/assign` | quality | `assign_camera` | `services/api/app/api/v1/quality/routes.py:203` | jwt(helper) | success(), error() | tenant_schema |
| PATCH | `/api/v1/quality/cameras/<camera_id>/config` | quality | `update_camera_config` | `services/api/app/api/v1/quality/routes.py:265` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/cameras/<camera_id>/toggle-setup-mode` | quality | `toggle_setup_mode` | `services/api/app/api/v1/quality/routes.py:312` | jwt(helper) | success(), error() | tenant_schema |
| DELETE | `/api/v1/quality/cameras/<camera_id>/unassign` | quality | `unassign_camera` | `services/api/app/api/v1/quality/routes.py:239` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/cameras/available` | quality | `list_available_cameras` | `services/api/app/api/v1/quality/routes.py:175` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/cep/<camera_id>` | quality | `get_cep_data` | `services/api/app/api/v1/quality/routes.py:1267` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/classes` | quality | `get_classes` | `services/api/app/api/v1/quality/routes.py:110` | jwt(helper) | success(), error() | — |
| GET | `/api/v1/quality/dashboard/stations` | quality | `dashboard_stations` | `services/api/app/api/v1/quality/routes.py:1944` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/dashboard/summary` | quality | `dashboard_summary` | `services/api/app/api/v1/quality/routes.py:1926` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/defect-categories` | quality | `get_defect_categories` | `services/api/app/api/v1/quality/routes.py:120` | jwt(helper) | success(), error() | — |
| POST | `/api/v1/quality/demo/seed` | quality | `demo_seed` | `services/api/app/api/v1/quality/routes.py:1966` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/pieces` | quality | `gate_list_pieces` | `services/api/app/api/v1/quality/routes.py:1562` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/pieces` | quality | `gate_create_piece` | `services/api/app/api/v1/quality/routes.py:1534` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/pieces/<piece_id>` | quality | `gate_get_piece` | `services/api/app/api/v1/quality/routes.py:1591` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/false-positive` | quality | `gate_mark_false_positive` | `services/api/app/api/v1/quality/routes.py:1685` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/identify` | quality | `gate_identify_piece` | `services/api/app/api/v1/quality/routes.py:1611` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/inspect` | quality | `gate_start_inspection` | `services/api/app/api/v1/quality/routes.py:1632` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/release-to-bench-b` | quality | `gate_release_to_bench_b` | `services/api/app/api/v1/quality/routes.py:1705` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/pieces/<piece_id>/result` | quality | `gate_process_inspection_result` | `services/api/app/api/v1/quality/routes.py:1652` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/reworks` | quality | `gate_list_reworks` | `services/api/app/api/v1/quality/routes.py:1725` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/reworks` | quality | `gate_start_rework` | `services/api/app/api/v1/quality/routes.py:1749` | jwt(helper) | success(), error() | tenant_schema |
| PATCH | `/api/v1/quality/gate/reworks/<rework_id>/complete` | quality | `gate_complete_rework` | `services/api/app/api/v1/quality/routes.py:1781` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/stations` | quality | `gate_list_stations` | `services/api/app/api/v1/quality/routes.py:1799` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/gate/stations` | quality | `gate_create_station` | `services/api/app/api/v1/quality/routes.py:1835` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/stations/<station_code>` | quality | `gate_get_station_status` | `services/api/app/api/v1/quality/routes.py:1817` | jwt(helper) | success(), error() | tenant_schema |
| PUT | `/api/v1/quality/gate/stations/<station_code>` | quality | `gate_update_station` | `services/api/app/api/v1/quality/routes.py:1861` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/stats/overview` | quality | `gate_stats_overview` | `services/api/app/api/v1/quality/routes.py:1890` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/gate/stats/rework` | quality | `gate_stats_rework` | `services/api/app/api/v1/quality/routes.py:1908` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections` | quality | `list_inspections` | `services/api/app/api/v1/quality/routes.py:348` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections/<inspection_id>` | quality | `get_inspection` | `services/api/app/api/v1/quality/routes.py:524` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections/<inspection_id>/annotation-frames` | quality | `list_annotation_frames` | `services/api/app/api/v1/quality/routes.py:844` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections/<inspection_id>/annotation-progress` | quality | `get_annotation_progress` | `services/api/app/api/v1/quality/routes.py:974` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections/<inspection_id>/clip-url` | quality | `get_clip_url` | `services/api/app/api/v1/quality/routes.py:556` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/inspections/<inspection_id>/create-training-job` | quality | `create_job_from_inspection` | `services/api/app/api/v1/quality/routes.py:1006` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections/<inspection_id>/evidence-url` | quality | `get_evidence_url` | `services/api/app/api/v1/quality/routes.py:600` | jwt(helper) | success(), error() | tenant_schema |
| PATCH | `/api/v1/quality/inspections/<inspection_id>/feedback` | quality | `submit_feedback` | `services/api/app/api/v1/quality/routes.py:642` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/inspections/<inspection_id>/prepare-annotation` | quality | `prepare_annotation` | `services/api/app/api/v1/quality/routes.py:827` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/inspections/summary` | quality | `get_inspections_summary` | `services/api/app/api/v1/quality/routes.py:442` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/reference-snapshots/<camera_id>` | quality | `get_reference_snapshots` | `services/api/app/api/v1/quality/routes.py:1232` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/reports/shift` | quality | `get_shift_report` | `services/api/app/api/v1/quality/routes.py:1348` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/reports/shift/pdf` | quality | `get_shift_report_pdf` | `services/api/app/api/v1/quality/routes.py:1432` | jwt(helper) | error(), raw:make_response | tenant_schema |
| GET | `/api/v1/quality/training/jobs` | quality | `list_training_jobs` | `services/api/app/api/v1/quality/routes.py:1098` | jwt(helper) | success(), error() | tenant_schema |
| POST | `/api/v1/quality/training/jobs` | quality | `create_training_job` | `services/api/app/api/v1/quality/routes.py:1056` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/training/jobs/<job_id>` | quality | `get_training_job` | `services/api/app/api/v1/quality/routes.py:1128` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/quality/training/jobs/<job_id>/progress` | quality | `get_training_progress` | `services/api/app/api/v1/quality/routes.py:1153` | jwt(helper) | success(), error() | — |
| POST | `/api/v1/quality/training/models/<model_id>/activate` | quality | `activate_model` | `services/api/app/api/v1/quality/routes.py:1177` | jwt(helper) | success(), error() | tenant_schema |
| GET | `/api/v1/recorders` | recorders | `list_recorders` | `services/api/app/api/v1/recorders/routes.py:42` | jwt | success() | tenant_id |
| POST | `/api/v1/recorders` | recorders | `create_recorder` | `services/api/app/api/v1/recorders/routes.py:50` | jwt | success() | tenant_id |
| DELETE | `/api/v1/recorders/<recorder_id>` | recorders | `delete_recorder` | `services/api/app/api/v1/recorders/routes.py:89` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/recorders/<recorder_id>` | recorders | `get_recorder` | `services/api/app/api/v1/recorders/routes.py:63` | jwt | success(), error() | tenant_id |
| PUT | `/api/v1/recorders/<recorder_id>` | recorders | `update_recorder` | `services/api/app/api/v1/recorders/routes.py:76` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/recorders/<recorder_id>/extract-frames` | recorders | `extract_frames` | `services/api/app/api/v1/recorders/routes.py:162` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/recorders/<recorder_id>/recordings` | recorders | `get_recordings` | `services/api/app/api/v1/recorders/routes.py:113` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/recorders/<recorder_id>/test` | recorders | `test_recorder_connection` | `services/api/app/api/v1/recorders/routes.py:101` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/reports/export` | dashboard | `export_report` | `services/api/app/api/v1/dashboard/routes.py:195` | jwt | error(), raw:file | tenant_id |
| GET | `/api/v1/scenarios/operation-types` | scenarios | `list_scenario_operation_types` | `services/api/app/api/v1/scenarios/routes.py:102` | jwt | success() | — |
| GET | `/api/v1/site-gateways/<site_id>` | site_gateways | `get_gateway` | `services/api/app/api/v1/site_gateways/routes.py:32` | jwt | success(), error() | tenant_id |
| PUT | `/api/v1/site-gateways/<site_id>` | site_gateways | `upsert_gateway` | `services/api/app/api/v1/site_gateways/routes.py:46` | jwt | success(), error() | tenant_id |
| PATCH | `/api/v1/site-gateways/<site_id>/status` | site_gateways | `update_gateway_status` | `services/api/app/api/v1/site_gateways/routes.py:73` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/storage/health` | storage | `storage_health` | `services/api/app/api/v1/storage/routes.py:23` | jwt(inline) | success(), error() | — |
| POST | `/api/v1/storage/test-upload` | storage | `test_upload` | `services/api/app/api/v1/storage/routes.py:121` | jwt | success(), error() | — |
| GET | `/api/v1/tenant/branding` | branding | `get_tenant_branding` | `services/api/app/api/v1/branding/routes.py:60` | jwt(inline) | success() | tenant_id, public.* |
| GET | `/api/v1/tenant/retention` | retention | `get_tenant_retention` | `services/api/app/api/v1/retention/routes.py:36` | jwt | success(), error() | tenant_id, public.* |
| PUT | `/api/v1/tenant/retention` | retention | `put_tenant_retention` | `services/api/app/api/v1/retention/routes.py:69` | jwt | success(), error() | tenant_id, public.* |
| POST | `/api/v1/training/jobs/<job_id>/progress-callback` | training | `training_progress_callback` | `services/api/app/api/v1/training/routes.py:404` | callback_secret(inline)+shared_secret(compare_digest) | success(), error() | — |
| GET | `/api/v1/training/propagation/jobs` | training | `list_propagation_jobs` | `services/api/app/api/v1/training/routes.py:243` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/training/propagation/jobs` | training | `create_propagation_job` | `services/api/app/api/v1/training/routes.py:236` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/training/propagation/jobs/<job_id>` | training | `get_propagation_job` | `services/api/app/api/v1/training/routes.py:249` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/training/propagation/jobs/<job_id>/callback` | training | `propagation_callback` | `services/api/app/api/v1/training/routes.py:258` | callback_secret(inline)+shared_secret(compare_digest) | success(), error() | tenant_id |
| GET | `/api/v1/training/propagation/preflight` | training | `preflight_propagation` | `services/api/app/api/v1/training/routes.py:229` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/training/search/jobs` | training | `list_search_jobs` | `services/api/app/api/v1/training/routes.py:282` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/training/search/jobs` | training | `create_search_job` | `services/api/app/api/v1/training/routes.py:275` | jwt | success(), error() | tenant_id |
| GET | `/api/v1/training/search/jobs/<job_id>` | training | `get_search_job` | `services/api/app/api/v1/training/routes.py:288` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/training/search/jobs/<job_id>/callback` | training | `search_callback` | `services/api/app/api/v1/training/routes.py:304` | callback_secret(inline)+shared_secret(compare_digest) | success(), error() | — |
| POST | `/api/v1/training/search/jobs/<job_id>/promote` | training | `promote_search_findings` | `services/api/app/api/v1/training/routes.py:294` | jwt | success(), error() | tenant_id |
| POST | `/api/v1/training/search/preflight` | training | `preflight_search` | `services/api/app/api/v1/training/routes.py:268` | jwt | success(), error() | tenant_id |
| DELETE | `/api/v1/videos/<video_id>` | videos | `delete_video` | `services/api/app/api/v1/videos/routes.py:274` | jwt | success(), error() | — |
| GET | `/api/v1/videos/<video_id>/blob` | videos | `get_video_blob` | `services/api/app/api/v1/videos/routes.py:468` | jwt | error(), raw:stream, raw:Response | — |
| GET | `/api/v1/videos/<video_id>/download-url` | videos | `get_download_url` | `services/api/app/api/v1/videos/routes.py:395` | jwt | success(), error() | — |
| POST | `/api/v1/videos/<video_id>/extract` | videos | `trigger_extraction` | `services/api/app/api/v1/videos/routes.py:197` | jwt | success(), error() | — |
| POST | `/api/v1/videos/<video_id>/finalize-extraction` | videos | `finalize_extraction` | `services/api/app/api/v1/videos/routes.py:453` | jwt | success(), error() | — |
| POST | `/api/v1/videos/<video_id>/frames/upload` | videos | `upload_frame` | `services/api/app/api/v1/videos/routes.py:417` | jwt | success(), error() | — |
| POST | `/api/v1/videos/<video_id>/retry-extraction` | videos | `retry_extraction` | `services/api/app/api/v1/videos/routes.py:366` | jwt | success(), error() | — |
| POST | `/api/v1/videos/<video_id>/server-extract` | videos | `server_extract` | `services/api/app/api/v1/videos/routes.py:624` | jwt | success(), error() | — |
| GET | `/api/v1/videos/<video_id>/status` | videos | `get_video_status` | `services/api/app/api/v1/videos/routes.py:226` | jwt | success(), error() | — |
| POST | `/api/v1/videos/<video_id>/upload-complete` | videos | `upload_complete` | `services/api/app/api/v1/videos/routes.py:333` | jwt | success(), error() | — |
| POST | `/api/v1/videos/images/upload` | videos | `upload_images` | `services/api/app/api/v1/videos/routes.py:679` | jwt | success(), error() | — |
| GET | `/api/v1/videos/storage` | videos | `get_storage_stats` | `services/api/app/api/v1/videos/routes.py:658` | jwt | success(), error() | — |
| POST | `/api/v1/videos/upload` | videos | `upload_video` | `services/api/app/api/v1/videos/routes.py:58` | jwt | success(), error() | — |
| POST | `/api/v1/videos/upload-url` | videos | `get_upload_url` | `services/api/app/api/v1/videos/routes.py:126` | jwt | success(), error() | — |
| POST | `/api/verification/<alert_id>/review` | verification | `review_alert` | `services/api/app/api/v1/verification/routes.py:57` | jwt | success(), error() | tenant_id |
| GET | `/api/verification/queue` | verification | `get_queue` | `services/api/app/api/v1/verification/routes.py:25` | jwt | success(), error() | tenant_id |
| GET | `/api/verification/queue/count` | verification | `queue_count` | `services/api/app/api/v1/verification/routes.py:42` | jwt | success(), error() | tenant_id |
| GET | `/health` | health | `health_check` | `services/api/app/api/v1/health/routes.py:34` | NONE(verificar) | jsonify | — |
| GET | `/livez` | health | `liveness_check` | `services/api/app/api/v1/health/routes.py:75` | NONE(verificar) | jsonify | — |
| GET | `/readyz` | health | `readiness_check` | `services/api/app/api/v1/health/routes.py:115` | NONE(verificar) | error(), jsonify | — |
| GET | `/status` | health | `status_check` | `services/api/app/api/v1/health/routes.py:173` | NONE(verificar) | jsonify | — |
