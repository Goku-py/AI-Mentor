# Tests Directory

This directory contains automated tests for the AI Code Mentor project.

## Structure

- `test_analyzer.py` - Unit tests for the code analyzer module
- `test_api.py` - Integration tests for the Flask API

## Running Tests

### Prerequisites

Install pytest:
```bash
pip install pytest
```

Or install from requirements.txt (already included):
```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_analyzer.py -v
pytest tests/test_api.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_analyzer.py::TestSyntaxChecking -v
```

### Run Specific Test Function

```bash
pytest tests/test_analyzer.py::TestSyntaxChecking::test_valid_python_syntax -v
```

### Generate Coverage Report

```bash
pip install coverage
coverage run -m pytest
coverage report
coverage html  # Creates htmlcov/index.html
```

## Test Coverage

The tests cover:

### Analyzer Tests (`test_analyzer.py`)
- Tool verification and availability detection
- Python syntax checking
- Line-level code quality checks (long lines, TODO comments, whitespace)
- Error help generation
- Code analysis integration
- Python code execution and error handling

### API Tests (`test_api.py`)
- Health check endpoint
- Tools availability endpoint
- Code analysis endpoint (POST /analyze)
- Error handling (missing code, invalid JSON)
- Response structure validation
- CORS header validation

## Adding New Tests

1. Create a test function starting with `test_`
2. Use descriptive names that explain what is being tested
3. Add docstrings explaining the test purpose
4. Use assertions to verify behavior

Example:
```python
def test_my_feature(self):
    """Test that my feature does the expected thing."""
    result = some_function()
    assert result == expected_value
```

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```bash
# Example GitHub Actions
pytest --cov=. --cov-report=xml
```
