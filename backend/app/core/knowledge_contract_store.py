from __future__ import annotations

import json
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.db_models import (
    KnowledgeEntityModel,
    KnowledgeRelationshipModel,
    StudioOrganizationMembershipModel,
    StudioTeamMembershipModel,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC)


class KnowledgeContractStore:
    def _conflict_rank(self, entity: dict[str, Any]) -> tuple[int, int, float, float, str]:
        kind = str(entity.get("kind", "")).strip().lower()
        kind_priority = 4 if kind == "policy" else 0
        source = entity.get("source", {}) if isinstance(entity.get("source"), dict) else {}
        quality = entity.get("quality", {}) if isinstance(entity.get("quality"), dict) else {}
        verification = str(quality.get("verification_state", "asserted")).strip().lower()
        verification_priority = {"inferred": 1, "derived": 2, "verified": 3}.get(verification, 1)
        source_priority = 2 if bool(source.get("source_of_truth", False)) else 1
        confidence_raw = quality.get("confidence", 0.0)
        confidence = float(confidence_raw) if isinstance(confidence_raw, int | float) else 0.0
        observed = _parse_dt(entity.get("timestamps", {}).get("observed_at"))
        observed_ts = observed.timestamp() if observed else 0.0
        entity_id = str(entity.get("entity_id", ""))
        return (kind_priority, source_priority + verification_priority, confidence, observed_ts, entity_id)

    def _dedupe_key(self, entity: dict[str, Any]) -> str:
        source = entity.get("source", {}) if isinstance(entity.get("source"), dict) else {}
        raw = str(source.get("dedupe_key", "")).strip()
        if raw:
            return raw
        external_ref = str(source.get("external_ref", "")).strip()
        if external_ref:
            return external_ref
        return str(entity.get("entity_id", "")).strip()
    def _is_org_member(self, *, tenant_id: str, org_id: str, user_id: str) -> bool:
        with SessionLocal() as db:
            membership_id = db.scalar(
                select(StudioOrganizationMembershipModel.membership_id).where(
                    StudioOrganizationMembershipModel.tenant_id == tenant_id,
                    StudioOrganizationMembershipModel.org_id == org_id,
                    StudioOrganizationMembershipModel.user_id == user_id,
                    StudioOrganizationMembershipModel.status == "active",
                )
            )
            return membership_id is not None

    def _is_team_member(self, *, tenant_id: str, team_id: str, user_id: str) -> bool:
        with SessionLocal() as db:
            membership_id = db.scalar(
                select(StudioTeamMembershipModel.team_membership_id).where(
                    StudioTeamMembershipModel.tenant_id == tenant_id,
                    StudioTeamMembershipModel.team_id == team_id,
                    StudioTeamMembershipModel.user_id == user_id,
                    StudioTeamMembershipModel.status == "active",
                )
            )
            return membership_id is not None

    def _entity_dict(self, row: KnowledgeEntityModel) -> dict[str, Any]:
        return {
            "entity_id": row.entity_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "kind": row.kind,
            "kind_schema_version": row.kind_schema_version,
            "title": row.title,
            "summary": row.summary,
            "tags": json.loads(row.tags_json),
            "contexts": json.loads(row.contexts_json),
            "facets": json.loads(row.facets_json),
            "owners": json.loads(row.owners_json),
            "visibility": json.loads(row.visibility_json),
            "source": json.loads(row.source_json),
            "content_refs": json.loads(row.content_refs_json),
            "quality": json.loads(row.quality_json),
            "lifecycle": json.loads(row.lifecycle_json),
            "timestamps": {
                "created_at": _iso(row.created_at),
                "updated_at": _iso(row.updated_at),
                "observed_at": _iso(row.observed_at),
                "effective_from": _iso(row.effective_from),
                "effective_to": _iso(row.effective_to),
            },
            "kind_payload": json.loads(row.kind_payload_json),
            "schema_version": row.schema_version,
        }

    def _relationship_dict(self, row: KnowledgeRelationshipModel) -> dict[str, Any]:
        return {
            "relationship_id": row.relationship_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "from_entity_id": row.from_entity_id,
            "to_entity_id": row.to_entity_id,
            "relationship_type": row.relationship_type,
            "directionality": row.directionality,
            "weight": row.weight,
            "facets": json.loads(row.facets_json),
            "evidence": json.loads(row.evidence_json),
            "visibility": json.loads(row.visibility_json),
            "source": json.loads(row.source_json),
            "timestamps": {
                "created_at": _iso(row.created_at),
                "updated_at": _iso(row.updated_at),
                "observed_at": _iso(row.observed_at),
                "effective_from": _iso(row.effective_from),
                "effective_to": _iso(row.effective_to),
            },
            "schema_version": row.schema_version,
        }

    def upsert_entities(self, *, tenant_id: str, org_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = _utc_now()
        saved: list[dict[str, Any]] = []
        with SessionLocal() as db:
            for item in items:
                entity_id = str(item["entity_id"])
                row = db.scalar(
                    select(KnowledgeEntityModel).where(
                        KnowledgeEntityModel.tenant_id == tenant_id,
                        KnowledgeEntityModel.org_id == org_id,
                        KnowledgeEntityModel.entity_id == entity_id,
                    )
                )
                created_at = now
                if row is None:
                    row = KnowledgeEntityModel(
                        entity_id=entity_id,
                        tenant_id=tenant_id,
                        org_id=org_id,
                        created_at=now,
                    )
                else:
                    created_at = row.created_at

                ts = item.get("timestamps", {}) if isinstance(item.get("timestamps"), dict) else {}
                row.kind = str(item["kind"])
                row.kind_schema_version = str(item.get("kind_schema_version", "v1"))
                row.title = str(item["title"])
                row.summary = str(item.get("summary", ""))
                row.tags_json = json.dumps(item.get("tags", []))
                row.contexts_json = json.dumps(item.get("contexts", []))
                row.facets_json = json.dumps(item.get("facets", {}))
                row.owners_json = json.dumps(item.get("owners", []))
                row.visibility_json = json.dumps(item.get("visibility", {}))
                row.source_json = json.dumps(item.get("source", {}))
                row.content_refs_json = json.dumps(item.get("content_refs", []))
                row.quality_json = json.dumps(item.get("quality", {}))
                row.lifecycle_json = json.dumps(item.get("lifecycle", {}))
                row.kind_payload_json = json.dumps(item.get("kind_payload", {}))
                row.observed_at = _parse_dt(ts.get("observed_at")) or now
                row.effective_from = _parse_dt(ts.get("effective_from"))
                row.effective_to = _parse_dt(ts.get("effective_to"))
                row.schema_version = str(item.get("schema_version", "v1"))
                row.created_at = created_at
                row.updated_at = now
                db.add(row)
                db.flush()
                saved.append(self._entity_dict(row))
            db.commit()
        return saved

    def upsert_relationships(
        self, *, tenant_id: str, org_id: str, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        now = _utc_now()
        saved: list[dict[str, Any]] = []
        with SessionLocal() as db:
            for item in items:
                relationship_id = str(item["relationship_id"])
                row = db.scalar(
                    select(KnowledgeRelationshipModel).where(
                        KnowledgeRelationshipModel.tenant_id == tenant_id,
                        KnowledgeRelationshipModel.org_id == org_id,
                        KnowledgeRelationshipModel.relationship_id == relationship_id,
                    )
                )
                created_at = now
                if row is None:
                    row = KnowledgeRelationshipModel(
                        relationship_id=relationship_id,
                        tenant_id=tenant_id,
                        org_id=org_id,
                        created_at=now,
                    )
                else:
                    created_at = row.created_at
                ts = item.get("timestamps", {}) if isinstance(item.get("timestamps"), dict) else {}
                row.from_entity_id = str(item["from_entity_id"])
                row.to_entity_id = str(item["to_entity_id"])
                row.relationship_type = str(item["relationship_type"])
                row.directionality = str(item.get("directionality", "directed"))
                row.weight = float(item.get("weight", 1.0))
                row.facets_json = json.dumps(item.get("facets", {}))
                row.evidence_json = json.dumps(item.get("evidence", []))
                row.visibility_json = json.dumps(item.get("visibility", {}))
                row.source_json = json.dumps(item.get("source", {}))
                row.observed_at = _parse_dt(ts.get("observed_at")) or now
                row.effective_from = _parse_dt(ts.get("effective_from"))
                row.effective_to = _parse_dt(ts.get("effective_to"))
                row.schema_version = str(item.get("schema_version", "v1"))
                row.created_at = created_at
                row.updated_at = now
                db.add(row)
                db.flush()
                saved.append(self._relationship_dict(row))
            db.commit()
        return saved

    def _allows_visibility(
        self,
        visibility: dict[str, Any],
        *,
        user_id: str,
        tenant_id: str,
        org_id: str,
        org_memberships: set[str] | None = None,
        team_memberships: set[str] | None = None,
    ) -> bool:
        scope = str(visibility.get("scope", "")).strip()
        acl_policy_id = str(visibility.get("acl_policy_id", "")).strip()
        if not scope or not acl_policy_id:
            return False

        allowed_user_ids = visibility.get("user_ids", [])
        if isinstance(allowed_user_ids, list) and user_id in {str(item) for item in allowed_user_ids}:
            return True

        if scope == "private":
            owner_user_id = visibility.get("owner_user_id")
            return owner_user_id == user_id

        if scope == "user":
            return str(visibility.get("user_id", "")).strip() == user_id

        if scope == "team":
            team_id = str(visibility.get("team_id", "")).strip()
            if not team_id:
                return False
            if team_memberships is not None:
                return team_id in team_memberships
            return self._is_team_member(tenant_id=tenant_id, team_id=team_id, user_id=user_id)

        if scope == "group":
            group_team_id = str(visibility.get("group_id", "")).strip()
            if not group_team_id:
                return False
            if team_memberships is not None:
                return group_team_id in team_memberships
            return self._is_team_member(tenant_id=tenant_id, team_id=group_team_id, user_id=user_id)

        if scope in {"org", "restricted"}:
            target_org_id = str(visibility.get("org_id", org_id)).strip() or org_id
            if target_org_id != org_id:
                return False
            if visibility.get("require_membership", False):
                if org_memberships is not None:
                    return target_org_id in org_memberships
                return self._is_org_member(tenant_id=tenant_id, org_id=target_org_id, user_id=user_id)
            return True

        if scope == "tenant":
            return True
        return False

    def resolve(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        anchor_entity_id: str | None,
        anchor_text: str,
        include_node_kinds: set[str],
        include_relationship_types: set[str],
        max_nodes: int,
        max_edges: int,
        max_snippets: int,
        max_tokens: int,
        debug: bool,
    ) -> dict[str, Any]:
        now = _utc_now()
        exclusions: list[dict[str, str]] = []
        with SessionLocal() as db:
            org_memberships = {
                str(value)
                for value in db.scalars(
                    select(StudioOrganizationMembershipModel.org_id).where(
                        StudioOrganizationMembershipModel.tenant_id == tenant_id,
                        StudioOrganizationMembershipModel.user_id == user_id,
                        StudioOrganizationMembershipModel.status == "active",
                    )
                ).all()
            }
            team_memberships = {
                str(value)
                for value in db.scalars(
                    select(StudioTeamMembershipModel.team_id).where(
                        StudioTeamMembershipModel.tenant_id == tenant_id,
                        StudioTeamMembershipModel.user_id == user_id,
                        StudioTeamMembershipModel.status == "active",
                    )
                ).all()
            }

            all_entities = db.scalars(
                select(KnowledgeEntityModel).where(
                    KnowledgeEntityModel.tenant_id == tenant_id,
                    KnowledgeEntityModel.org_id == org_id,
                )
            ).all()

            allowed_entities: dict[str, dict[str, Any]] = {}
            for row in all_entities:
                entity = self._entity_dict(row)
                visibility = entity.get("visibility", {})
                if not isinstance(visibility, dict) or not self._allows_visibility(
                    visibility,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    org_id=org_id,
                    org_memberships=org_memberships,
                    team_memberships=team_memberships,
                ):
                    exclusions.append({"entity_id": row.entity_id, "reason": "acl_denied"})
                    continue
                if include_node_kinds and entity.get("kind") not in include_node_kinds:
                    exclusions.append({"entity_id": row.entity_id, "reason": "scope_filtered"})
                    continue
                lifecycle = entity.get("lifecycle", {})
                if isinstance(lifecycle, dict) and lifecycle.get("status") == "archived":
                    exclusions.append({"entity_id": row.entity_id, "reason": "scope_filtered"})
                    continue
                ttl_seconds = 0
                if isinstance(lifecycle, dict):
                    ttl_raw = lifecycle.get("staleness_ttl_seconds")
                    ttl_seconds = int(ttl_raw) if isinstance(ttl_raw, int | float) else 0
                observed_at = _parse_dt(entity.get("timestamps", {}).get("observed_at"))
                if ttl_seconds > 0 and observed_at and observed_at + timedelta(seconds=ttl_seconds) < now:
                    exclusions.append({"entity_id": row.entity_id, "reason": "stale"})
                    continue
                allowed_entities[row.entity_id] = entity

            deduped_entities_by_id: dict[str, dict[str, Any]] = {}
            dedupe_buckets: dict[str, list[dict[str, Any]]] = {}
            for entity in allowed_entities.values():
                dedupe_buckets.setdefault(self._dedupe_key(entity), []).append(entity)
            for bucket_items in dedupe_buckets.values():
                if len(bucket_items) == 1:
                    only = bucket_items[0]
                    deduped_entities_by_id[str(only["entity_id"])] = only
                    continue
                ranked = sorted(bucket_items, key=self._conflict_rank, reverse=True)
                winner = ranked[0]
                deduped_entities_by_id[str(winner["entity_id"])] = winner
                for loser in ranked[1:]:
                    exclusions.append({"entity_id": str(loser["entity_id"]), "reason": "conflict_lost"})

            rel_rows = db.scalars(
                select(KnowledgeRelationshipModel).where(
                    KnowledgeRelationshipModel.tenant_id == tenant_id,
                    KnowledgeRelationshipModel.org_id == org_id,
                )
            ).all()

            adjacency: dict[str, list[tuple[str, str]]] = {}
            allowed_edges = 0
            for row in rel_rows:
                rel = self._relationship_dict(row)
                if include_relationship_types and rel["relationship_type"] not in include_relationship_types:
                    continue
                if row.from_entity_id not in deduped_entities_by_id or row.to_entity_id not in deduped_entities_by_id:
                    exclusions.append({"entity_id": row.relationship_id, "reason": "edge_acl_denied"})
                    continue
                visibility = rel.get("visibility", {})
                if not isinstance(visibility, dict) or not self._allows_visibility(
                    visibility,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    org_id=org_id,
                    org_memberships=org_memberships,
                    team_memberships=team_memberships,
                ):
                    exclusions.append({"entity_id": row.relationship_id, "reason": "edge_acl_denied"})
                    continue
                adjacency.setdefault(row.from_entity_id, []).append((row.to_entity_id, row.relationship_type))
                if rel.get("directionality") == "bidirectional":
                    adjacency.setdefault(row.to_entity_id, []).append((row.from_entity_id, row.relationship_type))
                allowed_edges += 1

        terms = [term for term in anchor_text.lower().split() if term]
        distances: dict[str, int] = {}
        parent: dict[str, tuple[str, str]] = {}
        if anchor_entity_id and anchor_entity_id in deduped_entities_by_id:
            queue: deque[tuple[str, int]] = deque([(anchor_entity_id, 0)])
            distances[anchor_entity_id] = 0
            while queue:
                current, depth = queue.popleft()
                if depth >= 4:
                    continue
                for neighbor, rel_type in adjacency.get(current, []):
                    if neighbor in distances:
                        continue
                    distances[neighbor] = depth + 1
                    parent[neighbor] = (current, rel_type)
                    queue.append((neighbor, depth + 1))

        def _path_for(entity_id: str) -> list[dict[str, str]]:
            hops: list[dict[str, str]] = []
            cursor = entity_id
            limit = 4
            while cursor in parent and limit > 0:
                prev, rel_type = parent[cursor]
                hops.append({"from": prev, "rel": rel_type, "to": cursor})
                cursor = prev
                limit -= 1
            hops.reverse()
            return hops

        scored: list[dict[str, Any]] = []
        for entity in deduped_entities_by_id.values():
            text = (
                f"{entity.get('title', '')} {entity.get('summary', '')} {' '.join(entity.get('tags', []))}"
            ).lower()
            semantic = 0.0
            if terms:
                semantic = sum(1 for term in terms if term in text) / max(1, len(terms))
            distance = distances.get(entity["entity_id"], 99)
            graph_proximity = 1.0 if distance == 0 else (0.8 if distance == 1 else (0.6 if distance == 2 else (0.4 if distance == 3 else 0.2)))
            authority = 0.9 if entity.get("kind") == "policy" else 0.6
            updated_at = _parse_dt(entity.get("timestamps", {}).get("updated_at"))
            freshness = 1.0
            if updated_at is not None:
                age_days = max(0.0, (now - updated_at).total_seconds() / 86400.0)
                freshness = max(0.2, 1.0 - min(0.8, age_days / 30.0))
            permission = 1.0
            final = round(
                semantic * 0.4 + graph_proximity * 0.3 + authority * 0.1 + freshness * 0.1 + permission * 0.1,
                4,
            )
            reasons = {
                "semantic_match": semantic,
                "graph_proximity": graph_proximity,
                "owner_authority": authority,
                "freshness_boost": freshness,
                "policy_priority": 0.0,
            }
            reason_code = max(reasons, key=reasons.get)
            scored.append(
                {
                    "entity": entity,
                    "final": final,
                    "reason_code": reason_code,
                    "reason_short": f"Selected via {reason_code.replace('_', ' ')}",
                    "path": _path_for(entity["entity_id"]),
                    "scores": {
                        "semantic": round(semantic, 4),
                        "graph_proximity": round(graph_proximity, 4),
                        "authority": round(authority, 4),
                        "freshness": round(freshness, 4),
                        "permission_suitability": permission,
                        "final": final,
                    },
                }
            )

        scored.sort(
            key=lambda item: (
                item["final"],
                item["scores"]["semantic"],
                item["scores"]["graph_proximity"],
                item["scores"]["authority"],
                str(item["entity"]["entity_id"]),
            ),
            reverse=True,
        )
        selected = scored[:max_nodes]
        if len(scored) > max_nodes:
            for item in scored[max_nodes:]:
                exclusions.append({"entity_id": item["entity"]["entity_id"], "reason": "budget_exceeded"})

        sources: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        for item in selected:
            entity = item["entity"]
            sources.append(
                {
                    "entity_id": entity["entity_id"],
                    "kind": entity.get("kind"),
                    "title": entity.get("title"),
                    "score": item["final"],
                    "selection_reason_code": item["reason_code"],
                    "selection_reason_short": item["reason_short"],
                    "primary_path": item["path"][:4],
                }
            )
            provenance.append(
                {
                    "entity_id": entity["entity_id"],
                    "selection_reason": item["reason_short"],
                    "path": item["path"][:4],
                    "scores": item["scores"],
                }
            )

        return {
            "bundle_id": f"ctx_{int(now.timestamp() * 1000)}",
            "graph_version": now.isoformat(),
            "cache": {"hit": False, "cache_key": "", "ttl_seconds": 0},
            "tiers": {
                "constraints": [src for src in sources if src.get("kind") == "policy"],
                "core_evidence": [src for src in sources if src.get("kind") != "policy"][: max(1, max_snippets // 2)],
                "supplemental": [src for src in sources][max(1, max_snippets // 2) : max_snippets],
            },
            "sources": sources[:max_snippets],
            "provenance": provenance,
            "inferred_tags": [],
            "inferred_contexts": [],
            "exclusion_report": exclusions if debug else [],
            "summary": {
                "selected_nodes": len(sources[:max_snippets]),
                "selected_edges": min(allowed_edges, max_edges),
                "max_tokens": max_tokens,
            },
        }


knowledge_contract_store = KnowledgeContractStore()
