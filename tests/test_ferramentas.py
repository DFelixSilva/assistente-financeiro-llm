"""Testes das ferramentas de cálculo e da validação. Não chamam a API."""

import json

import pytest

from assistente_financeiro import executar_ferramenta, juros_compostos, juros_simples


def test_juros_simples():
    assert juros_simples(5000, 12, 18) == {"montante": 5900.0, "juros": 900.0}


def test_juros_compostos_taxa_efetiva_anual():
    # 12% a.a. efetivos por 12 meses devem render exatamente 12%
    r = juros_compostos(5000, 12, 12)
    assert r["montante"] == pytest.approx(5600.0)
    assert r["taxa_mensal_equivalente_pct"] == pytest.approx(0.9489, abs=1e-4)


def test_compostos_rendem_mais_que_simples_apos_um_ano():
    assert juros_compostos(1000, 10, 36)["montante"] > juros_simples(1000, 10, 36)["montante"]


def test_rejeita_valor_negativo():
    r = json.loads(executar_ferramenta("juros_simples", '{"principal": -1, "taxa_anual": 10, "meses": 3}'))
    assert "erro" in r


def test_rejeita_parametro_faltando():
    r = json.loads(executar_ferramenta("juros_compostos", '{"principal": 1000, "meses": 3}'))
    assert "erro" in r


def test_rejeita_json_invalido():
    r = json.loads(executar_ferramenta("juros_simples", "não é json"))
    assert "erro" in r
