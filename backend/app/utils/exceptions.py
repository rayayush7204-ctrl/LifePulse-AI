from typing import Any, Dict, Optional

class AppException(Exception):
    def __init__(self, message: str, status_code: int = 500, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, identifier: str):
        super().__init__(f"{entity_name} '{identifier}' not found.", status_code=404)

class ValidationException(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=400)
