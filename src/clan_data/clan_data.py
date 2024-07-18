"""storage objects"""
from typing_extensions import Annotated
from pydantic import BaseModel, Field

Name = Annotated[str, Field(min_length=1)]

class Member(BaseModel, str_strip_whitespace=True):
    """class that stores Member data"""
    name: Name
    member_id: int = 0

class Clan(BaseModel, str_strip_whitespace=True):
    """class that store clan data"""
    name: Name
    clan_id: int = 0
    is_clan_disbanded: bool = False
    old_name: str = " "
    members: list[Member] = None
