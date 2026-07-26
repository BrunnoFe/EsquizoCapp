"""Formato do nome do arquivo de gravação.

O formato é digitado pelo usuário, e a validação acontece no pior momento possível: a
aquisição já terminou e os dados estão em memória, esperando um destino. Um formato
inválido não pode custar a gravação, então tudo aqui cai no padrão em vez de levantar.
"""

import pytest

from esquizocap.infraestrutura import persistencia


class TestFormatoPadrao:
    def test_sem_formato_usa_o_nome_herdado(self) -> None:
        nome = persistencia.nome_sugerido('Amplitude')

        assert nome.startswith('Gravação Amplitude_')

    @pytest.mark.parametrize('formato', ['', '   '])
    def test_formato_em_branco_cai_no_padrao(self, formato: str) -> None:
        assert persistencia.nome_sugerido('Amplitude', formato).startswith('Gravação Amplitude_')


class TestMarcadores:
    def test_substitui_os_marcadores_do_contexto(self) -> None:
        nome = persistencia.nome_sugerido(
            'Frequência',
            'EEG_{modo}_{canal}_{taxa}',
            {'canal': 'A4', 'taxa': '1000Hz'},
        )

        assert nome == 'EEG_Frequência_A4_1000Hz'

    def test_todos_os_marcadores_anunciados_funcionam(self) -> None:
        """A interface lista `MARCADORES_DO_NOME` como clicáveis; um que não resolvesse
        derrubaria o nome inteiro para o padrão sem o usuário entender por quê."""
        formato = '_'.join('{' + marcador + '}' for marcador in persistencia.MARCADORES_DO_NOME)

        nome = persistencia.nome_sugerido('Amplitude', formato, {'canal': 'A1', 'taxa': '100Hz'})

        assert 'Gravação' not in nome, 'não pode ter caído no padrão'
        assert 'Amplitude' in nome and 'A1' in nome and '100Hz' in nome

    def test_marcador_sem_contexto_vira_vazio(self) -> None:
        nome = persistencia.nome_sugerido('Amplitude', 'x{canal}x')

        assert nome == 'xx'


class TestFormatoInvalido:
    @pytest.mark.parametrize('formato', ['{cannal}', '{', '{0}', '{modo!z}'])
    def test_formato_quebrado_cai_no_padrao_sem_levantar(self, formato: str) -> None:
        nome = persistencia.nome_sugerido('Amplitude', formato)

        assert nome.startswith('Gravação Amplitude_')

    @pytest.mark.parametrize('proibido', ['/', '\\', ':', '*', '?', '"', '<', '>', '|'])
    def test_caractere_proibido_pelo_sistema_de_arquivos_e_trocado(self, proibido: str) -> None:
        """Uma barra viraria uma pasta inexistente, e a gravação falharia só no fim."""
        nome = persistencia.nome_sugerido('Amplitude', f'a{proibido}b')

        assert proibido not in nome
        assert nome == 'a-b'

    def test_formato_que_resulta_em_nada_cai_no_padrao(self) -> None:
        """Um nome vazio abriria o diálogo de salvar sem nome nenhum."""
        nome = persistencia.nome_sugerido('Amplitude', '{canal}')

        assert nome.startswith('Gravação Amplitude_')

    def test_ponto_final_e_removido(self) -> None:
        """O Windows descarta pontos finais em nome de arquivo, em silêncio."""
        assert persistencia.nome_sugerido('Amplitude', 'coleta.') == 'coleta'
