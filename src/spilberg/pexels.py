import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional


class PexelsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY")
        if not self.api_key:
            raise ValueError("PEXELS_API_KEY nao encontrada no ambiente")
        self.base_url = "https://api.pexels.com/videos/search"

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
        req = urllib.request.Request(url, headers={"Authorization": self.api_key})
        
        try:
            with urllib.request.urlopen(req) as response:
                if response.status != 200:
                    return None
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

        videos = data.get("videos", [])
        if not videos:
            return None

        # Pega o primeiro video relevante
        best_video = videos[0]
        video_files = best_video.get("video_files", [])
        
        # Procura por um arquivo HD (720p ou 1080p) para economizar banda/processamento
        hd_files = [
            f for f in video_files 
            if f.get("quality") == "hd" and f.get("width", 0) >= 720
        ]
        
        if hd_files:
            return hd_files[0]["link"]
            
        # Fallback: pega qualquer hd, senao sd
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
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            with open(dest_path, "wb") as f:
                while chunk := response.read(8192):
                    f.write(chunk)
        return dest_path
