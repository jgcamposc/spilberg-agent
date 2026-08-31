import json
import os
import ssl
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Optional


class PexelsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY")
        if not self.api_key:
            raise ValueError("PEXELS_API_KEY nao encontrada no ambiente")
        self.base_url = "https://api.pexels.com/videos/search"

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        """Usa a cadeia de confiança normal; nunca desabilita TLS para mídia externa."""
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            return ssl.create_default_context()

    def _open(self, request: urllib.request.Request):
        try:
            return urllib.request.urlopen(request, context=self._ssl_context(), timeout=30)
        except HTTPError as error:
            raise RuntimeError(f"Pexels respondeu HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"Falha de rede ao acessar Pexels: {error.reason}") from error

    def search_video(self, query: str, orientation: str = "landscape") -> Optional[str]:
        """
        Busca um video no Pexels e retorna a URL do arquivo de video MP4
        na resolucao 720p/1080p. Retorna None se nao encontrar.
        """
        params = {
            "query": query,
            "orientation": orientation,
            "per_page": 5,
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        headers = {"Authorization": self.api_key, "User-Agent": "Spilberg-Agent/1.0"}
        req = urllib.request.Request(url, headers=headers)

        with self._open(req) as response:
            if response.status != 200:
                raise RuntimeError(f"Pexels respondeu status inesperado: {response.status}")
            data = json.loads(response.read().decode("utf-8"))

        videos = data.get("videos", [])
        if not videos:
            return None

        # Pega o primeiro vídeo retornado e escolhe um arquivo HD.
        best_video = videos[0]
        video_files = best_video.get("video_files", [])
        hd_files = [
            f for f in video_files
            if f.get("quality") == "hd" and f.get("width", 0) >= 720
        ]
        if hd_files:
            return hd_files[0]["link"]

        hd_files = [f for f in video_files if f.get("quality") == "hd"]
        if hd_files:
            return hd_files[0]["link"]
        sd_files = [f for f in video_files if f.get("quality") == "sd"]
        if sd_files:
            return sd_files[0]["link"]

        return None

    def download_video(self, url: str, dest_path: Path) -> Path:
        """
        Faz o download do video da URL especificada.
        """
        if not url.startswith("https://"):
            raise ValueError("Pexels deve fornecer uma URL HTTPS")
        destination = Path(dest_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "Spilberg-Agent/1.0"})
        with self._open(req) as response:
            with temporary.open("wb") as f:
                while chunk := response.read(8192):
                    f.write(chunk)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("Pexels não entregou um arquivo de vídeo utilizável")
        temporary.replace(destination)
        return destination
