class Extraction:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
