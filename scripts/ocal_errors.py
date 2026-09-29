"""ocal_errors — 错误类型。"""


class CalError(Exception):
    """日历操作抛给用户的错误；消息直接展示给用户，不打印 traceback。"""

    def __init__(self, message, *, code=None, http_status=None, outcome_unknown=None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.outcome_unknown = outcome_unknown

    def to_dict(self):
        result = {"error": str(self), "exit": 1}
        for key in ("code", "http_status", "outcome_unknown"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result
