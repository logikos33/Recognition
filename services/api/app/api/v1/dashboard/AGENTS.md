<!-- Parent: ../AGENTS.md -->

# dashboard — System Analytics & Reporting

KPIs, detection stats, and Excel export for reports.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/dashboard/stats` | GET | System overview (cameras, videos, frames, jobs, models, alerts, class distribution) |
| `/api/v1/dashboard/detections` | GET | Daily detection counts for last N days (query param: `days`, default 30) |
| `/api/v1/reports/export` | GET | Export alerts as Excel XLSX (query params: `days`, filters) |

**Key Notes:**
- Stats include all counters + top 10 classes by annotation frequency
- Detections: grouped by date, default 30-day window
- Excel export includes: ID, camera, timestamp, confidence, violations, acknowledged
- Reports scoped by optional filters matching alerts query params
