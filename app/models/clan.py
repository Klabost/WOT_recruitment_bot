"""model storing Clan data"""
from typing import Union
from pydantic import BaseModel, field_validator

from models.member import Member

class Clan(BaseModel, str_strip_whitespace=True):
    """class that store clan data"""
    name: str
    clan_id: int = 0
    tag: str = ""
    is_clan_disbanded: bool = False
    old_name: str = ""
    members_count: int = 0
    description: str = ''
    members: list[Member] = None


    def __eq__(self, other) -> bool:
        return self.clan_id == other.clan_id

    def update_values(self, other):
        """update current values"""
        self.name = other.name
        self.is_clan_disbanded = other.is_clan_disbanded
        self.old_name = other.old_name
        self.members_count = other.members_count
        self.members = other.members

    @field_validator('clan_id', 'members_count', mode='before')
    @classmethod
    def empty_string_to_zero(cls, v: Union[str,int]) -> int:
        """If clan_id is an int, return int. if its a string make it an int
        if it's an empty string or an invalid int then return 0"""
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            if not v or v.isspace():
                return 0
        if not v:
            return 0
        return int(v)
