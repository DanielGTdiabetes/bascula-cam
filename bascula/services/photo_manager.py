# -*- coding: utf-8 -*-
import os, json, time
from dataclasses import dataclass, asdict
from pathlib import Path
try:
    from PIL import Image
    _PIL_OK = True
except Exception:
    _PIL_OK = False

HOME = Path(os.path.expanduser("~"))
BASE = HOME / ".bascula" / "photos"; STAGING = BASE / "staging"; META = BASE / "meta"
CFG = BASE / "config.json"

@dataclass
class PhotoConfig:
    max_count:int=500; max_bytes:int=800*1024*1024; jpeg_quality:int=90; prefix:str="cap"; keep_last_n_after_use:int=0
    @staticmethod
    def load():
        try:
            if CFG.exists(): return PhotoConfig(**json.loads(CFG.read_text()))
        except Exception: pass
        return PhotoConfig()
    def save(self): BASE.mkdir(parents=True, exist_ok=True); CFG.write_text(json.dumps(asdict(self), indent=2))

class PhotoManager:
    def __init__(self, logger=None, config:PhotoConfig=None):
        self.log = logger or type("L", (), {"info":lambda *a,**k:None,"warning":lambda *a,**k:None,"error":lambda *a,**k:None})()
        self.cfg = config or PhotoConfig.load()
        for d in (BASE, STAGING, META): d.mkdir(parents=True, exist_ok=True)
        self.picam2 = None
    def attach_camera(self, picam2): self.picam2 = picam2; self.log.info("PhotoManager: cámara adjuntada.")
    def capture(self, label="manual"):
        ts = time.strftime("%Y%m%d-%H%M%S", time.localtime()); ms = int((time.time()%1)*1000)
        name = f"{self.cfg.prefix}-{ts}-{ms:03d}-{''.join(c if c.isalnum() else '-' for c in label).strip('-') or 'x'}.jpg"
        p = STAGING / name
        try:
            self.picam2.capture_file(str(p), format="jpeg", quality=self.cfg.jpeg_quality)
        except Exception:
            if not _PIL_OK:
                raise
            arr = self.picam2.capture_array()
            img = Image.fromarray(arr)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(p, "JPEG", quality=self.cfg.jpeg_quality, optimize=True)
        (META / (p.stem + ".json")).write_text(json.dumps({"label":label,"ts":time.time()}))
        self._enforce_limits()
        return p
    def mark_used(self, path:Path):
        mp = META / (Path(path).stem + ".json")
        for q in (Path(path), mp):
            try:
                if q.exists(): q.unlink()
            except Exception: pass
    def _enforce_limits(self):
        files = sorted(STAGING.glob("*.jpg"), key=lambda x: x.stat().st_mtime)
        if len(files) > self.cfg.max_count:
            for p in files[:len(files)-self.cfg.max_count]:
                try: p.unlink(); (META/(p.stem+".json")).unlink(missing_ok=True)
                except Exception: pass
        total = sum(p.stat().st_size for p in STAGING.glob("*.jpg"))
        i=0
        while total > self.cfg.max_bytes and i < len(files):
            fp = files[i]; sz = fp.stat().st_size
            try: fp.unlink(); (META/(fp.stem+".json")).unlink(missing_ok=True)
            except Exception: pass
            total -= sz; i+=1

    def clear_all(self):
        try:
            for p in STAGING.glob("*.jpg"):
                try:
                    p.unlink()
                except Exception:
                    pass
            for m in META.glob("*.json"):
                try:
                    m.unlink()
                except Exception:
                    pass
            self.log.info("PhotoManager: staging/meta limpiado")
        except Exception:
            pass
