"""
Tests: active_learning.prioritize_frames — a query não pode referenciar a
coluna inexistente status='pre_annotated' (bug conhecido). O predicado real
é pre_annotations IS NOT NULL: o pre_annotator preenche pre_annotations +
pre_annotated_at (migration 011); training_frames não tem coluna status.
"""
from unittest.mock import MagicMock, patch

import src.services.active_learning as active_learning


def _run(frames):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = frames
    with patch.object(active_learning, "_get_conn", return_value=conn):
        result = active_learning.prioritize_frames("tenant-1", "epi")
    return result, cur


class TestPrioritizeFramesQuery:
    def test_query_does_not_reference_pre_annotated_status(self):
        _, cur = _run([])
        sql = cur.execute.call_args_list[0].args[0]
        assert "pre_annotated'" not in sql
        assert "status" not in sql

    def test_query_uses_pre_annotations_is_not_null(self):
        _, cur = _run([])
        sql = cur.execute.call_args_list[0].args[0]
        assert "pre_annotations IS NOT NULL" in sql

    def test_query_keeps_tenant_and_module_filters(self):
        _, cur = _run([])
        sql = cur.execute.call_args_list[0].args[0]
        assert "tenant_id = %s" in sql
        assert "module_code = %s" in sql


class TestPrioritizeFramesRanking:
    def test_empty_result_short_circuits(self):
        result, _ = _run([])
        assert result == {"prioritized": 0}

    def test_most_uncertain_frame_ranked_first(self):
        frames = [
            {
                "id": "f1",
                "pre_annotations": [
                    {"confidence": 0.90},
                    {"confidence": 0.95},
                    {"confidence": 0.90},
                ],
            },
            {"id": "f2", "pre_annotations": []},
        ]
        result, _ = _run(frames)
        assert result["prioritized"] == 2
        # f2 sem detecções → incerteza máxima (1.0) → rank 0
        assert result["top_5"][0]["frame_id"] == "f2"
