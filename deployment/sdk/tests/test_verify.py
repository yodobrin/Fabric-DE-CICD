"""Tests for verify.py — table name extraction and verification logic."""

import pytest
from unittest.mock import MagicMock, patch

from verify import (
    _extract_table_from_query,
    _check_shortcuts,
    VerificationResult,
    run_verifications,
    display_verifications,
)
from config import VerificationDef, WorkspaceConfig
from state import WorkspaceState


class TestExtractTableFromQuery:
    """Test SQL query parsing for table name extraction."""

    def test_simple_from_dbo(self):
        assert _extract_table_from_query("SELECT COUNT(*) FROM dbo.t2", "dbo") == "t2"

    def test_from_without_schema(self):
        assert _extract_table_from_query("SELECT * FROM t1", "dbo") == "t1"

    def test_case_insensitive(self):
        assert _extract_table_from_query("select count(*) from DBO.t5", "dbo") == "t5"

    def test_with_where_clause(self):
        q = "SELECT COUNT(*) as cnt FROM dbo.t1 WHERE AGE > 30"
        assert _extract_table_from_query(q, "dbo") == "t1"

    def test_multiline_query(self):
        q = """SELECT
            COUNT(*)
        FROM
            dbo.t3_dev
        WHERE 1=1"""
        assert _extract_table_from_query(q, "dbo") == "t3_dev"

    def test_no_from_returns_empty(self):
        assert _extract_table_from_query("INSERT INTO dbo.t2 VALUES (1)", "dbo") == ""

    def test_different_schema(self):
        assert _extract_table_from_query("SELECT * FROM public.users", "public") == "users"

    def test_shortcut_check_not_parsed_as_table(self):
        # SHORTCUT_CHECK queries are handled separately, but if accidentally passed here
        assert _extract_table_from_query("SHORTCUT_CHECK: t3", "dbo") == ""


class TestCheckShortcuts:
    """Test shortcut existence verification."""

    def test_all_shortcuts_found(self):
        client = MagicMock()
        client.list_shortcuts.return_value = [
            {"name": "t3"},
            {"name": "other"},
        ]
        vdef = VerificationDef(
            key="check_sc", description="Shortcuts exist",
            lakehouse="lh", query="SHORTCUT_CHECK: t3", expect={},
        )
        result = _check_shortcuts(client, "ws-id", "lh-id", vdef)
        assert result.passed is True
        assert "t3" in result.message

    def test_missing_shortcut(self):
        client = MagicMock()
        client.list_shortcuts.return_value = [{"name": "other"}]
        vdef = VerificationDef(
            key="check_sc", description="Shortcuts exist",
            lakehouse="lh", query="SHORTCUT_CHECK: t3", expect={},
        )
        result = _check_shortcuts(client, "ws-id", "lh-id", vdef)
        assert result.passed is False
        assert "Missing" in result.message

    def test_multiple_shortcuts_check(self):
        client = MagicMock()
        client.list_shortcuts.return_value = [
            {"name": "t3"},
            {"name": "t4"},
        ]
        vdef = VerificationDef(
            key="check_sc", description="Shortcuts",
            lakehouse="lh", query="SHORTCUT_CHECK: t3, t4", expect={},
        )
        result = _check_shortcuts(client, "ws-id", "lh-id", vdef)
        assert result.passed is True

    def test_api_error(self):
        from fabric_client import FabricError
        client = MagicMock()
        client.list_shortcuts.side_effect = FabricError(401, "Unauthorized", "Token expired")
        vdef = VerificationDef(
            key="check_sc", description="Shortcuts",
            lakehouse="lh", query="SHORTCUT_CHECK: t3", expect={},
        )
        result = _check_shortcuts(client, "ws-id", "lh-id", vdef)
        assert result.passed is False
        assert "Could not list shortcuts" in result.message


class TestRunVerifications:
    """Test the run_verifications() orchestration."""

    def test_filters_by_keys(self):
        cfg = WorkspaceConfig()
        cfg.verifications = {
            "v1": VerificationDef(key="v1", description="Check 1", lakehouse="lh", query="SELECT 1 FROM dbo.t1"),
            "v2": VerificationDef(key="v2", description="Check 2", lakehouse="lh", query="SELECT 1 FROM dbo.t2"),
        }
        state = WorkspaceState()
        state.item_ids = {}

        client = MagicMock()
        results = run_verifications(client, "ws-id", cfg, state, keys=["v1"])
        # Only v1 should be checked (will fail since lakehouse not found, but only 1 result)
        assert len(results) == 1
        assert results[0].key == "v1"

    def test_lakehouse_not_found(self):
        cfg = WorkspaceConfig()
        cfg.verifications = {
            "v1": VerificationDef(key="v1", description="X", lakehouse="lh_missing",
                                   query="SELECT 1 FROM dbo.t1"),
        }
        state = WorkspaceState()
        state.item_ids = {}

        client = MagicMock()
        results = run_verifications(client, "ws-id", cfg, state)
        assert len(results) == 1
        assert results[0].passed is False
        assert "not found" in results[0].message


class TestVerificationResult:
    """Test VerificationResult data class."""

    def test_to_dict_basic(self):
        r = VerificationResult(key="v1", description="Check", passed=True, message="OK")
        d = r.to_dict()
        assert d["key"] == "v1"
        assert d["passed"] is True
        assert "details" not in d

    def test_to_dict_with_details(self):
        r = VerificationResult(key="v1", description="Check", passed=True, message="OK",
                                details={"table": "t1", "parquet_files": 5})
        d = r.to_dict()
        assert d["details"]["parquet_files"] == 5


class TestDisplayVerifications:
    """Test display doesn't crash."""

    def test_table_output(self, capsys):
        results = [
            VerificationResult("v1", "Check t1", True, "OK — 5 files"),
            VerificationResult("v2", "Check t2", False, "Table not found"),
        ]
        display_verifications(results, output_format="table")
        out = capsys.readouterr().out
        assert "PASS" in out
        assert "FAIL" in out
        assert "1/2" in out

    def test_json_output(self, capsys):
        results = [VerificationResult("v1", "X", True, "OK")]
        display_verifications(results, output_format="json")
        out = capsys.readouterr().out
        assert '"passed": true' in out
