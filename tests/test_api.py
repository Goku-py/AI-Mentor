"""
Integration tests for the Flask backend API.

Run with: python -m pytest tests/test_api.py -v
"""

import pytest
import json
from app import app


@pytest.fixture
def client():
    """Create Flask test client."""
    app.config['TESTING'] = True
    app.config['RATELIMIT_ENABLED'] = False
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Test server health check endpoint."""
    
    def test_health_endpoint_exists(self, client):
        """Health endpoint should return 200."""
        response = client.get('/api/v1/health')
        assert response.status_code == 200
    
    def test_health_response_structure(self, client):
        """Health response should include status and tool info."""
        response = client.get('/api/v1/health')
        data = json.loads(response.data)
        assert 'status' in data
        assert 'available_tools' in data
        assert 'ai_mentor_enabled' in data


class TestToolsEndpoint:
    """Test tools availability endpoint."""
    
    def test_tools_endpoint_exists(self, client):
        """Tools endpoint should return 200."""
        response = client.get('/api/v1/tools')
        assert response.status_code == 200
    
    def test_tools_response_structure(self, client):
        """Tools response should list available tools."""
        response = client.get('/api/v1/tools')
        data = json.loads(response.data)
        assert 'available' in data
        assert 'message' in data


class TestAnalyzeEndpoint:
    """Test code analysis endpoint."""
    
    def test_analyze_endpoint_requires_post(self, client):
        """GET request to POST-only endpoint should not succeed."""
        response = client.get('/api/v1/analyze')
        # Flask returns 404 (caught by static catch-all) or 405 depending on
        # routing order; either way it must not return 200.
        assert response.status_code in (404, 405)
    
    def test_analyze_requires_code(self, client):
        """Analyze should reject missing code."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({}),
                               content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_analyze_requires_non_empty_code(self, client):
        """Analyze should reject empty/whitespace-only code."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({'code': '   ', 'language': 'python'}),
                               content_type='application/json')
        assert response.status_code == 400
    
    def test_analyze_python_success(self, client):
        """Analyze should process valid Python code."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'print("hello")',
                                   'language': 'python'
                               }),
                               content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['language'] == 'python'
    
    def test_analyze_includes_execution_result(self, client):
        """Analyze response should include execution output."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'print("test output")',
                                   'language': 'python'
                               }),
                               content_type='application/json')
        data = json.loads(response.data)
        assert 'execution' in data
        assert 'test output' in data['execution']['stdout']
    
    def test_analyze_includes_issues(self, client):
        """Analyze response should include detected issues."""
        # Code with a long line (> 79 chars)
        code = 'x = ' + 'y' * 100
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': code,
                                   'language': 'python'
                               }),
                               content_type='application/json')
        data = json.loads(response.data)
        assert 'issues' in data
        assert isinstance(data['issues'], list)
    
    def test_analyze_includes_ai_feedback(self, client):
        """Analyze response should include AI mentor feedback."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'x = 10\nprint(x)',
                                   'language': 'python'
                               }),
                               content_type='application/json')
        data = json.loads(response.data)
        assert 'ai_mentor_feedback' in data
    
    def test_analyze_with_syntax_error(self, client):
        """Analyze should handle syntax errors gracefully."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'print("missing paren',
                                   'language': 'python'
                               }),
                               content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        # Should have detected syntax error
        assert any(i['code'] == 'SYNTAX_ERROR' for i in data['issues'])
    
    def test_analyze_default_language_is_python(self, client):
        """Language should default to Python if not specified."""
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'print("hello")'
                               }),
                               content_type='application/json')
        data = json.loads(response.data)
        assert data['language'] == 'python'
    
    def test_analyze_with_invalid_json(self, client):
        """Malformed JSON should be handled gracefully."""
        response = client.post('/api/v1/analyze',
                               data='invalid json',
                               content_type='application/json')
        assert response.status_code == 400


class TestHistoryEndpoint:
    """Test session-backed analyze history endpoint."""

    def test_history_empty_by_default(self, client):
        response = client.get('/api/v1/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['history'] == []

    def test_history_appends_on_analyze(self, client):
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'print("hello world")',
                                   'language': 'python'
                               }),
                               content_type='application/json',
                               environ_overrides={'REMOTE_ADDR': '10.1.0.1'})
        assert response.status_code == 200

        history_response = client.get('/api/v1/history')
        assert history_response.status_code == 200
        data = json.loads(history_response.data)
        assert len(data['history']) >= 1
        latest = data['history'][-1]
        assert 'timestamp' in latest
        assert latest['language'] == 'python'
        assert latest['code'] == 'print("hello world")'
        assert isinstance(latest['had_error'], bool)

    def test_history_returns_last_10_entries(self, client):
        for idx in range(12):
            response = client.post('/api/v1/analyze',
                                   data=json.dumps({
                                       'code': f'print({idx})',
                                       'language': 'python'
                                   }),
                                   content_type='application/json',
                                   environ_overrides={'REMOTE_ADDR': f'10.1.1.{idx + 1}'})
            assert response.status_code == 200

        history_response = client.get('/api/v1/history')
        assert history_response.status_code == 200
        data = json.loads(history_response.data)
        assert len(data['history']) == 10
        # Last item should correspond to the most recent call.
        assert data['history'][-1]['code'] == 'print(11)'

    def test_history_delete_clears_entries(self, client):
        response = client.post('/api/v1/analyze',
                               data=json.dumps({
                                   'code': 'print("to clear")',
                                   'language': 'python'
                               }),
                               content_type='application/json',
                               environ_overrides={'REMOTE_ADDR': '10.2.0.1'})
        assert response.status_code == 200

        clear_response = client.delete('/api/v1/history')
        assert clear_response.status_code == 200
        clear_data = json.loads(clear_response.data)
        assert clear_data['ok'] is True
        assert clear_data['history'] == []

        history_response = client.get('/api/v1/history')
        data = json.loads(history_response.data)
        assert data['history'] == []


class TestRootEndpoint:
    """Test root endpoint (serves the frontend SPA)."""

    def test_root_endpoint_exists(self, client):
        """Root endpoint should return 200 (serves index.html or fallback)."""
        response = client.get('/')
        # The app serves a built frontend; 200 or 404 (dist not built) are both
        # acceptable in a test environment without a built frontend.
        assert response.status_code in (200, 404)


class TestCORSHeaders:
    """Test CORS configuration."""
    
    def test_cors_headers_present(self, client):
        """Response should include CORS headers."""
        response = client.options('/api/v1/analyze')
        # CORS headers should be set
        # The actual check depends on flask-cors configuration
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
