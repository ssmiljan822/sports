from lib.model.country import Country
from lib.model.entity import Entity


class League(Entity):

    def __init__(self, id: int, name: str):
        super().__init__(id, name)
        self.country: Country = None
    