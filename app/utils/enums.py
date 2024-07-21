"""usefull enums for data parsing"""
from enum import Enum

class RequestType(Enum):
    """Type of requests"""
    ID = 'id'
    MEMBER = 'member'

    def __str__(self):
        return str(self.value)

class Reason(Enum):
    """Reasons member left clan"""
    LEFT = "left"
    DISBANDED = "Disbanded"

    def __str__(self):
        return str(self.value)
