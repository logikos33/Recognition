<!-- Parent: ../AGENTS.md -->

# alerts — EPI Violation Alerts

List, filter, export, and acknowledge alerts from violation detection.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts` | GET | List alerts with pagination + filters (camera_id, date range, violation_type, acknowledged) |
| `/api/alerts/export` | GET | Export alerts to CSV (same filters) |
| `/api/alerts/<id>/acknowledge` | POST | Mark alert as acknowledged |
| `/api/alerts/stats` | GET | Alert counts by camera (total, unacknowledged) |

**Key Notes:**
- Pagination: `page`, `per_page` (default 20, max 100)
- Date filters: ISO 8601 format
- CSV export includes violations array flattened (one row per violation)
- Stats supports optional `camera_id` filter
- Confidence shown as percentage in CSV
