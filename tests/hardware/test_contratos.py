"""Testes de contrato das bordas de hardware.

A mesma bateria roda contra a implementação REAL e a FAKE. Se o fake divergir do
contrato, ele deixa de valer como substituto — e todo teste que depende dele passa a
mentir.

Nada aqui exige hardware plugado: só se testa o que é verificável sem Arduino nem
BITalino (instanciação, fechamento idempotente, context manager, validação de entrada).
Conectar de fato é território do `TESTES_MANUAIS.md`.
"""

import inspect

import pytest

from esquizocap.hardware.arduino_fake import ArduinoFake
from esquizocap.hardware.arduino_real import ArduinoSerial
from esquizocap.hardware.bitalino_direto import BitalinoDireto
from esquizocap.hardware.bitalino_fake import BitalinoSintetico
from esquizocap.hardware.bitalino_real import BitalinoLSL
from esquizocap.hardware.contratos import (
    ControladorLedArduino,
    ErroConexaoBitalino,
    LeitorBitalino,
)

IMPLEMENTACOES_ARDUINO = [ArduinoSerial, ArduinoFake]
IMPLEMENTACOES_BITALINO = [BitalinoLSL, BitalinoDireto, BitalinoSintetico]

PARAMETROS_DE_CONEXAO_BITALINO: tuple[str, ...] = ('endereco', 'taxa_amostragem_hz', 'canais')
"""Parâmetros que toda implementação da fonte de sinal precisa aceitar ao conectar."""

ENDERECO_INVALIDO: str = 'nao-e-um-endereco'
TAXA_QUALQUER_HZ: int = 1000
CANAIS_QUAISQUER: list[int] = [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize('classe', IMPLEMENTACOES_ARDUINO)
class TestContratoArduino:
    def test_e_subclasse_do_contrato(self, classe: type[ControladorLedArduino]) -> None:
        assert issubclass(classe, ControladorLedArduino)

    def test_comeca_desconectado(self, classe: type[ControladorLedArduino]) -> None:
        assert classe().esta_conectado is False

    def test_desconectar_e_idempotente(self, classe: type[ControladorLedArduino]) -> None:
        """O `__exit__` chama `desconectar` mesmo se `conectar` nunca rodou."""
        controlador = classe()

        controlador.desconectar()
        controlador.desconectar()

        assert controlador.esta_conectado is False

    def test_serve_de_context_manager(self, classe: type[ControladorLedArduino]) -> None:
        with classe() as controlador:
            assert isinstance(controlador, ControladorLedArduino)

        assert controlador.esta_conectado is False

    def test_o_context_manager_fecha_mesmo_com_excecao(self, classe: type[ControladorLedArduino]) -> None:
        """Fechar a porta é o motivo do `with` existir: precisa valer no caminho de erro."""
        controlador = classe()

        with pytest.raises(RuntimeError, match='falha simulada'):  # noqa: PT012
            with controlador:
                raise RuntimeError('falha simulada')

        assert controlador.esta_conectado is False

    def test_listar_portas_devolve_strings(self, classe: type[ControladorLedArduino]) -> None:
        portas = classe().listar_portas()

        assert isinstance(portas, list)
        assert all(isinstance(porta, str) for porta in portas)


@pytest.mark.parametrize('classe', IMPLEMENTACOES_BITALINO)
class TestContratoBitalino:
    def test_e_subclasse_do_contrato(self, classe: type[LeitorBitalino]) -> None:
        assert issubclass(classe, LeitorBitalino)

    def test_encerrar_stream_e_idempotente(self, classe: type[LeitorBitalino]) -> None:
        leitor = classe()

        leitor.encerrar_stream()
        leitor.encerrar_stream()

    def test_serve_de_context_manager(self, classe: type[LeitorBitalino]) -> None:
        with classe() as leitor:
            assert isinstance(leitor, LeitorBitalino)

    def test_o_context_manager_encerra_mesmo_com_excecao(self, classe: type[LeitorBitalino]) -> None:
        with pytest.raises(RuntimeError, match='falha simulada'):  # noqa: PT012
            with classe():
                raise RuntimeError('falha simulada')

    def test_conectar_carrega_taxa_de_amostragem_e_canais(self, classe: type[LeitorBitalino]) -> None:
        """O Modo Direto precisa mandar taxa e canais ao iniciar a aquisição no dispositivo.

        No Modo OpenSignals os dois já foram fixados fora da aplicação, então a implementação
        sobre LSL os ignora — mas eles têm que existir no contrato, senão a informação não tem
        caminho até a borda de hardware.
        """
        parametros = tuple(
            nome for nome in inspect.signature(classe.conectar).parameters if nome != 'self'
        )

        assert parametros == PARAMETROS_DE_CONEXAO_BITALINO

    def test_endereco_invalido_levanta_erro_do_contrato(self, classe: type[LeitorBitalino]) -> None:
        """Real e fake precisam rejeitar o mesmo lixo, com a mesma exceção."""
        with pytest.raises(ErroConexaoBitalino):
            classe().conectar(
                endereco=ENDERECO_INVALIDO,
                taxa_amostragem_hz=TAXA_QUALQUER_HZ,
                canais=CANAIS_QUAISQUER,
            )

    def test_definir_canal_ativo_vale_antes_de_conectar(self, classe: type[LeitorBitalino]) -> None:
        """O canal ativo é estado de INTERFACE: pode ser informado a qualquer momento, e
        trocá-lo nunca reconecta. Por isso não faz parte de `conectar`.

        Só o Modo Direto precisa dele — é ele que decide qual canal converter para
        microvolts. As outras implementações aceitam e ignoram.
        """
        leitor = classe()

        leitor.definir_canal_ativo(canal=1)
        leitor.definir_canal_ativo(canal=6)

    @pytest.mark.parametrize('canal_invalido', [0, 7, -1])
    def test_canal_ativo_fora_da_faixa_falha_alto(
        self, classe: type[LeitorBitalino], canal_invalido: int
    ) -> None:
        """Canal inexistente é erro de programação, não entrada de usuário: a interface só
        oferece 1 a 6. Falhar alto aqui evita converter o canal errado em silêncio."""
        with pytest.raises(ValueError, match='[Cc]anal'):
            classe().definir_canal_ativo(canal=canal_invalido)

    def test_ler_sem_conectar_nao_vaza_erro_cru(self, classe: type[LeitorBitalino]) -> None:
        """Nunca um `AttributeError` de `NoneType`: o contrato tem exceção própria."""
        leitor = classe()

        try:
            leitor.ler_amostra(timeout=0.1)
        except ErroConexaoBitalino:
            pass  # É o esperado no leitor real.
        except AttributeError as erro:  # pragma: no cover
            pytest.fail(f'Vazou erro cru em vez da exceção do contrato: {erro}')


class TestContratosSaoAbstratos:
    def test_o_contrato_nao_e_instanciavel(self) -> None:
        with pytest.raises(TypeError):
            ControladorLedArduino()  # type: ignore[abstract]

        with pytest.raises(TypeError):
            LeitorBitalino()  # type: ignore[abstract]

    def test_implementacao_incompleta_falha_na_instanciacao(self) -> None:
        """O ganho do abc sobre o Protocol: o erro aparece ao instanciar, e não no meio
        de uma aquisição, quando o método faltante for finalmente chamado."""

        class ArduinoIncompleto(ControladorLedArduino):
            @property
            def esta_conectado(self) -> bool:
                return False

            def listar_portas(self) -> list[str]:
                return []

            def conectar(self, porta: str, baudrate: int) -> None: ...

            def desconectar(self) -> None: ...

            # `enviar_comando_cor` ausente de propósito.

        with pytest.raises(TypeError, match='enviar_comando_cor'):
            ArduinoIncompleto()  # type: ignore[abstract]
