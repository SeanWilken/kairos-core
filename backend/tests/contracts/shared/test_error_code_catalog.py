from app.core.errors import map_http_exception_code


def test_error_code_catalog_is_stable_for_common_codes() -> None:
    assert map_http_exception_code(404) == "NOT_FOUND"
    assert map_http_exception_code(403) == "ACCESS_DENIED"
    assert map_http_exception_code(401) == "UNAUTHORIZED"
    assert map_http_exception_code(422) == "VALIDATION_ERROR"
    assert map_http_exception_code(500) == "HTTP_ERROR"
