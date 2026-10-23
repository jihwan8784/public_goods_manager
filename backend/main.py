"""Vercel / uvicorn 진입점. 실제 코드는 pgm 패키지에 있다."""

from pgm.app import create_app

app = create_app()
