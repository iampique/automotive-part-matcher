#!/usr/bin/env python3
"""
Generate deterministic graph seed data from connector_catalog.json.

Creates vehicles, assemblies, BOM lines, suppliers, sourcing, and
compliance requirements that extend the flat connector catalog with
graph relationships for impact analysis and supplier topology demos.
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Application tag -> assembly mapping
APPLICATION_ASSEMBLIES = {
    "Battery Management": {"id": "asm-bms", "name": "Battery Management System", "criticality": "high"},
    "ADAS": {"id": "asm-adas", "name": "ADAS Sensor Module", "criticality": "high"},
    "Infotainment": {"id": "asm-infotainment", "name": "Infotainment Head Unit", "criticality": "medium"},
    "Powertrain": {"id": "asm-powertrain", "name": "Powertrain Control Module", "criticality": "high"},
    "Charging": {"id": "asm-charging", "name": "Onboard Charger Assembly", "criticality": "high"},
    "Lighting": {"id": "asm-lighting", "name": "LED Lighting Module", "criticality": "low"},
    "Sensors": {"id": "asm-sensors", "name": "Sensor Fusion ECU", "criticality": "medium"},
}

PLATFORM_ASSEMBLY = {
    "id": "asm-platform-ev",
    "name": "EV Platform Electronics",
    "parent_id": None,
    "criticality": "high",
    "requirement_ids": ["req-iso26262-asil-d", "req-iatf16949"],
}

BRAKE_ASSEMBLY = {
    "id": "asm-brake-ecm",
    "name": "Brake Electronic Control Module",
    "parent_id": "asm-platform-ev",
    "criticality": "critical",
    "requirement_ids": ["req-iso26262-asil-d", "req-dual-source"],
}

VEHICLES = [
    {"id": "veh-ev-sedan-2025", "name": "Aurora EV Sedan", "platform": "EV-Sedan", "model_year": 2025},
    {"id": "veh-ev-suv-2026", "name": "Summit EV SUV", "platform": "EV-SUV", "model_year": 2026},
    {"id": "veh-commercial-van-2025", "name": "CargoFlex Commercial Van", "platform": "EV-Van", "model_year": 2025},
    {"id": "veh-performance-ev-2026", "name": "Velocity Performance EV", "platform": "EV-Performance", "model_year": 2026},
]

SUPPLIERS = [
    {"id": "sup-aptiv", "name": "Aptiv PLC", "region": "North America", "tier": 1},
    {"id": "sup-te", "name": "TE Connectivity", "region": "North America", "tier": 1},
    {"id": "sup-molex", "name": "Molex LLC", "region": "Asia-Pacific", "tier": 1},
    {"id": "sup-amphenol", "name": "Amphenol Corporation", "region": "Europe", "tier": 1},
    {"id": "sup-yazaki", "name": "Yazaki Corporation", "region": "Asia-Pacific", "tier": 1},
    {"id": "sup-sumitomo", "name": "Sumitomo Electric", "region": "Asia-Pacific", "tier": 2},
    {"id": "sup-leoni", "name": "Leoni AG", "region": "Europe", "tier": 2},
    {"id": "sup-furukawa", "name": "Furukawa Electric", "region": "Asia-Pacific", "tier": 2},
    {"id": "sup-jst", "name": "JST Corporation", "region": "Asia-Pacific", "tier": 2},
    {"id": "sup-hirose", "name": "Hirose Electric", "region": "Asia-Pacific", "tier": 2},
]

REQUIREMENTS = [
    {"id": "req-iso26262-asil-d", "name": "ISO 26262 ASIL-D", "standard": "ISO 26262", "severity": "critical"},
    {"id": "req-rohs", "name": "RoHS Compliance", "standard": "RoHS 3", "severity": "medium"},
    {"id": "req-reach", "name": "REACH Compliance", "standard": "REACH", "severity": "medium"},
    {"id": "req-dual-source", "name": "Dual-Source Supplier", "standard": "Internal", "severity": "high"},
    {"id": "req-iatf16949", "name": "IATF 16949 Quality", "standard": "IATF 16949", "severity": "high"},
    {"id": "req-iso9001", "name": "ISO 9001 Quality", "standard": "ISO 9001", "severity": "medium"},
    {"id": "req-aec-q200", "name": "AEC-Q200 Passive Components", "standard": "AEC-Q200", "severity": "high"},
    {"id": "req-ul", "name": "UL Recognition", "standard": "UL", "severity": "medium"},
]

REQUIREMENT_HIERARCHY = [
    {"child_id": "req-rohs", "parent_id": "req-iatf16949"},
    {"child_id": "req-reach", "parent_id": "req-iatf16949"},
    {"child_id": "req-aec-q200", "parent_id": "req-iatf16949"},
]


def _hash_index(part_number: str, modulo: int) -> int:
    return int(hashlib.md5(part_number.encode()).hexdigest()[:8], 16) % modulo


def generate_seed(catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    assemblies: Dict[str, Dict[str, Any]] = {}

    # Platform and brake assemblies
    assemblies[PLATFORM_ASSEMBLY["id"]] = {**PLATFORM_ASSEMBLY, "requirement_ids": list(PLATFORM_ASSEMBLY["requirement_ids"])}
    assemblies[BRAKE_ASSEMBLY["id"]] = {**BRAKE_ASSEMBLY, "requirement_ids": list(BRAKE_ASSEMBLY["requirement_ids"])}

    for app, asm_def in APPLICATION_ASSEMBLIES.items():
        asm_id = asm_def["id"]
        assemblies[asm_id] = {
            "id": asm_id,
            "name": asm_def["name"],
            "parent_id": PLATFORM_ASSEMBLY["id"],
            "criticality": asm_def["criticality"],
            "requirement_ids": ["req-rohs", "req-reach"],
        }
        if asm_def["criticality"] in ("high", "critical"):
            assemblies[asm_id]["requirement_ids"].append("req-aec-q200")

    bom_lines: List[Dict[str, Any]] = []
    sourcing: List[Dict[str, Any]] = []
    seen_bom: set = set()

    for conn in catalog:
        pn = conn["part_number"]
        apps = conn.get("applications", [])

        # Map connector to assemblies via applications
        target_assemblies = set()
        for app in apps:
            if app in APPLICATION_ASSEMBLIES:
                target_assemblies.add(APPLICATION_ASSEMBLIES[app]["id"])

        if not target_assemblies:
            # Default assignment based on hash
            default_asm = list(APPLICATION_ASSEMBLIES.values())[_hash_index(pn, len(APPLICATION_ASSEMBLIES))]
            target_assemblies.add(default_asm["id"])

        for asm_id in target_assemblies:
            key = (asm_id, pn)
            if key not in seen_bom:
                seen_bom.add(key)
                critical = assemblies[asm_id]["criticality"] in ("high", "critical")
                bom_lines.append({
                    "assembly_id": asm_id,
                    "part_number": pn,
                    "qty": 1 + _hash_index(pn + asm_id, 3),
                    "critical": critical,
                })

        # Supplier assignment (deterministic)
        supplier = SUPPLIERS[_hash_index(pn, len(SUPPLIERS))]
        sole_source = _hash_index(pn, 100) < 15 and any(
            assemblies.get(a, {}).get("criticality") in ("high", "critical")
            for a in target_assemblies
        )
        sourcing.append({
            "part_number": pn,
            "supplier_id": supplier["id"],
            "share_pct": 100.0 if sole_source else 70.0 + _hash_index(pn, 30),
            "sole_source": sole_source,
        })

    # Vehicle -> assembly links
    asm_ids = [a["id"] for a in assemblies.values() if a["id"] != PLATFORM_ASSEMBLY["id"]]
    vehicle_assemblies: List[Dict[str, str]] = []
    for i, veh in enumerate(VEHICLES):
        # Each vehicle uses platform + subset of subsystems
        vehicle_assemblies.append({"vehicle_id": veh["id"], "assembly_id": PLATFORM_ASSEMBLY["id"]})
        vehicle_assemblies.append({"vehicle_id": veh["id"], "assembly_id": BRAKE_ASSEMBLY["id"]})
        start = (i * 2) % len(asm_ids)
        for asm_id in asm_ids[start : start + 5]:
            vehicle_assemblies.append({"vehicle_id": veh["id"], "assembly_id": asm_id})

    assembly_list = [
        {
            "id": a["id"],
            "name": a["name"],
            "parent_id": a.get("parent_id"),
            "criticality": a["criticality"],
            "requirement_ids": a.get("requirement_ids", []),
        }
        for a in assemblies.values()
    ]

    return {
        "vehicles": VEHICLES,
        "assemblies": assembly_list,
        "bom_lines": bom_lines,
        "suppliers": SUPPLIERS,
        "sourcing": sourcing,
        "requirements": REQUIREMENTS,
        "requirement_hierarchy": REQUIREMENT_HIERARCHY,
        "vehicle_assemblies": vehicle_assemblies,
    }


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    catalog_path = script_dir.parent.parent / "data" / "raw" / "connector_catalog.json"
    output_path = script_dir.parent.parent / "data" / "raw" / "graph_seed.json"

    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)

    seed = generate_seed(catalog)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2)

    print(f"Generated graph seed: {output_path}")
    print(f"  Vehicles: {len(seed['vehicles'])}")
    print(f"  Assemblies: {len(seed['assemblies'])}")
    print(f"  BOM lines: {len(seed['bom_lines'])}")
    print(f"  Suppliers: {len(seed['suppliers'])}")
    print(f"  Sourcing entries: {len(seed['sourcing'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
