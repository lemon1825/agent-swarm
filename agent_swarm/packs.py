"""Skill Packs — installable domain bundles for Agent Swarm.

A pack is a directory containing:
  pack.yaml       — metadata + skills + ontology terms + playbook config
  (optional .py)  — custom validators or hooks

Usage:
    from agent_swarm.packs import PackManager
    pm = PackManager()
    pm.install("research-pack")          # Install built-in pack
    pm.install_from_path("./my-pack")    # Install from directory
    pm.list_installed()                   # See what's loaded
    bank, ontology = pm.apply()           # Get SkillBank + OntologyBundle
"""
import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .skills import Skill, SkillBank, SkillManifest
from .ontology import OntologyTerm, OntologyRelation, OntologyBundle, OntologyRegistry

PACKS_DIR = os.path.join(os.path.dirname(__file__), "builtin_packs")
USER_PACKS_DIR = os.path.expanduser("~/.agent-swarm/packs")


@dataclass
class PackMetadata:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    skills: List[Dict] = field(default_factory=list)
    ontology_terms: List[Dict] = field(default_factory=list)
    ontology_relations: List[Dict] = field(default_factory=list)
    playbook_steps: List[Dict] = field(default_factory=list)
    competency_questions: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> 'PackMetadata':
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            skills=data.get("skills", []),
            ontology_terms=data.get("ontology_terms", []),
            ontology_relations=data.get("ontology_relations", []),
            playbook_steps=data.get("playbook_steps", []),
            competency_questions=data.get("competency_questions", []),
        )

    def to_skills(self) -> List[Skill]:
        result = []
        for s in self.skills:
            manifest = None
            if "manifest" in s:
                m = s["manifest"]
                manifest = SkillManifest(
                    capabilities=m.get("capabilities", []),
                    task_types=m.get("task_types", []),
                    artifact_types=m.get("artifact_types", []),
                    domain=m.get("domain", self.category),
                    tags=m.get("tags", []),
                )
            result.append(Skill(
                name=s["name"],
                principle=s.get("principle", ""),
                when_to_apply=s.get("when_to_apply", ""),
                source=f"pack:{self.name}",
                category=s.get("category", self.category),
                manifest=manifest,
            ))
        return result

    def to_ontology_bundle(self) -> Optional[OntologyBundle]:
        if not self.ontology_terms:
            return None
        terms = [OntologyTerm(**t) for t in self.ontology_terms]
        relations = [OntologyRelation(**r) for r in self.ontology_relations]
        return OntologyBundle(
            bundle_id=f"pack-{self.name}",
            version=self.version,
            namespace="sw",
            terms=terms,
            relations=relations,
            competency_questions=self.competency_questions,
        )


class PackManager:
    """Manage skill pack installation and loading."""

    def __init__(self, packs_dir: str = None):
        self.user_dir = packs_dir or USER_PACKS_DIR
        self._installed: Dict[str, PackMetadata] = {}
        self._scan_builtin()
        self._scan_user()

    def _scan_builtin(self):
        if not os.path.isdir(PACKS_DIR):
            return
        for name in os.listdir(PACKS_DIR):
            pack_dir = os.path.join(PACKS_DIR, name)
            meta = self._load_pack(pack_dir)
            if meta:
                self._installed[meta.name] = meta

    def _scan_user(self):
        if not os.path.isdir(self.user_dir):
            return
        for name in os.listdir(self.user_dir):
            pack_dir = os.path.join(self.user_dir, name)
            meta = self._load_pack(pack_dir)
            if meta:
                self._installed[meta.name] = meta

    def _load_pack(self, pack_dir: str) -> Optional[PackMetadata]:
        yaml_path = os.path.join(pack_dir, "pack.yaml")
        json_path = os.path.join(pack_dir, "pack.json")
        if os.path.isfile(yaml_path):
            try:
                import yaml
                with open(yaml_path) as f:
                    return PackMetadata.from_dict(yaml.safe_load(f))
            except ImportError:
                pass
        if os.path.isfile(json_path):
            with open(json_path) as f:
                return PackMetadata.from_dict(json.load(f))
        return None

    def install(self, pack_name: str) -> bool:
        """Install a built-in pack by name."""
        builtin = os.path.join(PACKS_DIR, pack_name)
        if not os.path.isdir(builtin):
            return False
        meta = self._load_pack(builtin)
        if meta:
            self._installed[meta.name] = meta
            return True
        return False

    def install_from_path(self, path: str) -> bool:
        """Install a pack from a directory path."""
        meta = self._load_pack(path)
        if not meta:
            return False
        # Copy to user packs dir
        dest = os.path.join(self.user_dir, meta.name)
        os.makedirs(dest, exist_ok=True)
        for f in os.listdir(path):
            src = os.path.join(path, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(dest, f))
        self._installed[meta.name] = meta
        return True

    def uninstall(self, pack_name: str) -> bool:
        """Remove an installed pack."""
        if pack_name in self._installed:
            del self._installed[pack_name]
            user_path = os.path.join(self.user_dir, pack_name)
            if os.path.isdir(user_path):
                shutil.rmtree(user_path)
            return True
        return False

    def list_installed(self) -> List[Dict]:
        """List all installed packs."""
        return [
            {"name": m.name, "version": m.version, "description": m.description,
             "category": m.category, "skills": len(m.skills),
             "ontology_terms": len(m.ontology_terms), "tags": m.tags}
            for m in self._installed.values()
        ]

    def list_available(self) -> List[str]:
        """List built-in packs available for installation."""
        if not os.path.isdir(PACKS_DIR):
            return []
        available = []
        for name in os.listdir(PACKS_DIR):
            if os.path.isdir(os.path.join(PACKS_DIR, name)):
                available.append(name)
        return sorted(available)

    def get(self, pack_name: str) -> Optional[PackMetadata]:
        return self._installed.get(pack_name)

    def apply(self, bank: SkillBank = None) -> Tuple[SkillBank, List[OntologyBundle]]:
        """Apply all installed packs to a SkillBank. Returns (bank, ontology_bundles)."""
        if bank is None:
            bank = SkillBank()
        bundles = []
        for meta in self._installed.values():
            for skill in meta.to_skills():
                bank.add(skill)
            bundle = meta.to_ontology_bundle()
            if bundle:
                bundles.append(bundle)
        return bank, bundles

    def apply_single(self, pack_name: str, bank: SkillBank = None) -> Tuple[SkillBank, Optional[OntologyBundle]]:
        """Apply a single pack."""
        meta = self._installed.get(pack_name)
        if not meta:
            return bank or SkillBank(), None
        if bank is None:
            bank = SkillBank()
        for skill in meta.to_skills():
            bank.add(skill)
        return bank, meta.to_ontology_bundle()
