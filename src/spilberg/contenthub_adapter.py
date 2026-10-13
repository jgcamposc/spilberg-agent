"""Explicit preview renderer using Content Hub's private worker request shape.

Run in a dedicated worker process. This neither adopts, approves nor publishes.
The caller owns master lineage, budget, job state and speaker selection.
"""
import json
import os
from pathlib import Path
import sys


def render_request(request):
    options = request.get("options", {})
    if request.get("asset", {}).get("type") != "video" or options.get("aspect") == "horizontal":
        raise ValueError("O adaptador CIBO requer master de vídeo e entrega vertical")
    source = Path(request["source"]).resolve(strict=True)
    output = Path(request["output"]).resolve()
    report = Path(request["report"]).resolve()
    if report.exists() or report in {source, output}:
        raise FileExistsError("Escolha um recibo novo para esta versão")
    for key in ("ffmpeg", "ffprobe"):
        if request.get(key):
            os.environ["SPILBERG_" + key.upper()] = str(Path(request[key]).resolve(strict=True))
    from .spilberg2_engine import render_spilberg2_cut, captions_from_transcript
    clip = request["clip"]
    transcript = {"segments": [{"start": c["start"], "end": c["end"], "text": c["text"], "words": c.get("words", [])} for c in request.get("cues", [])]}
    # A shared style belongs to Content Hub's existing finalizer. Never burn
    # Cal Sans first and prevent that finalizer from honoring the user's choice.
    owns_captions = options.get("subtitles", True) and not options.get("captionStyle")
    caps = captions_from_transcript(transcript, clip["start"], clip["end"]) if owns_captions else []
    if owns_captions and not caps:
        raise ValueError("Legendas selecionadas, mas nenhuma evidência temporizada está disponível no corte")
    cibo = options.get("cibo", {})
    render_spilberg2_cut(source, clip["start"], clip["end"], "", caps, output, output.parent/"spilberg2-work", assets_dir=cibo.get("assets_dir"), encoder=cibo.get("encoder", "auto"), intro=cibo.get("intro", True), filmburn=cibo.get("filmburn", True), clicks=cibo.get("clicks", True), embed_cover=False)
    qa = json.loads(output.with_suffix(".render.json").read_text())
    payload = {"output": str(output), "captionsBurned": bool(caps), "engine": "spilberg2-cibo", "qa": qa}
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("x") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return payload


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Explicit Spilberg2 Content Hub preview worker")
    parser.add_argument("request")
    args = parser.parse_args()
    result = render_request(json.loads(Path(args.request).read_text()))
    print(json.dumps({"done": True, "captionsBurned": result["captionsBurned"]}))

if __name__ == "__main__":
    main()
