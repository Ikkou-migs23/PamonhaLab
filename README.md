# 🌽 Pamonha Lab

Um mini ecossistema de trabalhos e ferramentas digitais. (MVP em Python + Flask)

> Você traz a demanda. O Pamonha Lab ajuda a transformar em resultado.

## Ferramentas

| Rota | O que faz | Lib principal |
|---|---|---|
| `/ferramentas/imagem` | Converte formato, redimensiona, comprime, preto e branco | Pillow |
| `/ferramentas/vetor` | Imagem para SVG colorido em camadas (k-means em Lab + contornos suaves) | OpenCV, scikit-learn, NumPy |
| `/ferramentas/video` | Divide um vídeo em cortes de duração fixa e entrega um ZIP (processa em segundo plano) | MoviePy |
| `/ferramentas/automacao` | Divide PDF por capítulos, extrai páginas, cria várias pastas de uma vez (ZIP) | pypdf |
| `/pedido` | Formulário para serviços sob encomenda (design, arquivos, outros) | SQLite |
| `/admin` | Lista os pedidos e muda o status | - |

As ferramentas de vetor, vídeo e automação vêm dos projetos `Vetorizar-Imagem`, `video-cut`, `cortar-pdf` e `Create-Files`, adaptados para o navegador (a lógica fica em `servicos/`).

## Como rodar

Requisitos: Python 3.9+ e **FFmpeg** instalado no sistema (usado pelo MoviePy).

```bash
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt

export ADMIN_PASSWORD="uma-senha-sua"   # senha do /admin (usuário: qualquer um)
export SECRET_KEY="uma-chave-qualquer"
python app.py
```

Abra http://127.0.0.1:5000

Em produção, use **um único worker** (o andamento dos cortes é ligado ao processo):

```bash
gunicorn -w 1 --threads 4 --timeout 120 app:app
```

## Estrutura

```
app.py              rotas e banco
servicos/vetor.py   vetorização
servicos/video.py   cortes de vídeo
servicos/automacao.py   PDF e pastas
templates/ static/  páginas e visual
uploads/ jobs/      arquivos temporários (criados automaticamente)
```

## Notas

- Limite de upload: 2 GB no vídeo e 200 MB nas demais ferramentas (ajuste `MAX_CONTENT_LENGTH` e `LIMITE_PADRAO` em `app.py`). Lembre que o vídeo ocupa espaço em disco durante o corte: conte ~2x o tamanho do arquivo. Imagens para vetorizar são reduzidas para 1600 px de lado maior.
- Os ZIPs de vídeo ficam disponíveis por 2 horas e depois são apagados.
- Detecção de capítulos: procura uma linha só com número romano (I, II, III...). PDFs escaneados (sem texto) não funcionam.

🇧🇷 Goiás, Brasil. Feito com criatividade, código e um pouco de pamonha. 🌽
