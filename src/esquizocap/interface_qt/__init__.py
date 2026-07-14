"""Interface gráfica em PySide6/QML do EsquizoCap.

Substitui a antiga interface Tkinter (arquivada em `interface_tkinter_legado/`, na raiz do
projeto). A regra que se mantém: esta camada só lê e chama o `dominio/`, a `aplicacao/` e o
`hardware/` — nunca reimplementa lógica de negócio.
"""
