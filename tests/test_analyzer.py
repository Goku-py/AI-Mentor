"""
Unit tests for the code analyzer module.

Run with: python -m pytest tests/test_analyzer.py -v
"""

import pytest
from analyzer import (
    analyze_code,
    verify_tools,
    _check_syntax,
    _line_based_checks,
    _python_error_help,
    Issue
)


class TestToolVerification:
    """Test tool detection functionality."""
    
    def test_verify_tools_returns_dict(self):
        """verify_tools should return a dictionary."""
        tools = verify_tools()
        assert isinstance(tools, dict)
        assert 'python' in tools
        assert 'javascript' in tools
    
    def test_verify_tools_values_are_booleans(self):
        """All tool values should be booleans."""
        tools = verify_tools()
        for tool, available in tools.items():
            assert isinstance(available, bool), f"{tool} should have boolean value"
    
    def test_python_tool_is_available(self):
        """Python should always be available (we're running tests with it)."""
        tools = verify_tools()
        assert tools['python'] is True


class TestSyntaxChecking:
    """Test Python syntax checking."""
    
    def test_valid_python_syntax(self):
        """Valid Python code should not raise syntax errors."""
        code = "print('hello')\nx = 10"
        issues, exc = _check_syntax(code)
        assert len(issues) == 0
        assert exc is None
    
    def test_invalid_python_syntax(self):
        """Invalid Python code should be detected."""
        code = "print('hello'\nx = 10"  # Missing closing paren
        issues, exc = _check_syntax(code)
        assert len(issues) > 0
        assert exc is not None
        assert issues[0].code == "SYNTAX_ERROR"
    
    def test_syntax_error_has_line_number(self):
        """Syntax errors should include line number."""
        code = "x = 1\nprint('hello'\ny = 2"
        issues, exc = _check_syntax(code)
        assert issues[0].line > 0


class TestLineLevelChecks:
    """Test line-based code quality checks."""
    
    def test_long_line_detection(self):
        """Lines exceeding 79 characters should be detected."""
        code = "x = " + "y" * 100  # Way over 79 chars
        issues = _line_based_checks(code)
        assert any(i.code == "LONG_LINE" for i in issues)
    
    def test_todo_comment_detection(self):
        """TODO/FIXME comments should be detected."""
        code = "# TODO: fix this later\nx = 10"
        issues = _line_based_checks(code)
        assert any(i.code == "TODO_COMMENT" for i in issues)
    
    def test_trailing_whitespace_detection(self):
        """Trailing whitespace should be detected."""
        code = "x = 10   \ny = 20"
        issues = _line_based_checks(code)
        assert any(i.code == "TRAILING_WHITESPACE" for i in issues)
    
    def test_tab_indentation_detection(self):
        """Tab indentation should be detected (should use spaces)."""
        code = "\tfor i in range(10):\n\t\tprint(i)"
        issues = _line_based_checks(code)
        assert any(i.code == "TABS_INDENT" for i in issues)


class TestErrorHelp:
    """Test error explanation generation."""
    
    def test_zero_division_error_help(self):
        """ZeroDivisionError should provide specific help."""
        help_text = _python_error_help("ZeroDivisionError", "division by zero")
        assert "divide by zero" in help_text['explanation'].lower()
        assert len(help_text['suggestions']) > 0
    
    def test_name_error_help(self):
        """NameError should provide specific help."""
        help_text = _python_error_help("NameError", "name 'x' is not defined")
        assert "not been defined" in help_text['explanation'].lower()
    
    def test_unknown_error_generic_help(self):
        """Unknown errors should get generic help."""
        help_text = _python_error_help("UnknownError", "something broke")
        assert "runtime error" in help_text['explanation'].lower()


class TestAnalyzeCode:
    """Integration tests for the analyze_code function."""
    
    @pytest.mark.asyncio
    async def test_analyze_valid_python(self):
        """analyze_code should successfully analyze valid Python."""
        code = 'x = 10\nprint(x)'
        result = await analyze_code(code, 'python')
        assert result['ok'] is True
        assert result['language'] == 'python'
        assert result['execution']['returncode'] == 0
    
    @pytest.mark.asyncio
    async def test_analyze_python_with_error(self):
        """analyze_code should detect runtime errors."""
        code = 'x = 10 / 0'  # ZeroDivisionError
        result = await analyze_code(code, 'python')
        assert result['ok'] is True  # ok=True, but execution has error
        assert result['execution']['returncode'] != 0 or result['execution']['error'] is not None
    
    @pytest.mark.asyncio
    async def test_analyze_invalid_language(self):
        """Unsupported languages should be marked as such."""
        code = 'print("hello")'
        result = await analyze_code(code, 'ruby')  # Not supported
        assert 'unsupported' in result['ai_mentor_feedback'].lower() or \
               any(i['code'] == 'LANGUAGE_UNSUPPORTED' for i in result['issues'])
    
    @pytest.mark.asyncio
    async def test_analyze_empty_code(self):
        """analyze_code should handle empty code."""
        result = await analyze_code('', 'python')
        assert result['summary']['line_count'] == 0
    
    @pytest.mark.asyncio
    async def test_analyze_result_structure(self):
        """analyze_code result should have correct structure."""
        code = 'print("test")'
        result = await analyze_code(code, 'python')
        
        assert 'ok' in result
        assert 'language' in result
        assert 'summary' in result
        assert 'issues' in result
        assert 'execution' in result
        assert 'ai_mentor_feedback' in result
        
        assert 'line_count' in result['summary']
        assert 'issue_count' in result['summary']
        
        assert isinstance(result['issues'], list)


class TestPythonExecution:
    """Test Python code execution."""
    
    @pytest.mark.asyncio
    async def test_python_stdout_capture(self):
        """Python stdout should be captured."""
        code = 'print("hello world")'
        result = await analyze_code(code, 'python')
        assert 'hello world' in result['execution']['stdout']
    
    @pytest.mark.asyncio
    async def test_python_timeout_detection(self):
        """Infinite loops should timeout (with 1 second limit)."""
        code = 'while True: pass'
        result = await analyze_code(code, 'python')
        # The _run_python function has a 3.0 second default timeout
        # For this test, we just check that either timeout happened or error occurred
        assert (result['execution']['timed_out'] is True or 
                result['execution']['error'] is not None)
    
    @pytest.mark.asyncio
    async def test_python_error_parsing(self):
        """RuntimeError should be parsed correctly."""
        code = 'x = undefined_variable'
        result = await analyze_code(code, 'python')
        assert result['execution']['error'] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
