from app.core.errors import map_http_exception_code


def test_map_http_exception_code_defaults_to_http_error() -> None:
    assert map_http_exception_code(418) == "HTTP_ERROR"
