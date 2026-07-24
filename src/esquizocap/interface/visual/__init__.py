"""Tradução do sinal em imagem: cores (HSV↔QColor), bandas de EEG e o simulador da fita LED.

O que esta camada produz é *visual* — cor e movimento da fita —, e é por isso que os bugs
daqui falham em silêncio (fita na cor errada, sem exceção). Mantê-la separada do estado e do
transporte deixa claro onde procurar quando a cor sai errada.
"""
