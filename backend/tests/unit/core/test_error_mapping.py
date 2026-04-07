from app.core.errors import map_http_exception_code

def test_map_http_exception_code_defaults_to_http_error() -> None:
    assert map_http_exception_code(418) == "HTTP_ERROR"

def test_map_http_exception_code_handles_404() -> None:
    assert map_http_exception_code(404) == "NOT_FOUND"

def test_map_http_exception_code_handles_403() -> None:
    assert map_http_exception_code(403) == "ACCESS_DENIED"

def test_map_http_exception_code_handles_500() -> None:
    assert map_http_exception_code(500) == "INTERNAL_SERVER_ERROR"
