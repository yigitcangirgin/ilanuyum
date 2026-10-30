# İlanUyum Öğrenme Rehberi (Django bilen biri için FastAPI)

## 1. Windows'ta çalıştırma

PowerShell'de proje klasöründe:

```powershell
uv sync                              # bağımlılıkları kurar (.venv oluşturur)
uv run alembic upgrade head          # tabloları oluşturur (Django'daki migrate)
uv run uvicorn app.main:app --reload # sunucu, http://127.0.0.1:8000
uv run pytest                        # testler
```

Tarayıcıda `/docs` (Swagger) ve `/` (arayüz) adreslerini aç. İsteğe bağlı: `.env.example` dosyasını
`.env` olarak kopyala ve `SECRET_KEY` değerini değiştir.

## 2. Dosyalar ne iş yapar?

- `app/main.py`: FastAPI nesnesini kurar, router'ları ve `/static` klasörünü bağlar.
- `app/config.py`: Ortam değişkenlerinden ayarları okur (Django'daki settings.py'ın hafif hali).
- `app/database.py`: Veritabanı bağlantısı (`engine`), oturum (`SessionLocal`) ve `get_db`.
- `app/models.py`: Tabloları temsil eden SQLAlchemy sınıfları (`User`, `Application`).
- `app/schemas.py`: Pydantic şemaları; gelen isteği doğrular, giden cevabı şekillendirir.
- `app/security.py`: Parola hash'leme (argon2) ve JWT üretme/çözme.
- `app/deps.py`: `get_current_user` gibi tekrar kullanılan bağımlılıklar.
- `app/routers/auth.py`: Kayıt, giriş, `/auth/me`.
- `app/routers/applications.py`: Başvuru CRUD'u ve istatistikler.
- `app/routers/health.py`: `/health` kontrolü.
- `app/routers/pages.py`: HTML sayfalarını Jinja2 ile sunar.
- `app/templates/`, `app/static/`: Sayfa şablonları, CSS ve `app.js` (API'ye fetch ile bağlanır).
- `alembic/`: Veritabanı şema değişikliklerinin (migration) geçmişi.
- `tests/`: pytest testleri; her test temiz bir bellek içi SQLite kullanır.
- `Dockerfile`, `docker-compose.yml`: Uygulama + PostgreSQL'i konteynerde çalıştırır.

## 3. İstek akışı: kayıt -> giriş -> token -> korumalı çağrı

1. **Kayıt:** Tarayıcı `POST /auth/register` ile JSON `{email, password}` yollar. Pydantic
   (`UserCreate`) e-posta biçimini ve parola uzunluğunu doğrular. `register` fonksiyonu e-postayı
   küçük harfe çevirir, aynısı varsa 409 döner, yoksa parolayı argon2 ile hash'leyip kaydeder.
2. **Giriş:** `POST /auth/login` form verisi (`username`, `password`) alır (OAuth2 standardı).
   Hash doğrulanırsa `create_access_token` kullanıcı id'sini `sub` alanına koyup imzalı bir JWT üretir.
3. **Token saklama:** `app.js` token'ı `localStorage["ilanuyum_token"]` içine yazar ve `/app`'e yönlendirir.
4. **Korumalı çağrı:** `GET /applications` isteğine `Authorization: Bearer <token>` başlığı eklenir.
   `oauth2_scheme` başlığı okur, `get_current_user` token'ı çözer, kullanıcıyı DB'den yükler.
   Başarısızsa 401 döner ve arayüz token'ı silip `/` sayfasına döner.
5. **Sahiplik:** Sorgu `owner_id == user.id` ile filtrelenir; başkasının kaydı 404 verir.

## 4. Sözlük

- **Dependency injection:** Bir fonksiyonun ihtiyaç duyduğu şeyi (DB oturumu, kullanıcı) kendisi
  üretmek yerine `Depends(...)` ile FastAPI'nin vermesi. Test sırasında `dependency_overrides` ile değiştirilebilir.
- **ORM:** Tabloları Python sınıflarına, satırları nesnelere çeviren katman (Django ORM'in SQLAlchemy karşılığı).
- **Migration:** Şema değişikliğinin versiyonlanmış betiği. Alembic bunu yönetir.
- **JWT:** İçinde bilgi (`sub`, `exp`) taşıyan, sunucu anahtarıyla imzalı token. İmza sayesinde değiştirilemez.
- **Hash vs şifreleme:** Hash tek yönlüdür (parolayı geri çıkaramazsın, sadece doğrularsın); şifreleme anahtarla geri açılır.
- **Pydantic şeması vs SQLAlchemy modeli:** Model veritabanı tablosunu, şema API'nin giriş/çıkış sözleşmesini tanımlar.
  Ayrı tutulur ki `hashed_password` gibi alanlar yanlışlıkla dışarı sızmasın.

## 5. Mülakat soruları

1. **FastAPI neden hızlı geliştirme sağlar?** Tip ipuçlarından doğrulama ve otomatik `/docs` üretir.
2. **Dependency injection nerede kullanıldı?** `DbSession` ve `CurrentUser` (`app/deps.py`).
3. **Neden başkasının kaydı için 403 değil 404?** Kaydın var olduğu bilgisi sızmasın diye (`_get_owned`).
4. **`/stats` neden `/{application_id}` öncesinde?** Yoksa "stats" id olarak yorumlanıp 422 verir.
5. **PUT ile PATCH farkı?** PUT tüm alanları değiştirir (`ApplicationCreate`); PATCH sadece gönderilenleri (`exclude_unset=True`).
6. **Neden create_all değil Alembic?** Şema değişiklikleri versiyonlanır ve üretimde güvenle uygulanır.
7. **Parolalar nasıl saklanıyor?** argon2 ile hash'lenir; düz metin asla saklanmaz.
8. **JWT'nin riski nedir?** Çalınırsa süresi bitene kadar geçerlidir; bu yüzden süre kısa tutulur ve `SECRET_KEY` gizli kalmalıdır.
9. **Sync mi async mı, neden?** Önce sync: daha basit. FastAPI sync endpoint'leri thread havuzunda çalıştırır.
10. **Testler DB'yi nasıl izole eder?** Bellek içi SQLite + `get_db` override; her testte şema sıfırlanır.
11. **SQL injection'dan nasıl korunuyoruz?** SQLAlchemy parametreli sorgu kullanır, string birleştirme yoktur.
12. **Arayüzde XSS'e karşı ne yapıldı?** Kullanıcı verisi `textContent` ile yazılır, `innerHTML` kullanılmaz.

## 6. Alıştırmalar

1. `GET /applications` için `search` sorgu parametresi ekle (company veya position içinde `ilike` ile ara) ve test yaz.
2. `Application`'a `deadline` (Date, nullable) sütunu ekle: modeli, şemaları ve yeni bir Alembic migration'ı (`uv run alembic revision --autogenerate -m "add deadline"`) yaz.
3. `/applications/stats` cevabına son 30 günde eklenen başvuru sayısını ekle.
4. Dashboard tablosuna şirket adına göre sıralama butonu ekle (`sort` parametresi + `app.js`).
5. `DELETE /auth/me` ile hesabı sil; ilişkili başvuruların cascade ile silindiğini testle doğrula.
