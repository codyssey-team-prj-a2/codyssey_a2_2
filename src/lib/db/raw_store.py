# lib/db/raw_store.py
"""raw 저장소: fetch가 수집한 원본 데이터를 가공 없이 JSONL로 저장한다.

clean.py가 이 파일들을 읽어 정제 후 clean_news 테이블(sqlite_mgr)로 옮긴다.
레코드에는 수집 시각(collected_at)과 소스 메타데이터(source_name/method/category)가
이미 포함돼 있으므로(fetch_via_rss 참고), 이 모듈은 그대로 append/read만 담당한다.
"""
import json
import os
from lib.system import config_mgr


def _raw_dir():
    cfg = config_mgr.load_config()
    raw_dir = cfg.get("raw_path", "./data/raw")
    os.makedirs(raw_dir, exist_ok=True)
    return raw_dir


def _path_for(source_name):
    return os.path.join(_raw_dir(), f"{source_name}.jsonl")


def append(source_name, record):
    with open(_path_for(source_name), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_all(source_name=None):
    raw_dir = _raw_dir()
    if source_name:
        paths = [_path_for(source_name)]
    else:
        paths = [
            os.path.join(raw_dir, name)
            for name in sorted(os.listdir(raw_dir))
            if name.endswith(".jsonl")
        ]
    records = []
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def list_sources():
    raw_dir = _raw_dir()
    return sorted(
        name[:-6] for name in os.listdir(raw_dir) if name.endswith(".jsonl")
    )
