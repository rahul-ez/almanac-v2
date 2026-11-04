class ApiError(Exception):
    def __init__(self, status, code, message, field_errors=None, headers=None):
        self.status = status
        self.code = code
        self.message = message
        self.field_errors = field_errors or []
        self.headers = headers or {}
