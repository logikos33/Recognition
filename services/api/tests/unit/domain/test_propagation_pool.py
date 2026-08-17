"""
Tests: domain/services/propagation_pool.py — guard fail-closed do pool de
propagação semeada (a trava contra vazamento de imagem de operação pra uma
GPU de terceiro).

Cobre:
- compute_pool_hash: determinístico, independente da ordem de entrada.
- validate_pool_frames: pool vazio, tenant errado, câmera fora do
  critério, data fora do intervalo, r2_key ausente — cada violação
  individual levanta PoolGuardError com motivo legível.
- materialize_pool: valida + ordena + trunca (validation_only).
- revalidate_pool (dispatch): frame sumiu/apareceu, frame passou a violar
  o critério, pool_hash divergente — falha-antes/passa-depois: sem o
  guard, qualquer uma dessas mudanças passaria batido pro executor.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.domain.services.propagation_pool import (
    PoolGuardError,
    compute_pool_hash,
    materialize_pool,
    revalidate_pool,
    validate_pool_frames,
)

_TENANT = "99999999-8888-7777-6666-555555555555"
_CAMERA = "11111111-2222-3333-4444-555555555555"
_OTHER_CAMERA = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_OTHER_TENANT = "00000000-0000-0000-0000-000000000000"


def _frame(
    frame_id: str,
    *,
    tenant_id: str = _TENANT,
    camera_id: str = _CAMERA,
    captured_at: datetime | date = datetime(2026, 7, 31, 12, 0, 0),
    r2_key: "str | None" = "frames/x/y.jpg",
) -> dict:
    return {
        "id": frame_id,
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "captured_at": captured_at,
        "r2_key": r2_key,
    }


class TestComputePoolHash:
    def test_deterministic_regardless_of_input_order(self) -> None:
        h1 = compute_pool_hash(["b", "a", "c"])
        h2 = compute_pool_hash(["c", "b", "a"])
        assert h1 == h2

    def test_different_lists_yield_different_hashes(self) -> None:
        assert compute_pool_hash(["a", "b"]) != compute_pool_hash(["a", "b", "c"])

    def test_empty_list_is_stable(self) -> None:
        assert compute_pool_hash([]) == compute_pool_hash([])


class TestValidatePoolFrames:
    def _kwargs(self, **overrides) -> dict:
        base = {
            "tenant_id": _TENANT,
            "camera_ids": [_CAMERA],
            "date_from": date(2026, 7, 31),
            "date_to": date(2026, 7, 31),
        }
        base.update(overrides)
        return base

    def test_valid_pool_never_raises(self) -> None:
        frames = [_frame("f1"), _frame("f2")]
        validate_pool_frames(frames, **self._kwargs())  # não levanta

    def test_empty_pool_raises(self) -> None:
        with pytest.raises(PoolGuardError, match="pool vazio"):
            validate_pool_frames([], **self._kwargs())

    def test_frame_from_other_tenant_raises(self) -> None:
        frames = [_frame("f1"), _frame("f2", tenant_id=_OTHER_TENANT)]
        with pytest.raises(PoolGuardError, match="outro tenant"):
            validate_pool_frames(frames, **self._kwargs())

    def test_frame_with_camera_outside_criteria_raises(self) -> None:
        frames = [_frame("f1"), _frame("f2", camera_id=_OTHER_CAMERA)]
        with pytest.raises(PoolGuardError, match="fora do critério"):
            validate_pool_frames(frames, **self._kwargs())

    def test_frame_with_date_outside_range_raises(self) -> None:
        frames = [_frame("f1", captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        with pytest.raises(PoolGuardError, match="fora do intervalo"):
            validate_pool_frames(frames, **self._kwargs())

    def test_frame_without_captured_at_raises(self) -> None:
        frame = _frame("f1")
        frame["captured_at"] = None
        with pytest.raises(PoolGuardError, match="captured_at"):
            validate_pool_frames([frame], **self._kwargs())

    def test_frame_without_r2_key_raises(self) -> None:
        frames = [_frame("f1", r2_key=None)]
        with pytest.raises(PoolGuardError, match="r2_key"):
            validate_pool_frames(frames, **self._kwargs())

    def test_frame_with_empty_r2_key_raises(self) -> None:
        frames = [_frame("f1", r2_key="")]
        with pytest.raises(PoolGuardError, match="r2_key"):
            validate_pool_frames(frames, **self._kwargs())

    def test_date_boundaries_are_inclusive(self) -> None:
        frames = [
            _frame("f1", captured_at=date(2026, 7, 30)),
            _frame("f2", captured_at=date(2026, 8, 1)),
        ]
        validate_pool_frames(
            frames,
            tenant_id=_TENANT,
            camera_ids=[_CAMERA],
            date_from=date(2026, 7, 30),
            date_to=date(2026, 8, 1),
        )  # não levanta — bordas inclusivas

    def test_multiple_cameras_in_criteria(self) -> None:
        frames = [_frame("f1", camera_id=_CAMERA), _frame("f2", camera_id=_OTHER_CAMERA)]
        validate_pool_frames(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA, _OTHER_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
        )  # não levanta


class TestEnforceDateGuard:
    """`enforce_date_guard=False` (task "propagação no edge"): pula SÓ a
    checagem de captured_at — tenant/câmera/r2_key continuam validados
    sempre, nos dois destinos. Frames com data de OPERAÇÃO (não só
    encenação) viram semente/pool válidos quando a imagem nunca sai do
    site (provider onsite)."""

    def _kwargs(self, **overrides) -> dict:
        base = {
            "tenant_id": _TENANT,
            "camera_ids": [_CAMERA],
            "date_from": date(2026, 7, 31),
            "date_to": date(2026, 7, 31),
        }
        base.update(overrides)
        return base

    def test_default_still_enforces_date(self) -> None:
        """Sem passar o parâmetro, comportamento IDÊNTICO ao anterior —
        retrocompat com todo caller offsite existente."""
        frames = [_frame("f1", captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        with pytest.raises(PoolGuardError, match="fora do intervalo"):
            validate_pool_frames(frames, **self._kwargs())

    def test_enforce_false_allows_operation_date_outside_window(self) -> None:
        frames = [_frame("f1", captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        validate_pool_frames(
            frames, **self._kwargs(), enforce_date_guard=False,
        )  # não levanta

    def test_enforce_false_still_checks_tenant(self) -> None:
        frames = [_frame("f1", tenant_id=_OTHER_TENANT)]
        with pytest.raises(PoolGuardError, match="outro tenant"):
            validate_pool_frames(frames, **self._kwargs(), enforce_date_guard=False)

    def test_enforce_false_still_checks_camera(self) -> None:
        frames = [_frame("f1", camera_id=_OTHER_CAMERA)]
        with pytest.raises(PoolGuardError, match="fora do critério"):
            validate_pool_frames(frames, **self._kwargs(), enforce_date_guard=False)

    def test_enforce_false_still_checks_r2_key(self) -> None:
        frames = [_frame("f1", r2_key=None, captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        with pytest.raises(PoolGuardError, match="r2_key"):
            validate_pool_frames(frames, **self._kwargs(), enforce_date_guard=False)

    def test_enforce_false_allows_missing_captured_at(self) -> None:
        """Sem checagem de data, um frame sem captured_at também não
        derruba o pool (a checagem de captured_at é justamente o que
        `enforce_date_guard=False` desliga)."""
        frame = _frame("f1")
        frame["captured_at"] = None
        validate_pool_frames(
            [frame], **self._kwargs(), enforce_date_guard=False,
        )  # não levanta

    def test_materialize_pool_propagates_enforce_date_guard(self) -> None:
        frames = [_frame("f1", captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        frame_ids, _ = materialize_pool(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
            enforce_date_guard=False,
        )
        assert frame_ids == ["f1"]

    def test_revalidate_pool_propagates_enforce_date_guard(self) -> None:
        frames = [_frame("f1", captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        pool_hash = compute_pool_hash(["f1"])
        revalidate_pool(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
            expected_frame_ids=["f1"], expected_pool_hash=pool_hash,
            enforce_date_guard=False,
        )  # não levanta — sem enforce_date_guard=False levantaria "fora do intervalo"

    def test_revalidate_pool_default_still_enforces_date(self) -> None:
        frames = [_frame("f1", captured_at=datetime(2026, 8, 1, 0, 0, 0))]
        pool_hash = compute_pool_hash(["f1"])
        with pytest.raises(PoolGuardError, match="fora do intervalo"):
            revalidate_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
                expected_frame_ids=["f1"], expected_pool_hash=pool_hash,
            )


class TestMaterializePool:
    def test_returns_sorted_ids_and_hash(self) -> None:
        frames = [_frame("f2"), _frame("f1")]
        frame_ids, pool_hash = materialize_pool(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
        )
        assert frame_ids == ["f1", "f2"]
        assert pool_hash == compute_pool_hash(["f1", "f2"])

    def test_validation_only_truncates_deterministically(self) -> None:
        frames = [_frame(f"f{i}") for i in range(10)]
        frame_ids, pool_hash = materialize_pool(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31), limit=5,
        )
        assert len(frame_ids) == 5
        assert frame_ids == sorted(f"f{i}" for i in range(10))[:5]
        # hash é da lista JÁ truncada — é essa que o dispatch revalida depois
        assert pool_hash == compute_pool_hash(frame_ids)

    def test_invalid_frame_prevents_materialization(self) -> None:
        frames = [_frame("f1"), _frame("f2", camera_id=_OTHER_CAMERA)]
        with pytest.raises(PoolGuardError):
            materialize_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
            )


class TestRevalidatePoolAtDispatch:
    """Falha-antes/passa-depois: cada teste aqui simula um jeito do pool
    "mudar" entre a criação do job e o dispatch — sem revalidate_pool,
    nenhuma dessas mudanças seria detectada e o executor receberia um
    conjunto diferente do que foi aprovado na criação."""

    def _base_ids(self) -> list[str]:
        return ["f1", "f2", "f3"]

    def _base_hash(self) -> str:
        return compute_pool_hash(self._base_ids())

    def test_unchanged_pool_passes(self) -> None:
        frames = [_frame(fid) for fid in self._base_ids()]
        revalidate_pool(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
            expected_frame_ids=self._base_ids(), expected_pool_hash=self._base_hash(),
        )  # não levanta

    def test_frame_deleted_since_creation_raises(self) -> None:
        """f3 não veio mais no refetch (deletado) — sem o guard, o job
        rodaria silenciosamente com só 2 dos 3 frames aprovados."""
        frames = [_frame("f1"), _frame("f2")]
        with pytest.raises(PoolGuardError, match="mudou"):
            revalidate_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
                expected_frame_ids=self._base_ids(),
                expected_pool_hash=self._base_hash(),
            )

    def test_unexpected_extra_frame_raises(self) -> None:
        """f4 aparece no refetch mas nunca esteve na lista aprovada."""
        frames = [_frame(fid) for fid in [*self._base_ids(), "f4"]]
        with pytest.raises(PoolGuardError, match="mudou"):
            revalidate_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
                expected_frame_ids=self._base_ids(),
                expected_pool_hash=self._base_hash(),
            )

    def test_frame_reassigned_to_another_camera_since_creation_raises(self) -> None:
        """Mesmos 3 ids voltam (conjunto bate), mas f2 foi reatribuído a
        outra câmera depois da criação do job — revalidate_pool ainda pega,
        via validate_pool_frames."""
        frames = [
            _frame("f1"), _frame("f2", camera_id=_OTHER_CAMERA), _frame("f3"),
        ]
        with pytest.raises(PoolGuardError, match="fora do critério"):
            revalidate_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
                expected_frame_ids=self._base_ids(),
                expected_pool_hash=self._base_hash(),
            )

    def test_pool_hash_mismatch_raises_even_if_set_matches(self) -> None:
        """Checagem final redundante por desenho: se o hash esperado
        gravado no job (por algum bug) não bate com o recomputado, mesmo
        com o conjunto de ids idêntico, o dispatch aborta."""
        frames = [_frame(fid) for fid in self._base_ids()]
        with pytest.raises(PoolGuardError, match="pool_hash divergente"):
            revalidate_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
                expected_frame_ids=self._base_ids(),
                expected_pool_hash="0" * 64,
            )

    def test_never_partially_proceeds_on_violation(self) -> None:
        """A violação aborta o pool INTEIRO — não existe um retorno
        parcial "os 2 frames bons, sem o ofensor"."""
        frames = [_frame("f1"), _frame("f2", tenant_id=_OTHER_TENANT), _frame("f3")]
        with pytest.raises(PoolGuardError):
            revalidate_pool(
                frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
                date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
                expected_frame_ids=self._base_ids(),
                expected_pool_hash=self._base_hash(),
            )


class TestMaterializePoolMustInclude:
    """`must_include` pina as sementes no corte de validação — `limit`
    conta só os frames-ALVO além delas (regressão do e2e DEV: semente fora
    dos primeiros N ids ficava fora do pool de 5)."""

    def _frames(self, n: int) -> list[dict]:
        return [_frame(f"f{i}") for i in range(n)]

    def _materialize(self, frames, limit=None, must_include=None):
        return materialize_pool(
            frames, tenant_id=_TENANT, camera_ids=[_CAMERA],
            date_from=date(2026, 7, 31), date_to=date(2026, 7, 31),
            limit=limit, must_include=must_include,
        )

    def test_seed_beyond_limit_is_pinned(self) -> None:
        frames = self._frames(10)
        ids, pool_hash = self._materialize(frames, limit=5, must_include=["f9"])
        assert "f9" in ids
        assert len(ids) == 6  # 1 semente + 5 alvos
        assert pool_hash == compute_pool_hash(ids)

    def test_seed_inside_limit_still_counts_targets_separately(self) -> None:
        frames = self._frames(10)
        ids, _ = self._materialize(frames, limit=5, must_include=["f0"])
        assert "f0" in ids
        assert len(ids) == 6

    def test_must_include_outside_pool_is_ignored(self) -> None:
        frames = self._frames(6)
        ids, _ = self._materialize(frames, limit=5, must_include=["fora-do-pool"])
        assert "fora-do-pool" not in ids
        assert len(ids) == 5

    def test_no_must_include_keeps_old_truncation(self) -> None:
        frames = self._frames(10)
        ids, _ = self._materialize(frames, limit=5)
        assert ids == sorted(f"f{i}" for i in range(10))[:5]

    def test_no_limit_ignores_must_include(self) -> None:
        frames = self._frames(4)
        ids, _ = self._materialize(frames, must_include=["f2"])
        assert len(ids) == 4
