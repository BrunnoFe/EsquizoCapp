# Engine visual (Godot) — integração arquivada

Esta integração foi **retirada de propósito**, pendente de reescrita do zero. Nada aqui
é importado pelo sistema em execução: o núcleo não abre socket, não lança processo e não
envia nada pela rede.

O código foi arquivado, e não apagado, porque documenta um protocolo que chegou a
funcionar de ponta a ponta.

## O que tem aqui

| Arquivo | O que era |
|---|---|
| `server.py` | Servidor TCP (vinha de `tools/server.py`, antes da reorganização em `src/`). A aplicação era o servidor; o Godot conectava como cliente. Fazia bind na IP da LAN e auto-incrementava a porta a partir da 5050. |
| `engine_real.py` | `EngineGodot`: lançava o executável e falava pelo socket. O `aguardar_conexao` era um `accept()` bloqueante, sem timeout, na thread da GUI. |
| `engine_fake.py` | `EngineSimulada`: fingia a engine, sem processo nem socket. |
| `engine_protocolo.py` | Montagem da mensagem de 9 campos. |
| `interfaces_engine.py` | O Protocol `EngineVisual` e o `ErroEngineDesconectada`, que viviam em `src/esquizocap/hardware/contratos.py`. |

## Achados confirmados sobre o protocolo

A mensagem tinha 9 campos separados por hífen:
`R-G-B-octaves-zoomfact-zoomcoef-brilho-power-intensity`
(ex.: `110-0-120-196-17,32-1,266-1-2-0,038`).

- **É RGB, não HSV.** Confirmado no fonte da engine: `godot/ChangeColor.cs:39` faz
  `Color color = new(r, g, b)`, com cada campo dividido por 255. Comentários dos dois
  lados diziam "H,S,V" — os dois estavam errados, e um herdou o erro do outro.
- **Decimais com vírgula estão certos.** O C# usa `Convert.ToDouble` com a cultura do
  sistema (pt-BR), então `17,32` é o formato esperado e `17.32` quebraria o parser.

## Achado sobre o shader (o motivo de nada disso ter efeito hoje)

`godot/ChangeColor.cs:43-50` seta os uniforms `line_color`, `octaves`, `zoom_factor`,
`zoom_coef`, `brilho`, `power` e `intensity`.

Mas a cena principal (`godot/project.godot` → `node_2d.tscn`) usa o
**`qwen_real.gdshader`**, que **não declara nenhum desses uniforms** (só `iResolution`).
No Godot, setar um uniform inexistente é silenciosamente ignorado — ou seja, **o EEG não
afetava a imagem em nada**; o visual era 100% dirigido por `TIME`.

Quem consumiria os 7 uniforms é o **`Basic_shader.gdshader`**, que existe no projeto mas
**não está atribuído à cena**. Ele foi claramente o alvo original do protocolo. Detalhe
sugestivo: nele o `zoom_factor` está comentado como `//frequenia`.

**Não confirmado:** se o binário compilado em `engine/` reflete esse estado ou foi gerado
de uma versão anterior, com o `Basic_shader` atribuído. Isso só se resolve rodando os
dois lados juntos.

## Onde estão os parâmetros hoje

Continuam sendo calculados a cada ciclo, em `ParametrosVisual`
(`src/esquizocap/dominio/ciclo_aquisicao.py`), prontos para uma engine nova consumir — só não são
enviados a lugar nenhum. Lá eles são números, e não texto: a formatação com vírgula
decimal era exigência do parser do Godot, isto é, um detalhe de transporte.

Os 6 campos não-cromáticos seguem **sorteados**, sem relação com o sinal EEG — como
sempre foram. Se devem passar a reagir ao EEG é decisão em aberto; ver
`DECISOES_PENDENTES.md`.
