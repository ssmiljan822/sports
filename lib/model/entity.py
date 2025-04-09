class Entity:

    def __init__(self, id: int, name: str):
        self.id: int = id
        self.name: str = name

    def __str__(self):
        return (f'{self.name} ({self.id})')
