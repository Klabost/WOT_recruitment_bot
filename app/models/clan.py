"""model storing Clan data"""
import json
from pydantic import BaseModel, field_serializer

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

    @field_serializer("members")
    def serialize_members(self, members, _info):
        """serialize members list to json"""
        json_members = [x.model_dump() for x in members]
        return json.dumps(json_members)
