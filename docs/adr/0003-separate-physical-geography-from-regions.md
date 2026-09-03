# Separar geografia física de regiões

- Status: Aceita
- Data: 2026-09-02

O mapa mantém as pegadas de `Region` como camada territorial semântica, enquanto
uma camada de geografia física pertencente ao `Map` se torna a única verdade de
terreno, elevação e água.

Foi rejeitada a derivação de terreno pelo tipo de região porque uma única região
precisa poder conter vales, montanhas, rios e assentamentos sem duplicar ou mudar
sua identidade. Também foi rejeitado um simulador independente de tiles porque
o mundo permanece region-first e multiescala.

As `Routes` já pertencentes ao mapa continuam sendo as únicas conexões explícitas
entre regiões. Overlays visuais devem ser projeções da geografia canônica ou do
estado dinâmico de seus respectivos domínios, nunca novos donos da realidade.
