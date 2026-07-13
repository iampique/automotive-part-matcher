"""
Neo4j graph database service for connector relationship queries.

Provides impact analysis, compliance inheritance, and supplier topology
queries. When not configured the service reports
disabled and API routes return 503.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver

from app.config import settings
from app.models import (
    AffectedAssembly,
    AffectedVehicle,
    AssemblyComplianceResponse,
    ComplianceGap,
    ComplianceRequirement,
    Connector,
    ConnectorComplianceResponse,
    GraphSeedData,
    ImpactAnalysisResponse,
    PartSourcing,
    SpofEntry,
    SpofResponse,
    SupplierConnectorEntry,
    SupplierConnectorsResponse,
    SupplierRiskEntry,
    SupplierRiskResponse,
)

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "neo4j" / "schema.cypher"

CERT_TO_REQUIREMENT = {
    "RoHS": "req-rohs",
    "REACH": "req-reach",
    "IATF 16949": "req-iatf16949",
    "ISO 9001": "req-iso9001",
    "AEC-Q200": "req-aec-q200",
    "UL": "req-ul",
}


class Neo4jService:
    """Graph database client for automotive connector relationships."""

    def __init__(self) -> None:
        self._driver: Optional[Driver] = None
        if settings.neo4j_enabled:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            logger.info("Neo4j driver initialized")
        else:
            logger.info("Neo4j disabled (NEO4J_URI or NEO4J_PASSWORD not set)")

    @property
    def enabled(self) -> bool:
        return self._driver is not None

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def verify_connectivity(self) -> bool:
        if not self._driver:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning("Neo4j connectivity check failed: %s", e)
            return False

    def _run(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self._driver:
            raise RuntimeError("Neo4j is not configured")
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def run_schema_migration(self) -> None:
        if not self._driver:
            raise RuntimeError("Neo4j is not configured")
        statements = SCHEMA_PATH.read_text(encoding="utf-8").strip().split(";\n")
        with self._driver.session() as session:
            for stmt in statements:
                stmt = stmt.strip()
                if stmt:
                    session.run(stmt)
        logger.info("Neo4j schema migration applied")

    def upsert_graph(
        self,
        seed: GraphSeedData,
        connectors: List[Connector],
    ) -> Dict[str, int]:
        if not self._driver:
            raise RuntimeError("Neo4j is not configured")

        self.run_schema_migration()
        counts: Dict[str, int] = {}

        with self._driver.session() as session:
            # Requirements
            for req in seed.requirements:
                session.run(
                    """
                    MERGE (r:Requirement {id: $id})
                    SET r.name = $name, r.standard = $standard, r.severity = $severity
                    """,
                    id=req.id,
                    name=req.name,
                    standard=req.standard,
                    severity=req.severity,
                )
            counts["requirements"] = len(seed.requirements)

            # Requirement hierarchy
            for rh in seed.requirement_hierarchy:
                session.run(
                    """
                    MATCH (child:Requirement {id: $child_id})
                    MATCH (parent:Requirement {id: $parent_id})
                    MERGE (child)-[:INHERITS_FROM]->(parent)
                    """,
                    child_id=rh.child_id,
                    parent_id=rh.parent_id,
                )
            counts["requirement_hierarchy"] = len(seed.requirement_hierarchy)

            # Suppliers
            for sup in seed.suppliers:
                session.run(
                    """
                    MERGE (s:Supplier {id: $id})
                    SET s.name = $name, s.region = $region, s.tier = $tier
                    """,
                    id=sup.id,
                    name=sup.name,
                    region=sup.region,
                    tier=sup.tier,
                )
            counts["suppliers"] = len(seed.suppliers)

            # Assemblies (parents first)
            assemblies_sorted = sorted(
                seed.assemblies,
                key=lambda a: (a.parent_id is not None, a.id),
            )
            for asm in assemblies_sorted:
                session.run(
                    """
                    MERGE (a:Assembly {id: $id})
                    SET a.name = $name, a.criticality = $criticality
                    """,
                    id=asm.id,
                    name=asm.name,
                    criticality=asm.criticality,
                )
                if asm.parent_id:
                    session.run(
                        """
                        MATCH (child:Assembly {id: $child_id})
                        MATCH (parent:Assembly {id: $parent_id})
                        MERGE (parent)-[:CONTAINS]->(child)
                        """,
                        child_id=asm.id,
                        parent_id=asm.parent_id,
                    )
                for req_id in asm.requirement_ids:
                    session.run(
                        """
                        MATCH (a:Assembly {id: $asm_id})
                        MATCH (r:Requirement {id: $req_id})
                        MERGE (a)-[:REQUIRES]->(r)
                        """,
                        asm_id=asm.id,
                        req_id=req_id,
                    )
            counts["assemblies"] = len(seed.assemblies)

            # Vehicles
            for veh in seed.vehicles:
                session.run(
                    """
                    MERGE (v:Vehicle {id: $id})
                    SET v.name = $name, v.platform = $platform, v.model_year = $model_year
                    """,
                    id=veh.id,
                    name=veh.name,
                    platform=veh.platform,
                    model_year=veh.model_year,
                )
            counts["vehicles"] = len(seed.vehicles)

            for va in seed.vehicle_assemblies:
                session.run(
                    """
                    MATCH (v:Vehicle {id: $vehicle_id})
                    MATCH (a:Assembly {id: $assembly_id})
                    MERGE (v)-[:USES]->(a)
                    """,
                    vehicle_id=va["vehicle_id"],
                    assembly_id=va["assembly_id"],
                )
            counts["vehicle_assemblies"] = len(seed.vehicle_assemblies)

            # Connectors from catalog
            for conn in connectors:
                session.run(
                    """
                    MERGE (c:Connector {part_number: $part_number})
                    SET c.name = $name, c.connector_type = $connector_type
                    """,
                    part_number=conn.part_number,
                    name=conn.name,
                    connector_type=conn.connector_type,
                )
                for app in conn.applications:
                    session.run(
                        """
                        MERGE (app:Application {name: $name})
                        WITH app
                        MATCH (c:Connector {part_number: $part_number})
                        MERGE (c)-[:USED_IN_APP]->(app)
                        """,
                        name=app,
                        part_number=conn.part_number,
                    )
                for cert in conn.certifications:
                    session.run(
                        """
                        MERGE (cert:Certification {name: $name})
                        WITH cert
                        MATCH (c:Connector {part_number: $part_number})
                        MERGE (c)-[:HAS_CERT]->(cert)
                        """,
                        name=cert,
                        part_number=conn.part_number,
                    )
            counts["connectors"] = len(connectors)

            # BOM lines
            for bom in seed.bom_lines:
                session.run(
                    """
                    MATCH (a:Assembly {id: $assembly_id})
                    MATCH (c:Connector {part_number: $part_number})
                    MERGE (a)-[r:USES_PART]->(c)
                    SET r.qty = $qty, r.critical = $critical
                    """,
                    assembly_id=bom.assembly_id,
                    part_number=bom.part_number,
                    qty=bom.qty,
                    critical=bom.critical,
                )
            counts["bom_lines"] = len(seed.bom_lines)

            # Sourcing
            for src in seed.sourcing:
                session.run(
                    """
                    MATCH (c:Connector {part_number: $part_number})
                    MATCH (s:Supplier {id: $supplier_id})
                    MERGE (c)-[r:SUPPLIED_BY]->(s)
                    SET r.share_pct = $share_pct, r.sole_source = $sole_source
                    """,
                    part_number=src.part_number,
                    supplier_id=src.supplier_id,
                    share_pct=src.share_pct,
                    sole_source=src.sole_source,
                )
            counts["sourcing"] = len(seed.sourcing)

        return counts

    def get_impact(self, part_number: str) -> ImpactAnalysisResponse:
        rows = self._run(
            """
            MATCH (c:Connector {part_number: $pn})<-[r:USES_PART]-(a:Assembly)
            OPTIONAL MATCH (v:Vehicle)-[:USES]->(directAsm:Assembly)
            WHERE directAsm = a OR (directAsm)-[:CONTAINS*]->(a)
            WITH c, a, r, collect(DISTINCT v) AS vehicles
            RETURN c.name AS connector_name,
                   a.id AS assembly_id,
                   a.name AS assembly_name,
                   a.criticality AS criticality,
                   r.qty AS qty,
                   r.critical AS critical,
                   [v IN vehicles WHERE v IS NOT NULL | {
                       id: v.id, name: v.name, platform: v.platform, model_year: v.model_year
                   }] AS vehicle_list
            """,
            {"pn": part_number},
        )

        if not rows:
            return ImpactAnalysisResponse(
                part_number=part_number,
                affected_vehicles=[],
                affected_assemblies=[],
                critical_paths=[],
                total_bom_qty=0,
            )

        connector_name = rows[0].get("connector_name")
        assemblies: Dict[str, AffectedAssembly] = {}
        vehicles: Dict[str, AffectedVehicle] = {}
        critical_paths: List[str] = []
        total_qty = 0

        for row in rows:
            asm_id = row["assembly_id"]
            qty = row["qty"] or 1
            critical = bool(row["critical"])
            total_qty += qty

            if asm_id not in assemblies:
                assemblies[asm_id] = AffectedAssembly(
                    id=asm_id,
                    name=row["assembly_name"],
                    criticality=row["criticality"] or "medium",
                    qty=qty,
                    critical=critical,
                )
            else:
                assemblies[asm_id].qty += qty

            if critical:
                critical_paths.append(f"{row['assembly_name']} (qty {qty})")

            for v in row.get("vehicle_list") or []:
                if v and v.get("id"):
                    vehicles[v["id"]] = AffectedVehicle(**v)

        return ImpactAnalysisResponse(
            part_number=part_number,
            connector_name=connector_name,
            affected_vehicles=list(vehicles.values()),
            affected_assemblies=list(assemblies.values()),
            critical_paths=critical_paths,
            total_bom_qty=total_qty,
        )

    def get_assembly_compliance(self, assembly_id: str) -> AssemblyComplianceResponse:
        rows = self._run(
            """
            MATCH (root:Assembly {id: $id})
            OPTIONAL MATCH (root)-[:CONTAINS*0..]->(desc:Assembly)
            WITH collect(DISTINCT desc) + root AS allAssemblies
            UNWIND allAssemblies AS asm
            MATCH (asm)-[:REQUIRES]->(req:Requirement)
            OPTIONAL MATCH (req)-[:INHERITS_FROM*]->(inherited:Requirement)
            RETURN DISTINCT
                asm.id AS source_assembly_id,
                asm.name AS source_assembly_name,
                req.id AS req_id,
                req.name AS req_name,
                req.standard AS standard,
                req.severity AS severity,
                inherited.id AS inherited_id,
                inherited.name AS inherited_name
            """,
            {"id": assembly_id},
        )

        assembly_name = assembly_id
        name_row = self._run(
            "MATCH (a:Assembly {id: $id}) RETURN a.name AS name",
            {"id": assembly_id},
        )
        if name_row:
            assembly_name = name_row[0]["name"]

        requirements: List[ComplianceRequirement] = []
        seen: set = set()

        for row in rows:
            key = (row["req_id"], row["source_assembly_id"])
            if key not in seen:
                seen.add(key)
                requirements.append(
                    ComplianceRequirement(
                        id=row["req_id"],
                        name=row["req_name"],
                        standard=row["standard"],
                        severity=row["severity"],
                        source_assembly_id=row["source_assembly_id"],
                        source_assembly_name=row["source_assembly_name"],
                        inherited_from=row.get("inherited_name"),
                    )
                )
            if row.get("inherited_id"):
                inh_key = (row["inherited_id"], row["source_assembly_id"])
                if inh_key not in seen:
                    seen.add(inh_key)
                    requirements.append(
                        ComplianceRequirement(
                            id=row["inherited_id"],
                            name=row["inherited_name"],
                            standard=row.get("standard", ""),
                            severity=row.get("severity", "medium"),
                            source_assembly_id=row["source_assembly_id"],
                            source_assembly_name=row["source_assembly_name"],
                            inherited_from=row["req_name"],
                        )
                    )

        return AssemblyComplianceResponse(
            assembly_id=assembly_id,
            assembly_name=assembly_name,
            requirements=requirements,
        )

    def get_connector_compliance(self, part_number: str) -> ConnectorComplianceResponse:
        rows = self._run(
            """
            MATCH (c:Connector {part_number: $pn})<-[:USES_PART]-(asm:Assembly)
            OPTIONAL MATCH (asm)-[:CONTAINS*0..]->(desc:Assembly)
            WITH c, collect(DISTINCT asm) + collect(DISTINCT desc) AS allAssemblies
            UNWIND allAssemblies AS a
            MATCH (a)-[:REQUIRES]->(req:Requirement)
            OPTIONAL MATCH (req)-[:INHERITS_FROM*]->(inherited:Requirement)
            RETURN DISTINCT
                c.name AS connector_name,
                a.id AS source_assembly_id,
                a.name AS source_assembly_name,
                req.id AS req_id,
                req.name AS req_name,
                req.standard AS standard,
                req.severity AS severity,
                inherited.id AS inherited_id,
                inherited.name AS inherited_name,
                inherited.standard AS inherited_standard,
                inherited.severity AS inherited_severity
            """,
            {"pn": part_number},
        )

        cert_rows = self._run(
            """
            MATCH (c:Connector {part_number: $pn})-[:HAS_CERT]->(cert:Certification)
            RETURN cert.name AS name
            """,
            {"pn": part_number},
        )
        return self._compliance_from_rows(part_number, rows, cert_rows)

    def _compliance_from_rows(
        self,
        part_number: str,
        rows: List[Dict[str, Any]],
        cert_rows: List[Dict[str, Any]],
    ) -> ConnectorComplianceResponse:
        certifications = [r["name"] for r in cert_rows]
        connector_name = None
        assemblies_set: set = set()
        requirements: List[ComplianceRequirement] = []
        seen: set = set()

        for row in rows:
            connector_name = row.get("connector_name")
            assemblies_set.add(row["source_assembly_name"])
            key = (row["req_id"], row["source_assembly_id"])
            if key not in seen:
                seen.add(key)
                requirements.append(
                    ComplianceRequirement(
                        id=row["req_id"],
                        name=row["req_name"],
                        standard=row["standard"],
                        severity=row["severity"],
                        source_assembly_id=row["source_assembly_id"],
                        source_assembly_name=row["source_assembly_name"],
                        inherited_from=row.get("inherited_name"),
                    )
                )
            # Expand requirement hierarchy so inherited parents are gap-checked too
            if row.get("inherited_id"):
                inh_key = (row["inherited_id"], row["source_assembly_id"])
                if inh_key not in seen:
                    seen.add(inh_key)
                    requirements.append(
                        ComplianceRequirement(
                            id=row["inherited_id"],
                            name=row["inherited_name"],
                            standard=row.get("inherited_standard")
                            or row.get("standard")
                            or "",
                            severity=row.get("inherited_severity")
                            or row.get("severity")
                            or "medium",
                            source_assembly_id=row["source_assembly_id"],
                            source_assembly_name=row["source_assembly_name"],
                            inherited_from=row["req_name"],
                        )
                    )

        gaps: List[ComplianceGap] = []
        req_cert_map = {
            "req-rohs": "RoHS",
            "req-reach": "REACH",
            "req-iatf16949": "IATF 16949",
            "req-iso9001": "ISO 9001",
            "req-aec-q200": "AEC-Q200",
            "req-ul": "UL",
            "req-iso26262-asil-d": "ISO 26262 ASIL-D",
        }
        for req in requirements:
            expected_cert = req_cert_map.get(req.id)
            if expected_cert and expected_cert not in certifications:
                gaps.append(
                    ComplianceGap(
                        requirement_id=req.id,
                        requirement_name=req.name,
                        standard=req.standard,
                        source_assembly_id=req.source_assembly_id,
                        source_assembly_name=req.source_assembly_name,
                    )
                )

        return ConnectorComplianceResponse(
            part_number=part_number,
            connector_name=connector_name,
            assemblies=sorted(assemblies_set),
            requirements=requirements,
            certifications=certifications,
            gaps=gaps,
        )

    def get_connector_compliance_batch(
        self, part_numbers: List[str]
    ) -> Dict[str, ConnectorComplianceResponse]:
        if not part_numbers:
            return {}

        req_rows = self._run(
            """
            UNWIND $pns AS pn
            MATCH (c:Connector {part_number: pn})<-[:USES_PART]-(asm:Assembly)
            OPTIONAL MATCH (asm)-[:CONTAINS*0..]->(desc:Assembly)
            WITH pn, c, collect(DISTINCT asm) + collect(DISTINCT desc) AS allAssemblies
            UNWIND allAssemblies AS a
            MATCH (a)-[:REQUIRES]->(req:Requirement)
            OPTIONAL MATCH (req)-[:INHERITS_FROM*]->(inherited:Requirement)
            RETURN DISTINCT
                   pn AS part_number,
                   c.name AS connector_name,
                   a.id AS source_assembly_id,
                   a.name AS source_assembly_name,
                   req.id AS req_id,
                   req.name AS req_name,
                   req.standard AS standard,
                   req.severity AS severity,
                   inherited.id AS inherited_id,
                   inherited.name AS inherited_name,
                   inherited.standard AS inherited_standard,
                   inherited.severity AS inherited_severity
            """,
            {"pns": part_numbers},
        )

        cert_rows = self._run(
            """
            UNWIND $pns AS pn
            MATCH (c:Connector {part_number: pn})-[:HAS_CERT]->(cert:Certification)
            RETURN pn AS part_number, cert.name AS name
            """,
            {"pns": part_numbers},
        )

        rows_by_pn: Dict[str, List[Dict[str, Any]]] = {pn: [] for pn in part_numbers}
        certs_by_pn: Dict[str, List[Dict[str, Any]]] = {pn: [] for pn in part_numbers}
        for row in req_rows:
            rows_by_pn.setdefault(row["part_number"], []).append(row)
        for row in cert_rows:
            certs_by_pn.setdefault(row["part_number"], []).append(row)

        return {
            pn: self._compliance_from_rows(pn, rows_by_pn.get(pn, []), certs_by_pn.get(pn, []))
            for pn in part_numbers
        }

    def get_part_sourcing(self, part_number: str) -> Optional[PartSourcing]:
        rows = self._run(
            """
            MATCH (c:Connector {part_number: $pn})-[sb:SUPPLIED_BY]->(s:Supplier)
            RETURN c.part_number AS part_number,
                   s.id AS supplier_id,
                   s.name AS supplier_name,
                   s.region AS region,
                   s.tier AS tier,
                   sb.share_pct AS share_pct,
                   sb.sole_source AS sole_source
            ORDER BY sb.share_pct DESC
            LIMIT 1
            """,
            {"pn": part_number},
        )
        if not rows:
            return None
        row = rows[0]
        return PartSourcing(
            part_number=row["part_number"],
            supplier_id=row["supplier_id"],
            supplier_name=row["supplier_name"],
            region=row["region"],
            tier=row["tier"],
            share_pct=float(row["share_pct"] or 100.0),
            sole_source=bool(row["sole_source"]),
        )

    def get_part_sourcing_batch(self, part_numbers: List[str]) -> Dict[str, PartSourcing]:
        if not part_numbers:
            return {}
        rows = self._run(
            """
            UNWIND $pns AS pn
            MATCH (c:Connector {part_number: pn})-[sb:SUPPLIED_BY]->(s:Supplier)
            WITH pn, s, sb
            ORDER BY sb.share_pct DESC
            WITH pn, collect({
                supplier_id: s.id,
                supplier_name: s.name,
                region: s.region,
                tier: s.tier,
                share_pct: sb.share_pct,
                sole_source: sb.sole_source
            })[0] AS top
            RETURN pn AS part_number,
                   top.supplier_id AS supplier_id,
                   top.supplier_name AS supplier_name,
                   top.region AS region,
                   top.tier AS tier,
                   top.share_pct AS share_pct,
                   top.sole_source AS sole_source
            """,
            {"pns": part_numbers},
        )
        result: Dict[str, PartSourcing] = {}
        for row in rows:
            result[row["part_number"]] = PartSourcing(
                part_number=row["part_number"],
                supplier_id=row["supplier_id"],
                supplier_name=row["supplier_name"],
                region=row["region"],
                tier=row["tier"],
                share_pct=float(row["share_pct"] or 100.0),
                sole_source=bool(row["sole_source"]),
            )
        return result

    def is_part_spof(self, part_number: str) -> bool:
        rows = self._run(
            """
            MATCH (s:Supplier)<-[sb:SUPPLIED_BY {sole_source: true}]-(c:Connector {part_number: $pn})
                  <-[up:USES_PART {critical: true}]-(:Assembly)
            RETURN count(*) AS cnt
            """,
            {"pn": part_number},
        )
        return bool(rows and rows[0]["cnt"] > 0)

    def get_supplier_risk(self) -> SupplierRiskResponse:
        rows = self._run(
            """
            MATCH (s:Supplier)<-[sb:SUPPLIED_BY]-(c:Connector)<-[up:USES_PART]-(a:Assembly)
            WHERE up.critical = true
            WITH s,
                 count(DISTINCT c) AS parts,
                 count(DISTINCT a) AS assemblies,
                 sum(CASE WHEN sb.sole_source THEN 1 ELSE 0 END) AS sole_source_count
            RETURN s.id AS supplier_id,
                   s.name AS supplier_name,
                   s.region AS region,
                   s.tier AS tier,
                   parts AS critical_parts,
                   assemblies AS critical_assemblies,
                   sole_source_count AS sole_source_count
            ORDER BY sole_source_count DESC, parts DESC
            """
        )

        suppliers = []
        for row in rows:
            risk_score = (
                row["sole_source_count"] * 3
                + row["critical_parts"] * 0.5
                + row["critical_assemblies"] * 1.0
            )
            suppliers.append(
                SupplierRiskEntry(
                    supplier_id=row["supplier_id"],
                    supplier_name=row["supplier_name"],
                    region=row["region"],
                    tier=row["tier"],
                    critical_parts=row["critical_parts"],
                    critical_assemblies=row["critical_assemblies"],
                    sole_source_count=row["sole_source_count"],
                    risk_score=round(risk_score, 2),
                )
            )

        return SupplierRiskResponse(suppliers=suppliers)

    def get_spof(self) -> SpofResponse:
        rows = self._run(
            """
            MATCH (s:Supplier)<-[sb:SUPPLIED_BY {sole_source: true}]-(c:Connector)
                  <-[up:USES_PART {critical: true}]-(a:Assembly)
            OPTIONAL MATCH (v:Vehicle)-[:USES]->(topAsm:Assembly)
            WHERE topAsm = a OR (topAsm)-[:CONTAINS*]->(a)
            RETURN c.part_number AS part_number,
                   c.name AS connector_name,
                   s.id AS supplier_id,
                   s.name AS supplier_name,
                   collect(DISTINCT a.name) AS assemblies,
                   collect(DISTINCT v.name) AS vehicles
            """
        )

        entries = [
            SpofEntry(
                part_number=row["part_number"],
                connector_name=row["connector_name"],
                supplier_id=row["supplier_id"],
                supplier_name=row["supplier_name"],
                affected_vehicles=row["vehicles"] or [],
                affected_assemblies=row["assemblies"] or [],
            )
            for row in rows
        ]
        return SpofResponse(entries=entries)

    def get_supplier_connectors(self, supplier_id: str) -> SupplierConnectorsResponse:
        rows = self._run(
            """
            MATCH (s:Supplier {id: $supplier_id})<-[sb:SUPPLIED_BY]-(c:Connector)
            OPTIONAL MATCH (c)<-[up:USES_PART]-(a:Assembly)
            WHERE up.critical = true
            RETURN s.name AS supplier_name,
                   c.part_number AS part_number,
                   c.name AS name,
                   sb.share_pct AS share_pct,
                   sb.sole_source AS sole_source,
                   collect(DISTINCT a.name) AS critical_assemblies
            ORDER BY c.part_number
            """,
            {"supplier_id": supplier_id},
        )

        if not rows:
            name_row = self._run(
                "MATCH (s:Supplier {id: $id}) RETURN s.name AS name",
                {"id": supplier_id},
            )
            if not name_row:
                raise ValueError(f"Supplier '{supplier_id}' not found")
            return SupplierConnectorsResponse(
                supplier_id=supplier_id,
                supplier_name=name_row[0]["name"],
                connectors=[],
            )

        connectors = [
            SupplierConnectorEntry(
                part_number=row["part_number"],
                name=row["name"],
                share_pct=row["share_pct"] or 100.0,
                sole_source=bool(row["sole_source"]),
                critical_assemblies=[a for a in (row["critical_assemblies"] or []) if a],
            )
            for row in rows
        ]

        return SupplierConnectorsResponse(
            supplier_id=supplier_id,
            supplier_name=rows[0]["supplier_name"],
            connectors=connectors,
        )

    def get_graph_stats(self) -> Dict[str, int]:
        rows = self._run(
            """
            CALL () {
                MATCH (c:Connector) RETURN count(c) AS connectors
            }
            CALL () {
                MATCH (a:Assembly) RETURN count(a) AS assemblies
            }
            CALL () {
                MATCH (v:Vehicle) RETURN count(v) AS vehicles
            }
            CALL () {
                MATCH (s:Supplier) RETURN count(s) AS suppliers
            }
            RETURN connectors, assemblies, vehicles, suppliers
            """
        )
        if rows:
            return {k: int(v) for k, v in rows[0].items()}
        return {}
