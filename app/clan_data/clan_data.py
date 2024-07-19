"""storage objects"""
from typing import Union
from typing_extensions import Annotated
from pydantic import BaseModel, Field, field_validator

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

    
    def __eq__(self, other) -> bool:
        return self.clan_id == other.clan_id
    
    def update_values(self, other):
        """update current values"""
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
        return int(v)
    
    @field_validator('is_clan_disbanded', mode='before')
    @classmethod
    def empty_string_to_bool(cls, v: Union[str,bool, int]) -> int:
        """If is_clan_disbanded is an empty string return False"""
        if isinstance(v, str):
            if not v or v.isspace():
                return False
        return bool(v)
