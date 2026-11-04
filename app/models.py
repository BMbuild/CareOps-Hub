"""Validation des données reçues par l'API (Pydantic).

Les noms de champs restent en camelCase pour correspondre au JavaScript du front.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["Critique", "Moyenne", "Faible"]
IssueState = Literal["Ouvert", "En cours", "Résolu"]
MilestoneState = Literal["À faire", "En cours", "Terminé", "Bloqué"]
FeatureState = Literal["Planifiée", "En développement", "Livrée"]

# Date ISO (AAAA-MM-JJ) ou vide.
OptionalDate = Field("", pattern=r"^(\d{4}-\d{2}-\d{2})?$")


class Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")


class Client(Base):
    name: str = Field(min_length=1, max_length=120)
    goLiveDate: str = OptionalDate


class Feature(Base):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=500)
    status: FeatureState = "Planifiée"


class Issue(Base):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field("", max_length=2000)
    severity: Severity = "Moyenne"
    state: IssueState = "Ouvert"
    featureId: str = ""
    clientIds: list[str] = []


class Milestone(Base):
    clientId: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=160)
    dueDate: str = OptionalDate
    owner: str = Field("", max_length=80)
    status: MilestoneState = "À faire"
    blocker: str = Field("", max_length=1000)


MODELS: dict[str, type[Base]] = {
    "clients": Client,
    "features": Feature,
    "issues": Issue,
    "milestones": Milestone,
}
