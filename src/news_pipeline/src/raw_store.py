"""raw 저장소: data/raw/{source_name}.jsonl 에 원본 데이터를 가공 없이 저장."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"


def configure(raw_dir: str | None) -> None:
    """main.py가 기동 시 config.json의 storage.raw_dir로 덮어쓰기 위해 호출한다."""
    global RAW_DIR
    if raw_dir:
        RAW_DIR = BASE_DIR / raw_dir


def _path_for(source_name: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR / f"{source_name}.jsonl"


def append(source_name: str, record: dict) -> None:
    path = _path_for(source_name)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_all(source_name: str | None = None) -> list[dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    files = [_path_for(source_name)] if source_name else sorted(RAW_DIR.glob("*.jsonl"))
    records = []
    for path in files:
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def list_sources() -> list[str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in RAW_DIR.glob("*.jsonl"))
