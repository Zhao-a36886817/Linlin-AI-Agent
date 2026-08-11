import json
from pathlib import Path

import pytest

from scripts.supply_chain import (
    SupplyChainError,
    canonical_json,
    generate_provenance,
    generate_sbom,
    scan_secrets,
)

ROOT = Path(__file__).parents[1]


def test_sbom_is_deterministic_and_contains_all_ecosystems() -> None:
    first = generate_sbom(ROOT)
    second = generate_sbom(ROOT)
    assert canonical_json(first) == canonical_json(second)
    purls = [item["purl"] for item in first["components"]]
    assert any(item.startswith("pkg:pypi/") for item in purls)
    assert any(item.startswith("pkg:npm/") for item in purls)
    assert any(item.startswith("pkg:cargo/") for item in purls)


def test_provenance_binds_reviewed_source_and_artifact_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "linlin.zip"
    artifact.write_bytes(b"release")
    document = generate_provenance(
        [artifact],
        source_commit="a" * 40,
        builder="https://github.com/example/linlin/actions/runs/1",
        workflow_ref="example/linlin/.github/workflows/release.yml@refs/tags/v1.0.0",
    )
    assert document["predicate"]["buildDefinition"]["externalParameters"]["sourceCommit"] == "a" * 40
    assert len(document["subject"][0]["digest"]["sha256"]) == 64
    json.loads(canonical_json(document))


def test_provenance_rejects_unreviewed_or_missing_subject(tmp_path: Path) -> None:
    with pytest.raises(SupplyChainError):
        generate_provenance([], source_commit="short", builder="test", workflow_ref="test")
    with pytest.raises(SupplyChainError):
        generate_provenance(
            [tmp_path / "missing"], source_commit="a" * 40, builder="test", workflow_ref="test"
        )


def test_secret_scan_detects_high_confidence_secret_without_echoing_value(tmp_path: Path) -> None:
    secret = "ghp_" + "A" * 36
    candidate = tmp_path / "settings.txt"
    candidate.write_text(f"credential={secret}\n", encoding="utf-8")
    findings = scan_secrets(tmp_path, [candidate])
    assert findings == ["settings.txt:1:github-token"]
    assert secret not in findings[0]


def test_repository_secret_scan_is_clean() -> None:
    assert scan_secrets(ROOT) == []


def test_compromise_drill_detects_changed_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "release.bin"
    artifact.write_bytes(b"approved")
    provenance = generate_provenance(
        [artifact], source_commit="b" * 40, builder="local-drill", workflow_ref="manual"
    )
    approved_digest = provenance["subject"][0]["digest"]["sha256"]
    artifact.write_bytes(b"compromised")
    regenerated = generate_provenance(
        [artifact], source_commit="b" * 40, builder="local-drill", workflow_ref="manual"
    )
    assert regenerated["subject"][0]["digest"]["sha256"] != approved_digest
