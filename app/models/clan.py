"""model storing Clan data"""
from pydantic import BaseModel

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
    members: list[Member] = []
