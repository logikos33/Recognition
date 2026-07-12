"""
Tests: fueling_mock_service — generate_dashboard, generate_bays, get_bay.

Pure deterministic logic: no DB, no network.
random.Random is seeded by date/slot — we patch the seed functions to get
stable, predictable output.
"""
from unittest.mock import patch

from app.domain.services.fueling_mock_service import (
    _BAY_NAMES,
    _BAY_STATUSES,
    generate_bays,
    generate_dashboard,
    get_bay,
)


# ---------------------------------------------------------------------------
# generate_dashboard
# ---------------------------------------------------------------------------

class TestGenerateDashboard:

    def test_returns_expected_top_level_keys(self):
        result = generate_dashboard()
        for key in ("kpis", "top_baias_produtivas", "top_baias_perda",
                    "series_operacoes_diarias", "series_tempo_por_baia",
                    "pizza_causas_perda"):
            assert key in result

    def test_kpis_has_expected_keys(self):
        kpis = generate_dashboard()["kpis"]
        for key in ("total_carregado", "tempo_medio_minutos",
                    "total_itens_movimentados", "itens_nao_conformes",
                    "taxa_nao_conformidade", "eventos_nao_conformidade",
                    "taxa_ocupacao_percent"):
            assert key in kpis

    def test_today_period(self):
        result = generate_dashboard("today")
        assert result["kpis"]["total_carregado"] > 0

    def test_week_multiplier_greater_than_today(self):
        with patch("app.domain.services.fueling_mock_service._day_seed", return_value=42):
            today = generate_dashboard("today")["kpis"]["total_carregado"]
            week = generate_dashboard("week")["kpis"]["total_carregado"]
        assert week > today

    def test_month_multiplier_greater_than_week(self):
        with patch("app.domain.services.fueling_mock_service._day_seed", return_value=42):
            week = generate_dashboard("week")["kpis"]["total_carregado"]
            month = generate_dashboard("month")["kpis"]["total_carregado"]
        assert month > week

    def test_top_baias_produtivas_has_3_items(self):
        assert len(generate_dashboard()["top_baias_produtivas"]) == 3

    def test_top_baias_perda_has_3_items(self):
        assert len(generate_dashboard()["top_baias_perda"]) == 3

    def test_top_baias_produtivas_sorted_descending(self):
        top = generate_dashboard()["top_baias_produtivas"]
        itens = [b["itens"] for b in top]
        assert itens == sorted(itens, reverse=True)

    def test_series_operacoes_length_matches_today(self):
        result = generate_dashboard("today")
        assert len(result["series_operacoes_diarias"]) == 1

    def test_series_operacoes_length_matches_week(self):
        result = generate_dashboard("week")
        assert len(result["series_operacoes_diarias"]) == 7

    def test_series_operacoes_length_matches_month(self):
        result = generate_dashboard("month")
        assert len(result["series_operacoes_diarias"]) == 30

    def test_series_tempo_por_baia_has_6_items(self):
        assert len(generate_dashboard()["series_tempo_por_baia"]) == 6

    def test_pizza_causas_perda_is_list(self):
        result = generate_dashboard()["pizza_causas_perda"]
        assert isinstance(result, list)
        assert len(result) > 0

    def test_taxa_nc_is_percentage_between_0_and_100(self):
        kpis = generate_dashboard()["kpis"]
        assert 0 <= kpis["taxa_nao_conformidade"] <= 100

    def test_unknown_period_defaults_to_multiplier_1(self):
        with patch("app.domain.services.fueling_mock_service._day_seed", return_value=7):
            r_unknown = generate_dashboard("unknown")
            r_today = generate_dashboard("today")
        assert r_unknown["kpis"]["total_carregado"] == r_today["kpis"]["total_carregado"]

    def test_deterministic_with_same_seed(self):
        with patch("app.domain.services.fueling_mock_service._day_seed", return_value=99):
            r1 = generate_dashboard()
            r2 = generate_dashboard()
        assert r1["kpis"] == r2["kpis"]


# ---------------------------------------------------------------------------
# generate_bays
# ---------------------------------------------------------------------------

class TestGenerateBays:

    def test_returns_6_bays(self):
        assert len(generate_bays()) == 6

    def test_each_bay_has_required_keys(self):
        for bay in generate_bays():
            for key in ("id", "nome", "status", "operador", "placa",
                        "total_itens", "progresso"):
                assert key in bay

    def test_bay_ids_are_1_to_6(self):
        ids = [b["id"] for b in generate_bays()]
        assert ids == list(range(1, 7))

    def test_bay_names_are_from_constant(self):
        names = [b["nome"] for b in generate_bays()]
        assert all(n in _BAY_NAMES for n in names)

    def test_status_is_valid(self):
        for bay in generate_bays():
            assert bay["status"] in _BAY_STATUSES

    def test_active_bay_has_operator_and_plate(self):
        with patch("app.domain.services.fueling_mock_service._slot_seed", return_value=1):
            bays = generate_bays()
        for bay in bays:
            if bay["status"] == "active":
                assert bay["operador"] is not None
                assert bay["placa"] is not None

    def test_inactive_bay_has_none_operator(self):
        with patch("app.domain.services.fueling_mock_service._slot_seed", return_value=1):
            bays = generate_bays()
        for bay in bays:
            if bay["status"] != "active":
                assert bay["operador"] is None
                assert bay["placa"] is None
                assert bay["total_itens"] == 0
                assert bay["progresso"] == 0

    def test_deterministic_with_same_seeds(self):
        with patch("app.domain.services.fueling_mock_service._slot_seed", return_value=5), \
             patch("app.domain.services.fueling_mock_service._day_seed", return_value=5):
            b1 = generate_bays()
            b2 = generate_bays()
        assert b1 == b2


# ---------------------------------------------------------------------------
# get_bay
# ---------------------------------------------------------------------------

class TestGetBay:

    def test_valid_id_returns_bay(self):
        bay = get_bay(1)
        assert bay is not None
        assert bay["id"] == 1

    def test_valid_id_6_returns_bay(self):
        bay = get_bay(6)
        assert bay is not None
        assert bay["id"] == 6

    def test_id_0_returns_none(self):
        assert get_bay(0) is None

    def test_id_7_returns_none(self):
        assert get_bay(7) is None

    def test_returned_bay_has_nome(self):
        bay = get_bay(3)
        assert bay is not None
        assert "nome" in bay
