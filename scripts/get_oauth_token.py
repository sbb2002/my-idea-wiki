"""
Google OAuth Refresh Token 최초 발급 스크립트.

한 번만 실행하면 됩니다. 발급된 Refresh Token을 .env와 Render 환경변수에 저장하면
이후 자동으로 갱신되며 재인증이 필요 없습니다.

사전 준비 (GCP Console에서):
  1. https://console.cloud.google.com 접속
  2. APIs & Services → OAuth 동의 화면
     - User Type: 외부(External)
     - 앱 이름, 이메일 입력 후 저장
     - 테스트 사용자에 본인 Gmail 추가
  3. APIs & Services → 사용자 인증 정보
     - + 사용자 인증 정보 만들기 → OAuth 클라이언트 ID
     - 애플리케이션 유형: 데스크톱 앱
     - 생성 후 클라이언트 ID, 클라이언트 보안 비밀 복사

사용법:
  python scripts/get_oauth_token.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ google-auth-oauthlib이 설치되지 않았습니다.")
    print("   pip install google-auth-oauthlib 실행 후 재시도하세요.")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main():
    print("=" * 55)
    print("  Google OAuth Refresh Token 발급")
    print("=" * 55)
    print("\nGCP Console에서 OAuth 클라이언트 ID를 먼저 생성하세요.")
    print("(스크립트 상단 docstring 참고)\n")

    client_id = input("클라이언트 ID를 입력하세요: ").strip()
    client_secret = input("클라이언트 보안 비밀을 입력하세요: ").strip()

    if not client_id or not client_secret:
        print("❌ 클라이언트 ID와 보안 비밀을 모두 입력해야 합니다.")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    print("\n브라우저가 열립니다. 구글 계정으로 로그인 후 권한을 허용하세요.")
    print("(브라우저가 자동으로 열리지 않으면 출력되는 URL을 직접 복사해서 여세요)\n")

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0, open_browser=True)

    print("\n" + "=" * 55)
    print("  ✅ 토큰 발급 완료!")
    print("=" * 55)
    print("\n아래 값을 .env 파일과 Render 환경변수에 추가하세요:\n")
    print(f"  GOOGLE_OAUTH_CLIENT_ID={client_id}")
    print(f"  GOOGLE_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"  GOOGLE_REFRESH_TOKEN={credentials.refresh_token}")
    print("\n⚠️  Refresh Token은 비밀번호처럼 취급하세요. 절대 공개하지 마세요.")
    print("\n설정 완료 후 setup_drive.py를 실행해서 wikis 폴더를 생성하세요:")
    print("  python scripts/setup_drive.py")

    # 로컬 .env 자동 업데이트 여부 확인
    update = input("\n.env 파일에 자동으로 추가할까요? (y/N): ").strip().lower()
    if update == "y":
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                env_content = f.read()

            additions = []
            if "GOOGLE_OAUTH_CLIENT_ID" not in env_content:
                additions.append(f"GOOGLE_OAUTH_CLIENT_ID={client_id}")
            if "GOOGLE_OAUTH_CLIENT_SECRET" not in env_content:
                additions.append(f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}")
            if "GOOGLE_REFRESH_TOKEN" not in env_content:
                additions.append(f"GOOGLE_REFRESH_TOKEN={credentials.refresh_token}")

            if additions:
                with open(env_path, "a", encoding="utf-8") as f:
                    f.write("\n# Google OAuth\n")
                    f.write("\n".join(additions) + "\n")
                print(f"✅ .env 파일에 {len(additions)}개 항목 추가됐습니다.")
            else:
                print("이미 .env에 모든 항목이 있습니다.")
        else:
            print("❌ .env 파일을 찾을 수 없습니다. 수동으로 추가해주세요.")


if __name__ == "__main__":
    main()
