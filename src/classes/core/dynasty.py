from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.classes.effect import load_effect_from_str
from src.classes.effect.desc import format_effects_to_text
from src.i18n import t
from src.utils.config import CONFIG
from src.utils.df import game_configs, get_float, get_int, get_str


@dataclass
class ImperialClaim:
    """One candidate's independent case inside an imperial crisis."""

    candidate_id: str
    opened_month: int
    position: str = "claimant"
    status: str = "active"
    political_positions: dict[str, str] = field(default_factory=dict)
    evidence_event_ids: list[str] = field(default_factory=list)
    evaluations: list[dict[str, Any]] = field(default_factory=list)
    winner: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": str(self.candidate_id),
            "opened_month": int(self.opened_month),
            "position": str(self.position),
            "status": str(self.status),
            "political_positions": dict(self.political_positions),
            "evidence_event_ids": list(self.evidence_event_ids),
            "evaluations": [dict(item) for item in self.evaluations],
            "winner": bool(self.winner),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImperialClaim":
        required = {"candidate_id", "opened_month", "position", "status", "political_positions", "evidence_event_ids", "evaluations", "winner"}
        missing = required.difference(data)
        if missing:
            raise ValueError(f"Imperial claim schema is missing fields: {sorted(missing)}")
        return cls(
            candidate_id=str(data["candidate_id"]),
            opened_month=int(data["opened_month"]),
            position=str(data["position"]),
            status=str(data["status"]),
            political_positions={str(key): str(value) for key, value in dict(data["political_positions"]).items()},
            evidence_event_ids=[str(value) for value in data["evidence_event_ids"]],
            evaluations=[dict(item) for item in data["evaluations"] if isinstance(item, dict)],
            winner=bool(data["winner"]),
        )


@dataclass
class ImperialCrisis:
    kind: str
    incumbent_id: str | None
    opened_month: int
    claims: list[ImperialClaim] = field(default_factory=list)
    status: str = "active"

    def __post_init__(self) -> None:
        if self.kind not in {"challenge", "succession"}:
            raise ValueError("Imperial crisis kind must be challenge or succession")
        if self.incumbent_id is not None:
            self.incumbent_id = str(self.incumbent_id)
        self.claims = list(self.claims)

    def get_claim(self, candidate_id: str) -> ImperialClaim | None:
        candidate_id = str(candidate_id)
        return next((claim for claim in self.claims if str(claim.candidate_id) == candidate_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "incumbent_id": self.incumbent_id,
            "opened_month": int(self.opened_month),
            "claims": [claim.to_dict() for claim in self.claims],
            "status": str(self.status),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImperialCrisis":
        if "emperor_avatar_id" in data or "claimant_avatar_id" in data:
            raise ValueError("Legacy imperial crisis schema is not supported")
        required = {"kind", "incumbent_id", "opened_month", "claims", "status"}
        missing = required.difference(data)
        if missing:
            raise ValueError(f"Imperial crisis schema is missing fields: {sorted(missing)}")
        claims_data = data["claims"]
        if not isinstance(claims_data, list):
            raise ValueError("Imperial crisis claims must be a list")
        return cls(
            kind=str(data["kind"]),
            incumbent_id=str(data["incumbent_id"]) if data["incumbent_id"] is not None else None,
            opened_month=int(data["opened_month"]),
            claims=[ImperialClaim.from_dict(item) for item in claims_data],
            status=str(data["status"]),
        )


@dataclass
class Dynasty:
    id: int
    name: str
    desc: str
    template_name: str = ""
    royal_surname: str = ""
    effect_desc: str = ""
    effects: dict[str, Any] = field(default_factory=dict)
    style_tag: str = ""
    official_preference_type: str = ""
    official_preference_value: str = ""
    weight: float = 1.0
    is_low_magic: bool = True
    current_emperor_id: str | None = None
    royal_house_member_ids: list[str] = field(default_factory=list)
    royal_blood_member_ids: list[str] = field(default_factory=list)
    imperial_crisis: ImperialCrisis | None = None

    def add_royal_house_member(self, avatar_id: str, *, blood: bool = False) -> None:
        avatar_id = str(avatar_id)
        if avatar_id and avatar_id not in self.royal_house_member_ids:
            self.royal_house_member_ids.append(avatar_id)
        if blood and avatar_id and avatar_id not in self.royal_blood_member_ids:
            self.royal_blood_member_ids.append(avatar_id)

    def register_birth(self, child_id: str, parent_ids: list[str]) -> None:
        if any(str(parent_id) in self.royal_blood_member_ids for parent_id in parent_ids):
            self.add_royal_house_member(child_id, blood=True)

    def register_marriage(self, spouse_ids: list[str]) -> None:
        if any(str(spouse_id) in self.royal_house_member_ids for spouse_id in spouse_ids):
            for spouse_id in spouse_ids:
                self.add_royal_house_member(spouse_id)

    def _get_localized_template(self) -> "Dynasty | None":
        template = dynasties_by_id.get(int(self.id))
        if template is None or template is self:
            return None
        if not self._matches_template_identity(template):
            return None
        return template

    def _matches_template_identity(self, template: "Dynasty") -> bool:
        source_name = source_dynasty_names_by_id.get(int(self.id), "")
        candidate_names = {
            str(self.template_name or "").strip(),
            str(self.name or "").strip(),
        }
        candidate_names.discard("")
        return bool(candidate_names & {str(template.name or "").strip(), str(source_name or "").strip()})

    @property
    def localized_name(self) -> str:
        template = self._get_localized_template()
        return str(getattr(template, "name", "") or self.name or "")

    @property
    def localized_desc(self) -> str:
        template = self._get_localized_template()
        return str(getattr(template, "desc", "") or self.desc or "")

    @property
    def localized_effect_desc(self) -> str:
        template = self._get_localized_template()
        if template is not None and getattr(template, "effect_desc", ""):
            return str(template.effect_desc or "")
        if self.effect_desc:
            return str(self.effect_desc or "")
        if self.effects:
            return format_effects_to_text(self.effects)
        return ""

    @property
    def title(self) -> str:
        name = self.localized_name
        if not name:
            return ""
        translated = t("dynasty_title_format", name=name)
        return translated if translated != "dynasty_title_format" else f"{name}朝"

    @property
    def royal_house_name(self) -> str:
        if not self.royal_surname:
            return ""
        translated = t("dynasty_royal_house_format", surname=self.royal_surname)
        return translated if translated != "dynasty_royal_house_format" else f"{self.royal_surname}氏"

    def create_runtime(self, royal_surname: str) -> "Dynasty":
        source_name = source_dynasty_names_by_id.get(int(self.id), str(self.name or ""))
        return Dynasty(
            id=int(self.id),
            name=str(self.name),
            desc=str(self.desc),
            template_name=str(source_name or ""),
            royal_surname=str(royal_surname or ""),
            effect_desc=str(self.effect_desc or ""),
            effects=dict(self.effects or {}),
            style_tag=str(self.style_tag or ""),
            official_preference_type=str(self.official_preference_type or ""),
            official_preference_value=str(self.official_preference_value or ""),
            weight=float(self.weight),
            is_low_magic=bool(self.is_low_magic),
            current_emperor_id=None,
            royal_house_member_ids=[],
            royal_blood_member_ids=[],
            imperial_crisis=None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": int(self.id),
            "name": str(self.name),
            "desc": str(self.desc),
            "template_name": str(self.template_name or ""),
            "royal_surname": str(self.royal_surname or ""),
            "effect_desc": str(self.effect_desc or ""),
            "effects": dict(self.effects or {}),
            "style_tag": str(self.style_tag or ""),
            "official_preference_type": str(self.official_preference_type or ""),
            "official_preference_value": str(self.official_preference_value or ""),
            "weight": float(self.weight),
            "is_low_magic": bool(self.is_low_magic),
            "current_emperor_id": self.current_emperor_id,
            "royal_house_member_ids": [str(value) for value in self.royal_house_member_ids],
            "royal_blood_member_ids": [str(value) for value in self.royal_blood_member_ids],
            "imperial_crisis": self.imperial_crisis.to_dict() if self.imperial_crisis else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dynasty":
        required_membership = {"royal_house_member_ids", "royal_blood_member_ids"}
        missing_membership = required_membership.difference(data)
        if missing_membership:
            raise ValueError(f"Dynasty schema is missing fields: {sorted(missing_membership)}")
        if not isinstance(data["royal_house_member_ids"], list) or not isinstance(data["royal_blood_member_ids"], list):
            raise ValueError("Dynasty membership fields must be lists")
        return cls(
            id=int(data["id"]),
            name=str(data.get("name", "") or ""),
            desc=str(data.get("desc", "") or ""),
            template_name=str(data.get("template_name", "") or ""),
            royal_surname=str(data.get("royal_surname", "") or ""),
            effect_desc=str(data.get("effect_desc", "") or ""),
            effects=dict(data.get("effects", {}) or {}),
            style_tag=str(data.get("style_tag", "") or ""),
            official_preference_type=str(data.get("official_preference_type", "") or ""),
            official_preference_value=str(data.get("official_preference_value", "") or ""),
            weight=float(data.get("weight", 1.0) or 1.0),
            is_low_magic=bool(data.get("is_low_magic", True)),
            current_emperor_id=str(data.get("current_emperor_id") or "") or None,
            royal_house_member_ids=[str(value) for value in data.get("royal_house_member_ids", [])],
            royal_blood_member_ids=[str(value) for value in data.get("royal_blood_member_ids", [])],
            imperial_crisis=ImperialCrisis.from_dict(data["imperial_crisis"]) if data.get("imperial_crisis") else None,
        )


def _load_dynasties_data() -> tuple[dict[int, Dynasty], dict[str, Dynasty]]:
    new_by_id: dict[int, Dynasty] = {}
    new_by_name: dict[str, Dynasty] = {}

    for row in game_configs.get("dynasty", []) or []:
        dynasty = Dynasty(
            id=get_int(row, "id"),
            name=get_str(row, "name"),
            desc=get_str(row, "desc"),
            effect_desc=get_str(row, "effect_desc"),
            effects=load_effect_from_str(get_str(row, "effects")),
            style_tag=get_str(row, "style_tag"),
            official_preference_type=get_str(row, "official_preference_type"),
            official_preference_value=get_str(row, "official_preference_value"),
            weight=get_float(row, "weight", 1.0),
        )
        if not dynasty.effect_desc and dynasty.effects:
            dynasty.effect_desc = format_effects_to_text(dynasty.effects)
        if dynasty.id <= 0 or not dynasty.name:
            continue
        new_by_id[dynasty.id] = dynasty
        new_by_name[dynasty.name] = dynasty

    return new_by_id, new_by_name


def _load_source_dynasty_names() -> dict[int, str]:
    source_names: dict[int, str] = {}
    csv_path = Path(CONFIG.paths.shared_game_configs) / "dynasty.csv"
    if not csv_path.exists():
        return source_names

    with csv_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    if len(rows) < 3:
        return source_names

    headers = [str(header or "").strip() for header in rows[0]]
    if headers and headers[0].startswith("\ufeff"):
        headers[0] = headers[0][1:]

    try:
        id_index = headers.index("id")
        name_index = headers.index("name")
    except ValueError:
        return source_names

    for row in rows[2:]:
        if not row or id_index >= len(row):
            continue
        raw_id = str(row[id_index] or "").strip()
        raw_name = str(row[name_index] or "").strip() if name_index < len(row) else ""
        if not raw_id or not raw_name:
            continue
        try:
            source_names[int(float(raw_id))] = raw_name
        except ValueError:
            continue

    return source_names


dynasties_by_id: dict[int, Dynasty] = {}
dynasties_by_name: dict[str, Dynasty] = {}
source_dynasty_names_by_id: dict[int, str] = _load_source_dynasty_names()


def reload() -> None:
    new_by_id, new_by_name = _load_dynasties_data()
    dynasties_by_id.clear()
    dynasties_by_id.update(new_by_id)
    dynasties_by_name.clear()
    dynasties_by_name.update(new_by_name)


reload()
