#!/usr/bin/env bash
# Smoke tests against the Books API through the Kong proxy at :8000
set -u
PROXY="http://localhost:8000/books-api"
fail=0
pass=0

check() {
  local label="$1"; shift
  local expected="$1"; shift
  local body
  body=$(mktemp)
  local code
  code=$(curl -s -o "$body" -w "%{http_code}" "$@")
  if [[ "$code" == "$expected" ]]; then
    echo "✅ $label  [$code]"
    pass=$((pass+1))
  else
    echo "❌ $label  expected=$expected got=$code"
    cat "$body"; echo
    fail=$((fail+1))
  fi
  rm -f "$body"
}

echo "=== Books API via Kong proxy ($PROXY) ==="
check "GET  /health"        200 "$PROXY/health"
check "GET  /books"         200 "$PROXY/books"
check "GET  /books/1"       200 "$PROXY/books/1"
check "GET  /books/999"     404 "$PROXY/books/999"
check "POST /books (good)"  201 -X POST -H 'Content-Type: application/json' -d '{"title":"SRE","author":"Beyer"}' "$PROXY/books"
check "POST /books (bad)"   400 -X POST -H 'Content-Type: application/json' -d '{}' "$PROXY/books"

echo
echo "=== Direct backend ($PROXY -> http://localhost:3000) ==="
check "GET direct /health"  200 "http://localhost:3000/health"

echo
echo "passed=$pass failed=$fail"
exit $fail
