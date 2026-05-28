<!-- Parent: ../AGENTS.md -->

# frames — Active Learning & Pre-Annotation

Proxy to pre-annotation service (DINO+SAM) and Active Learning prioritization.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/frames/<id>/pre-annotate` | POST | Trigger DINO+SAM pre-annotation for frame |
| `/api/frames/prioritize` | POST | Rank frames by Active Learning (module_code in body) |

**Key Notes:**
- Proxies to external `PRE_ANNOTATION_URL` service (default: `http://pre-annotation-service:8080`)
- Returns 503 if service unavailable
- Prioritization scoped to tenant + module_code
- Pre-annotation returns bounding boxes (auto-label on frames)
