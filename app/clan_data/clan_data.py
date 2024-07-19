"""storage objects"""
from typing_extensions import Annotated
from pydantic import BaseModel, Field

Name = Annotated[str, Field(min_length=1)]

class Member(BaseModel, str_strip_whitespace=True):
    """class that stores Member data"""
    account_name: Name
    account_id: int = 0
    role: str

class Clan(BaseModel, str_strip_whitespace=True):
    """class that store clan data"""
    name: Name
    clan_id: int = 0
    is_clan_disbanded: bool = False
    old_name: str = ""
    members_count: int = 0
    members: list[Member] = None

    def update_values(self, other):
        """update current values"""
        self.is_clan_disbanded = other.is_clan_disbanded
        self.old_name = other.old_name
        self.members_count = other.members_count
        self.members = other.members
