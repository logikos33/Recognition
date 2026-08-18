# D-002 · Corrigir o desperdício antes de medir custo

**Seção:** Infraestrutura e custo · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**02/08 · Vitor · 🔄 em execução**

Watchdog derrubando o stream, loop de FFmpeg condenado, 425 repedidos, abas duplicando download.
Tudo isso é CPU e egress pagos que não entregam imagem. Medir antes de corrigir seria medir desperdício
e projetar em cima dele.
