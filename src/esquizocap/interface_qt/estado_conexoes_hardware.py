"""Se o Arduino e o BITalino estão conectados agora.

Não é configuração (o que conectar, ex. porta/MAC — isso é `ConfiguracaoSelecionada`)
nem leitura ao vivo (o que o sinal está dizendo — isso é `LeituraAoVivo`): é um
terceiro estado, com ciclo de vida próprio. Sobrevive ao fim de uma aquisição — parar
não desconecta o hardware, só desconectar de verdade ou fechar a janela zera isto.
"""

from dataclasses import dataclass


@dataclass
class EstadoConexoesHardware:
    """Estado de conexão das duas bordas de hardware."""

    arduino_conectado: bool = False
    bitalino_conectado: bool = False
