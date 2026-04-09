<!-- Parent: ../AGENTS.md -->

# backend/tests — Test Suite

**Purpose**: Comprehensive pytest-based test coverage for all layers (unit, integration, E2E).

**Coverage target**: Minimum 80% per module. Run `pytest --cov=app/` to verify.

## Structure

```
tests/
├── conftest.py              # Shared fixtures
├── __init__.py
├── unit/                    # Fast, isolated, mocked
│   ├── core/                # auth, exceptions, responses, validators, middleware
│   ├── domain/              # services (no database, mocked storage)
│   ├── infrastructure/      # repositories, storage, queue
│   └── test_constants.py    # enum validation
└── integration/             # Real database, real API calls
    ├── test_api_routes.py   # All endpoints (happy path + errors)
    ├── test_health.py       # Health check endpoints
    └── test_authenticated_routes.py  # JWT-protected routes
```

## Fixtures (`conftest.py`)

**Available in all tests**:

```python
@pytest.fixture
def app():
    """Flask app configured with TestingConfig."""
    return create_app("testing")

@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()

@pytest.fixture
def mock_storage():
    """In-memory storage mock (never calls real R2)."""
    return MockStorageStrategy()

@pytest.fixture
def mock_db_pool():
    """Mock psycopg2 connection pool for unit tests."""
    pool, conn, cursor = MagicMock(), MagicMock(), MagicMock()
    return pool, conn, cursor
```

**Usage**:
```python
def test_create_user(client):
    response = client.post('/api/v1/auth/register', json={...})
    assert response.status_code == 201

def test_upload_video(client, mock_storage):
    # mock_storage provides fake presigned URLs
    response = client.post('/api/v1/videos/upload', ...)
    assert 'upload_url' in response.json
```

## Unit Tests

**No database access. Everything mocked.**

### Core Layer (`unit/core/`)

**test_auth.py**
- JWT token creation and expiry
- Token verification with `@jwt_required()`
- Invalid/expired token handling
- Password hashing with bcrypt

**test_exceptions.py**
- `EpiMonitorError` hierarchy
- Exception serialization to JSON
- HTTP status code mapping

**test_responses.py**
- `success_response()` format
- `error_response()` format
- Status field consistency

**test_validators.py**
- `RTSPUrlValidator` — IP, port, credentials validation
- `VideoUploadValidator` — file extension, size checks
- Boundary conditions (invalid IPs, oversized files)

**test_middleware.py**
- Error handler registration
- Security headers (CORS, X-Content-Type-Options)
- Request logging format

### Domain Layer (`unit/domain/`)

**test_auth_service.py**
- User registration validation
- Duplicate email detection
- Password strength requirements
- Login password verification

**test_camera_service.py** (mocked storage)
- Camera CRUD operations
- RTSP URL generation by manufacturer
- Password encryption/masking
- Validation of IP and port

**test_video_service.py** (mocked storage)
- Video upload presigned URL generation
- Video metadata storage
- Upload status tracking

**test_training_service.py**
- Training job creation
- Model selection
- Training status updates

**test_inference_service.py**
- YOLOv8 model loading
- Inference on mock frames
- Bounding box parsing

**test_dataset_service.py**
- Dataset version creation
- Frame collection
- Metadata aggregation

**test_annotation_service.py**
- Frame annotation storage
- Label validation against EpiClass enum
- Annotation retrieval

### Infrastructure Layer (`unit/infrastructure/`)

**test_repositories.py**
- User repository (mocked database)
- Camera repository (mocked database)
- Video repository (mocked database)
- Query parameter binding (prevent SQL injection)

**test_r2_storage.py** (mocked boto3)
- Presigned URL generation
- File upload/download
- Key existence checks
- Prefix listing

**test_local_storage.py**
- Local disk operations
- File I/O mocking
- Cleanup

### Constants (`unit/test_constants.py`)

- Enum values are strings (VideoStatus.PENDING == "pending")
- No duplicate enum values
- R2Prefix keys match storage structure
- RedisChannel templates are valid `.format()` strings

## Integration Tests

**Real Flask app. Real database (test copy). Real API calls via test client.**

**Setup**: `TestingConfig` uses `DATABASE_TEST_URL` or test copy of `DATABASE_URL`

**Teardown**: Database tables dropped after each test (via conftest fixtures)

### Health Endpoints (`test_health.py`)

```python
def test_get_health(client):
    """GET /api/v1/health returns 200 with system status."""
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    assert 'status' in response.json
    assert response.json['database'] is True  # database OK
    assert response.json['redis'] is True     # redis OK
```

### API Routes (`test_api_routes.py`)

**Auth endpoints**:
```python
def test_register_user(client):
    """POST /api/v1/auth/register creates user."""
    response = client.post('/api/v1/auth/register', json={
        'email': 'test@epi.dev',
        'password': 'SecurePass123!',
        'full_name': 'Test User'
    })
    assert response.status_code == 201
    assert 'user_id' in response.json

def test_login_user(client, user_fixture):
    """POST /api/v1/auth/login returns JWT token."""
    response = client.post('/api/v1/auth/login', json={
        'email': 'test@epi.dev',
        'password': 'SecurePass123!'
    })
    assert response.status_code == 200
    assert 'token' in response.json
```

**Camera endpoints**:
```python
def test_create_camera(authenticated_client):
    """POST /api/v1/cameras creates camera with auto RTSP URL."""
    response = authenticated_client.post('/api/v1/cameras', json={
        'name': 'Loading Bay 1',
        'manufacturer': 'intelbras',
        'ip': '192.168.1.100',
        'port': 554,
        'username': 'admin',
        'password': 'pass123'
    })
    assert response.status_code == 201
    assert response.json['rtsp_url'].startswith('rtsp://')

def test_list_cameras(authenticated_client, camera_fixture):
    """GET /api/v1/cameras returns user's cameras only."""
    response = authenticated_client.get('/api/v1/cameras')
    assert response.status_code == 200
    assert len(response.json) >= 1
```

**Stream endpoints**:
```python
def test_start_stream(authenticated_client, camera_fixture):
    """POST /api/v1/cameras/{id}/stream/start starts HLS + YOLO."""
    response = authenticated_client.post(
        f'/api/v1/cameras/{camera_fixture.id}/stream/start'
    )
    assert response.status_code == 200
    assert response.json['status'] == 'starting'

def test_stream_status(authenticated_client, camera_fixture):
    """GET /api/v1/cameras/{id}/stream/status returns stream status."""
    response = authenticated_client.get(
        f'/api/v1/cameras/{camera_fixture.id}/stream/status'
    )
    assert response.status_code == 200
    assert 'status' in response.json
```

### Authenticated Routes (`test_authenticated_routes.py`)

**JWT validation**:
```python
def test_missing_jwt_token(client):
    """Endpoint without token returns 401."""
    response = client.get('/api/v1/cameras')
    assert response.status_code == 401

def test_invalid_jwt_token(client):
    """Endpoint with invalid token returns 401."""
    response = client.get(
        '/api/v1/cameras',
        headers={'Authorization': 'Bearer invalid.token.here'}
    )
    assert response.status_code == 401

def test_expired_jwt_token(client, expired_token_fixture):
    """Endpoint with expired token returns 401."""
    response = client.get(
        '/api/v1/cameras',
        headers={'Authorization': f'Bearer {expired_token_fixture}'}
    )
    assert response.status_code == 401
```

**Isolation by user**:
```python
def test_camera_isolation(authenticated_client, other_user_camera):
    """User cannot access another user's camera."""
    response = authenticated_client.get(f'/api/v1/cameras/{other_user_camera.id}')
    assert response.status_code == 404
```

## Running Tests

**All tests**:
```bash
cd /Users/vitoremanuel/Documents/Logikos/CATH/'EPI - CATH V2'/backend/
pytest
```

**Unit tests only** (fast, ~2 seconds):
```bash
pytest tests/unit/
```

**Integration tests only** (slower, requires database):
```bash
pytest tests/integration/
```

**Specific test file**:
```bash
pytest tests/unit/core/test_auth.py
```

**Specific test function**:
```bash
pytest tests/unit/core/test_auth.py::test_jwt_token_creation
```

**With verbose output**:
```bash
pytest -v
```

**With coverage report**:
```bash
pytest --cov=app/ --cov-report=html
# Opens htmlcov/index.html in browser
```

**With output capture** (see print statements):
```bash
pytest -s
```

**Only failing tests** (after first run):
```bash
pytest --lf
```

**Stop on first failure**:
```bash
pytest -x
```

## Test Fixtures

**Custom fixtures** (defined in conftest.py or individual test files):

```python
@pytest.fixture
def authenticated_client(client):
    """Test client with valid JWT token."""
    response = client.post('/api/v1/auth/login', json={...})
    token = response.json['token']
    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    return client

@pytest.fixture
def user_fixture(client):
    """Create test user in database."""
    response = client.post('/api/v1/auth/register', json={...})
    return response.json

@pytest.fixture
def camera_fixture(authenticated_client, user_fixture):
    """Create test camera for user."""
    response = authenticated_client.post('/api/v1/cameras', json={...})
    return response.json
```

## Best Practices

1. **Isolation**: Each test is independent. Fixtures clean up after themselves.
2. **Clarity**: Test name = what is being tested. `test_create_camera_with_invalid_ip` is better than `test_camera`.
3. **Assertions**: Use specific assertions (`assert response.status_code == 201`) not generic (`assert response`).
4. **Mocking**: Mock external systems (R2, Redis, slow operations). Test real database in integration tests.
5. **Coverage**: Aim for 80%+ per module. Use `pytest --cov=app/ --cov-report=term-missing` to see gaps.
6. **Error cases**: Test both happy path and error conditions (401, 404, 422, 500).

## Common Issues

**Test fails with "database already exists"**:
- TestingConfig should use separate database (`DATABASE_TEST_URL`)
- Or drop tables in conftest teardown fixture

**Mock not working**:
- Check that mock is passed to function before it's imported
- Use `patch('app.module.function')` decorator pattern

**Timeout on integration test**:
- Real database operations may be slow
- Use fixtures to minimize setup time
- Consider moving to unit test with mocks

**Flaky test (passes sometimes, fails sometimes)**:
- Usually timing issues with async operations
- Add explicit waits or use `time.sleep()` in test
- Or mark with `@pytest.mark.flaky(reruns=3)`

## CI/CD Integration

**Before merge to staging/main**:
```bash
pytest tests/ --cov=app/ --cov-fail-under=80
```

Fails if coverage < 80%.
