"""
로컬 테스트용 파이프라인 실행 스크립트.

사용법:
  python run_local.py

준비사항:
  1. .env 파일에 환경변수 설정 (.env.example 참고)
  2. credentials/service_account.json 배치
  3. 구글 드라이브 wikis 폴더에 wiki.json, index.html 미리 업로드
     (서비스 계정은 파일 신규 생성 불가 — 기존 파일 업데이트만 가능)
     → 드라이브 설정에서 'Google 문서 자동변환' 옵션 해제 후 업로드할 것
"""
import dotenv
dotenv.load_dotenv()

from src.pipeline.runner import run_pipeline

print("파이프라인 시작...")
result = run_pipeline()

print("\n===== 결과 =====")
print(f"상태     : {result['status']}")
print(f"처리     : {result['processed']}개")
print(f"신규     : {result['new_items']}개")
print(f"업데이트 : {result['updated_items']}개")
print(f"스킵     : {result['skipped']}개")
print(f"사용 API : {result['api_used']}")
if result.get('ocr_processed') or result.get('ocr_skipped'):
    print(f"OCR 처리 : {result.get('ocr_processed', 0)}개 / 실패 {result.get('ocr_skipped', 0)}개")
if result.get('comments_processed'):
    print(f"코멘트   : {result.get('comments_processed', 0)}개")
if result['errors']:
    print("에러:")
    for e in result['errors']:
        print(f"  - {e}")
