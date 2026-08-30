"""
A1-skill Python package.

Provides:
  - Skill / SkillResult — base class and result dataclass for directive-based skills
  - skill — decorator to register a Skill subclass
  - list_skills / get_skill — skill registry access
  - sync_endpoints / register_endpoint / list_endpoints / remove_endpoint — endpoint aggregation
"""

from .skill import Skill, SkillResult, skill, list_skills, get_skill
from .aggregation import sync_endpoints, register_endpoint, list_endpoints, remove_endpoint

__all__ = [
    "Skill",
    "SkillResult",
    "skill",
    "list_skills",
    "get_skill",
    "sync_endpoints",
    "register_endpoint",
    "list_endpoints",
    "remove_endpoint",
]
