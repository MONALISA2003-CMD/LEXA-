# LEXA Live Integration

The canonical LEXA application uses the Neon project `LEXA`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`.

The API is served by Render and the web application is served by Vercel/Next.js. The browser communicates with the API through the same-origin Next.js proxy so refresh cookies remain HttpOnly.

Authentication no longer uses an open-development bootstrap or `sessionStorage` bearer persistence. Browser access tokens live in memory; refresh credentials are rotated through the HttpOnly refresh cookie.

The API runtime uses the restricted PostgreSQL role `lexa_app` and applies that role per database transaction so PgBouncer transaction pooling does not weaken the RLS boundary.

The source repository must contain every migration present on the canonical Neon database. The current production package includes migrations through `022_phase6a_brain_foundation`.
