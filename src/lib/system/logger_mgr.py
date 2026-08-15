# src/lib/system/logger_mgr.py
import os
import logging
# [추가] 로그 파일 크기 제한 및 회전을 위한 모듈
from logging.handlers import RotatingFileHandler
from lib.system import config_mgr

def init_logger():
    """
    config.json의 설정(파일 경로, 로그 수준)을 읽어와서
    시스템 전역(Root) 로거를 초기화합니다.
    (main.py와 automation.py의 가장 첫 부분에서 한 번만 호출됩니다)
    """
    # 1. 설정 파일에서 로그 정보 가져오기[cite: 12]
    cfg = config_mgr.load_config()
    log_cfg = cfg.get("logging", {})
    log_file = log_cfg.get("file", "./logs/app.log")
    log_level_str = log_cfg.get("level", "INFO").upper()

    # 2. 로그를 저장할 폴더가 없다면 자동 생성
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 3. 문자열 수준(Level)을 logging 모듈의 상수로 변환
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    log_level = level_map.get(log_level_str, logging.INFO)

    # 4. Root 로거 설정
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # 핸들러가 여러 번 중복 추가되는 것을 방지
    if not logger.handlers:
        # [수정] 무한히 커지는 FileHandler 대신, 용량 제한이 있는 RotatingFileHandler 사용
        # maxBytes: 5MB (5 * 1024 * 1024 bytes) 도달 시 새 파일 생성
        # backupCount: 오래된 로그 파일 3개까지만 보관 (총 용량 최대 20MB 이내로 엄격히 통제)
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=5*1024*1024, 
            backupCount=3, 
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)

        # 로그 메시지 포맷 설정
        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # 로거에 핸들러 부착
        logger.addHandler(file_handler)

def get_logger(name):
    """
    각 모듈에서 사용할 로거 객체를 반환합니다.
    사용 예: logger = logger_mgr.get_logger(__name__)
    """
    return logging.getLogger(name)