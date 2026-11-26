"""Compatibility CLI. No credentials or network calls when imported."""
from check_pages import check

if __name__=='__main__':raise SystemExit(check())
