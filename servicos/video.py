"""Cortes de vídeo em partes de duração fixa.
Adaptado do projeto video-cut (MoviePy)."""
import os


def cortar_video(caminho_entrada, pasta_saida, nome, duracao_corte, progresso=None):
    """Divide o vídeo em partes de `duracao_corte` segundos.
    Salva nome_001.mp4, nome_002.mp4... e nome_sobra.mp4 se sobrar um pedaço.
    Retorna a lista de arquivos criados. `progresso(feitos, total)` é opcional."""
    from moviepy import VideoFileClip  # import aqui: só carrega se for usado

    os.makedirs(pasta_saida, exist_ok=True)
    criados = []
    with VideoFileClip(caminho_entrada) as video:
        total_s = video.duration
        n_cortes = int(total_s // duracao_corte)
        tem_sobra = (total_s - n_cortes * duracao_corte) > 0.5
        total = n_cortes + (1 if tem_sobra else 0)
        if total == 0:  # vídeo menor que meio segundo
            raise ValueError("O vídeo é curto demais para cortar.")
        if progresso:
            progresso(0, total)

        def salvar(inicio, fim, arquivo):
            caminho = os.path.join(pasta_saida, arquivo)
            video.subclipped(inicio, fim).write_videofile(
                caminho, codec="libx264", audio_codec="aac", logger=None)
            criados.append(caminho)
            if progresso:
                progresso(len(criados), total)

        for i in range(n_cortes):
            salvar(i * duracao_corte, (i + 1) * duracao_corte, f"{nome}_{i + 1:03d}.mp4")
        if tem_sobra:
            salvar(n_cortes * duracao_corte, total_s, f"{nome}_sobra.mp4")
    return criados
