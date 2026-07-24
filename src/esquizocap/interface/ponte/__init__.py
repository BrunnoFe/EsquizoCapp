"""Pontes assíncronas entre a GUI thread e o mundo lento: conexão do BITalino e gravação.

O que mora aqui existe para não travar a interface: operações que bloqueiam (parear o
BITalino, drenar a gravação pendente) rodam fora da GUI thread e devolvem o resultado por
sinal. Manter esse transporte separado do estado e do visual isola o código sensível a
thread num canto só.
"""
