"""Testes de ingestao da Semana 1.

(a) retry: baixar() tenta de novo apos uma falha de rede.
(b) idempotencia: ingerir o mesmo pacote duas vezes nao duplica arquivos.
"""

from __future__ import annotations

import httpx
import pytest

from ingestion import bcb, cvm


def test_baixar_tenta_de_novo_apos_falha(monkeypatch):
    """A 1a chamada HTTP falha, a 2a retorna OK. baixar() deve retentar e ter sucesso."""
    chamadas = {"n": 0}

    class FakeResp:
        content = b"conteudo-ok"

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise httpx.ConnectError("falha de rede simulada")
        return FakeResp()

    monkeypatch.setattr(cvm.httpx, "get", fake_get)

    resultado = cvm.baixar("https://exemplo/arquivo.zip")

    assert resultado == b"conteudo-ok"
    assert chamadas["n"] == 2  # falhou 1x, teve sucesso na 2a tentativa


def test_baixar_bcb_tenta_de_novo_apos_falha(monkeypatch):
    """Mesmo contrato de retry para a ingestao do BCB."""
    chamadas = {"n": 0}

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"data": "01/01/2025", "valor": "1.0"}]

    def fake_get(url, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise httpx.ReadTimeout("timeout simulado")
        return FakeResp()

    monkeypatch.setattr(bcb.httpx, "get", fake_get)

    dados = bcb.baixar(432, "01/01/2025", "31/12/2025")

    assert dados == [{"data": "01/01/2025", "valor": "1.0"}]
    assert chamadas["n"] == 2


def _zip_fake(nomes_e_conteudos: dict[str, str]) -> bytes:
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, conteudo in nomes_e_conteudos.items():
            z.writestr(nome, conteudo)
    return buf.getvalue()


def test_ingerir_doc_e_idempotente(tmp_path, monkeypatch):
    """Rodar ingerir_doc duas vezes com o mesmo pacote nao recria o Parquet.

    Detectamos a nao-duplicacao comparando o mtime do Parquet: na 2a execucao,
    como _ja_ingerido() retorna True, o arquivo nao e reescrito.
    """
    # RAW aponta para um diretorio temporario isolado
    monkeypatch.setattr(cvm, "RAW", tmp_path / "cvm")

    csv = "CNPJ_CIA;VL_CONTA\n11.111/0001-11;100\n22.222/0001-22;200\n"
    zip_bytes = _zip_fake({"dfp_cia_aberta_DRE_con_2025.csv": csv})

    # baixar() sempre devolve o mesmo pacote (mesmo sha)
    monkeypatch.setattr(cvm, "baixar", lambda url: zip_bytes)

    cvm.ingerir_doc("DFP", 2025)
    parquet = tmp_path / "cvm" / "DFP" / "2025" / "dfp_cia_aberta_DRE_con_2025.parquet"
    assert parquet.exists()
    mtime_1 = parquet.stat().st_mtime_ns

    # 2a execucao: deve pular (idempotente), sem reescrever o arquivo
    cvm.ingerir_doc("DFP", 2025)
    mtime_2 = parquet.stat().st_mtime_ns

    assert mtime_1 == mtime_2, "o Parquet foi reescrito: a ingestao nao e idempotente"

    # e nao deve ter criado arquivos extras no diretorio
    parquets = list((tmp_path / "cvm" / "DFP" / "2025").glob("*.parquet"))
    assert len(parquets) == 1


@pytest.mark.parametrize(
    "ini,fim,esperado",
    [
        (2020, 2025, [("01/01/2020", "31/12/2024"), ("01/01/2025", "31/12/2025")]),
        (2025, 2025, [("01/01/2025", "31/12/2025")]),
        (2010, 2019, [("01/01/2010", "31/12/2014"), ("01/01/2015", "31/12/2019")]),
    ],
)
def test_janelas_bcb_respeitam_limite_de_5_anos(ini, fim, esperado):
    """Janelas do BCB nunca passam de 5 anos (a API corta em 10 para series diarias)."""
    assert bcb._janelas(ini, fim) == esperado
