from dataclasses import dataclass, field, asdict
import json
import uuid


@dataclass
class Attack:
    description: str = ""   # User's input
    name: str = ""          # GPT-polished name
    damage: int = 0         # GPT-assigned


@dataclass
class CardData:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_name: str = ""
    monster_name: str = ""
    description: str = ""
    hitpoints: int = 100
    attacks: list[Attack] = field(default_factory=lambda: [Attack(), Attack(), Attack()])
    flavor_text: str = ""
    monster_type: str = ""
    front_image: str = ""
    back_image: str = ""

    @property
    def back_label(self) -> str:
        return f"{self.user_name}Mon" if self.user_name else "YouMon"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "CardData":
        d = dict(d)
        d["attacks"] = [Attack(**a) for a in d.get("attacks", [])]
        return cls(**d)

    @classmethod
    def from_json(cls, text: str) -> "CardData":
        return cls.from_dict(json.loads(text))
