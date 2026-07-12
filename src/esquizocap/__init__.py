"""EsquizoCap — aquisição de EEG, predição de cor e saída para fita de LED.

Camadas:
    - `dominio`: núcleo de negócio, sem GUI e sem hardware.
    - `hardware`: contratos das bordas físicas e suas implementações (real e fake).
    - `infraestrutura`: configuração, logging, caminhos, exportação de dados.
    - `interface`: tudo que é Tkinter/ttkbootstrap.
"""
