"""Fonte de frame HLS do edge — ordem, dedup e PERDA MEDIDA.

O que estes testes travam é justamente o que se erra em silêncio: andar para
trás na ordem dos segmentos, reprocessar o mesmo frame, e principalmente
DEIXAR DE CONTAR o segmento que expirou sem ser visto (a perda por TTL some
sozinha se ninguém a somar).

Nenhum caso aqui depende de cv2: o decode é exercitado só no caminho em que o
segmento já expirou, que é onde mora a contagem de perda.
"""
from app.infrastructure.queue.tasks.hls_frame_source import (
    TTL_SEGMENTO_S,
    FonteHlsDoEdge,
    chave_playlist,
    chave_segmento,
    segmentos_da_playlist,
)

CAM = "eb1501db-82ad-485a-a441-5c665b4e5a28"


class FakeRedis:
    def __init__(self, dados=None, ttls=None):
        self.dados = dados or {}
        self.ttls = ttls or {}

    def get(self, chave):
        return self.dados.get(chave)

    def ttl(self, chave):
        return self.ttls.get(chave, -2)


def _playlist(*nomes):
    linhas = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:2"]
    for n in nomes:
        linhas += ["#EXTINF:2.000000,", n]
    return "\n".join(linhas).encode()


def test_playlist_preserva_a_ordem_do_ffmpeg_e_ignora_diretiva():
    assert segmentos_da_playlist(_playlist("stream8.ts", "stream9.ts", "stream10.ts")) == [
        "stream8.ts", "stream9.ts", "stream10.ts",
    ]


def test_stream10_vem_depois_de_stream9_nao_antes():
    """A armadilha: ordem lexicográfica poria stream10 antes de stream9 e o
    consumidor andaria para trás sem erro nenhum."""
    nomes = segmentos_da_playlist(_playlist("stream9.ts", "stream10.ts"))
    assert nomes[-1] == "stream10.ts"
    assert sorted(nomes)[-1] == "stream9.ts"  # prova de que ordenar quebraria


def test_segmento_expirado_conta_como_perda_e_nao_trava_o_consumidor():
    """Anunciado na playlist, ausente do Redis = perdido pelo TTL. Tem de
    somar no contador E avançar a marca, senão o laço fica preso nele."""
    r = FakeRedis({chave_playlist(CAM): _playlist("stream1.ts")})
    fonte = FonteHlsDoEdge(CAM, r)

    frame, idade = fonte.proximo_frame()

    assert frame is None and idade is None
    assert fonte.perdidos_por_ttl == 1
    assert fonte.consumidos == 0
    # avançou: um segundo passe não recontaria o mesmo segmento
    assert fonte.proximo_frame() == (None, None)
    assert fonte.perdidos_por_ttl == 1


def test_conta_os_segmentos_pulados_entre_duas_leituras():
    """Consumiu o 1, e na volta seguinte a playlist já está no 4.

    A conta correta desta 2ª leitura é TRÊS, não dois: `stream2` e `stream3`
    passaram sem ser vistos, e `stream4` foi anunciado mas já tinha expirado
    quando fomos buscá-lo. Errei essa soma na primeira escrita do teste e o
    próprio check me corrigiu — fica registrada porque é exatamente o tipo de
    perda que se subestima."""
    r = FakeRedis({chave_playlist(CAM): _playlist("stream1.ts")})
    fonte = FonteHlsDoEdge(CAM, r)
    fonte.proximo_frame()          # stream1 expirado -> perda 1, marca avança
    assert fonte.perdidos_por_ttl == 1

    r.dados[chave_playlist(CAM)] = _playlist(
        "stream1.ts", "stream2.ts", "stream3.ts", "stream4.ts"
    )
    fonte.proximo_frame()          # alvo = stream4; 2 e 3 ficaram para trás

    assert fonte.perdidos_por_ttl == 1 + 3  # 1 anterior + (s2, s3 pulados) + (s4 expirado)


def test_playlist_ausente_ou_vazia_nao_conta_perda():
    """Câmera que ainda não começou a transmitir não é perda — é silêncio."""
    fonte = FonteHlsDoEdge(CAM, FakeRedis())
    assert fonte.proximo_frame() == (None, None)
    assert fonte.perdidos_por_ttl == 0

    fonte2 = FonteHlsDoEdge(CAM, FakeRedis({chave_playlist(CAM): _playlist()}))
    assert fonte2.proximo_frame() == (None, None)
    assert fonte2.perdidos_por_ttl == 0


def test_idade_sai_do_ttl_restante():
    r = FakeRedis(
        {chave_playlist(CAM): _playlist("stream7.ts")},
        {chave_segmento(CAM, "stream7.ts"): TTL_SEGMENTO_S - 4},
    )
    fonte = FonteHlsDoEdge(CAM, r)
    assert fonte._idade_do_segmento_s(chave_segmento(CAM, "stream7.ts")) == 4.0


def test_idade_desconhecida_quando_o_redis_nao_sabe():
    """TTL -1 (sem expiração) e -2 (chave ausente) viram None, nunca um
    número inventado — latência exibida tem de ser medida ou ausente."""
    fonte = FonteHlsDoEdge(CAM, FakeRedis({}, {"k": -1}))
    assert fonte._idade_do_segmento_s("k") is None
    assert fonte._idade_do_segmento_s("inexistente") is None
