#!/usr/bin/env python3
"""
Pre-flight checks for live demo / YouTube recording.

Run from backend/:
  python scripts/preflight_demo.py
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Load backend/.env
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API = "http://localhost:8000"
HERO_PART = "EC-2024-3441"
HERO_QUERY = (
    "11-pin wire-to-board connector for battery management and infotainment, "
    "24V, IP67, automotive ECU"
)


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{API}{path}", timeout=60) as resp:
        return json.loads(resp.read().decode())


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def main() -> int:
    print("\n=== Automotive Part Matcher — Demo Pre-flight ===\n")
    errors = 0

    # 1. Backend health
    print("1. Backend API")
    try:
        health = get("/health")
        ok(f"Backend reachable — status {health.get('status')}")
        qdrant = health.get("qdrant", "unknown")
        neo4j = health.get("neo4j", "unknown")
        if qdrant == "connected":
            ok("Qdrant connected")
        else:
            fail(f"Qdrant: {qdrant}")
            errors += 1
        if neo4j == "connected":
            ok("Neo4j connected")
        else:
            fail(f"Neo4j: {neo4j} — graph features will not work until fixed")
            errors += 1
    except Exception as e:
        fail(f"Cannot reach {API}/health — start backend: uvicorn app.main:app --port 8000")
        print(f"     ({e})")
        return 1

    # 2. Neo4j direct (if configured)
    print("\n2. Neo4j graph data")
    if health.get("neo4j") == "connected":
        try:
            impact = get(f"/api/graph/impact/{HERO_PART}")
            v = len(impact.get("affected_vehicles", []))
            a = len(impact.get("affected_assemblies", []))
            if v > 0 and a > 0:
                ok(f"Hero part {HERO_PART}: {v} vehicles, {a} assemblies")
            else:
                fail(f"No graph data for {HERO_PART} — run: python ingest_graph.py")
                errors += 1
        except urllib.error.HTTPError as e:
            fail(f"Impact API failed ({e.code}) — run: python ingest_graph.py")
            errors += 1
    else:
        print("  → Skip (Neo4j disconnected). Fix Aura URI in backend/.env, then:")
        print("      python ingest_graph.py")

    # 3. Search
    print("\n3. Vector search (hero query)")
    try:
        import urllib.parse

        body = urllib.parse.urlencode(
            {"text_input": HERO_QUERY, "top_k": 3, "enable_acorn": "true"}
        ).encode()
        req = urllib.request.Request(
            f"{API}/api/search",
            data=body,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            search = json.loads(resp.read().decode())
        matches = search.get("matches") or search.get("results") or []
        if matches and matches[0].get("part_number") == HERO_PART:
            ok(f"Top match is {HERO_PART} (score {matches[0].get('match_score', 0):.1f})")
        elif matches:
            fail(f"Top match is {matches[0].get('part_number')} — expected {HERO_PART}")
            errors += 1
        else:
            fail("No search results — run: python ingest_data.py")
            errors += 1
    except Exception as e:
        fail(f"Search failed: {e}")
        errors += 1

    # 4. Disruption workflow
    print("\n4. Disruption mitigation workflow")
    try:
        disruption = post(
            "/api/disruption/analyze",
            {"part_number": HERO_PART, "max_alternatives": 5, "min_similarity": 55},
        )
        alts = disruption.get("alternatives", [])
        ok(f"Workflow completed in {disruption.get('processing_time_ms', 0):.0f}ms")
        ok(f"Summary: {disruption.get('summary', '')[:100]}...")
        if alts:
            top = alts[0]
            ok(f"Top alternative: {top['part_number']} ({top['verdict']})")
        else:
            fail("No alternatives returned")
            errors += 1
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        fail(f"Disruption API failed ({e.code}): {body[:200]}")
        errors += 1
    except Exception as e:
        fail(f"Disruption failed: {e}")
        errors += 1

    # 5. Frontend
    print("\n5. Frontend")
    try:
        with urllib.request.urlopen("http://localhost:3000", timeout=5) as resp:
            if resp.status == 200:
                ok("Frontend at http://localhost:3000")
            else:
                fail(f"Frontend returned {resp.status}")
                errors += 1
    except Exception:
        fail("Frontend not running — run: cd frontend && npm run dev")
        errors += 1

    print("\n=== Demo URLs ===")
    print("  Search:      http://localhost:3000/")
    print("  Disruption:  http://localhost:3000/disruption")
    print("  Supplier:    http://localhost:3000/graph")
    print("  Workflow:    http://localhost:3000/workflow")
    print(f"\n  Hero part:   {HERO_PART}")
    print(f"  Hero query:  {HERO_QUERY}")

    if errors:
        print(f"\n⚠  {errors} check(s) failed — fix before recording.\n")
        return 1
    print("\n✓ All checks passed — ready to record.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
