# Yol Haritası

> Not: `[x]` işaretli maddeler kodda uygulandı, ancak bu ortamda çalıştırılamadı.
> Kendi bilgisayarında `uv run pytest` ve uygulamayı çalıştırarak doğrula.

## v0

- [x] 1. In-memory CRUD (temel endpoint'ler)
- [x] 2. SQLAlchemy ile veritabanı (SQLite)
- [x] 3. Kullanıcılar, argon2 ile parola hash'leme ve JWT ile kimlik doğrulama
- [x] 4. Docker + PostgreSQL (Dockerfile, docker-compose; Alembic migration'ları)
- [ ] 4b. PostgreSQL üzerinde elle doğrulama (sahibi yapacak)
- [x] 5. Testler (pytest, ownership, validation, 401 senaryoları)
- [x] 6. Basit web arayüzü (Jinja2 + vanilla JS)
- [x] 7. CI (GitHub Actions: ruff + pytest) ve README
- [ ] 8. Deploy (bir bulut servisine yayınlama)

## v1

- [ ] CV yükleme (PDF/DOCX)
- [ ] Celery + Redis ile arka plan işleri
- [ ] LLM ile ilan/CV'den beceri çıkarma
- [ ] Embedding + pgvector ile ilan-CV eşleştirme (uyum skoru)
