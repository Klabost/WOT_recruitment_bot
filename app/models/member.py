"""Class storing Member data"""
from pydantic import BaseModel

class Member(BaseModel, str_strip_whitespace=True):
    """class that stores Member data"""
    account_name: str
    account_id: int
    role: str

    def __eq__(self, other) -> bool:
        return self.account_id==other.account_id
