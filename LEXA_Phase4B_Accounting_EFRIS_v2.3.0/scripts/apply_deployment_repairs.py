from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

main = ROOT / 'apps/api/app/main.py'
s = main.read_text()
s = s.replace(
    'from .routes import auth, organization, rbac, catalog, inventory, kernel, business_engine\n',
    'from .routes import auth, organization, rbac, catalog, inventory, business_engine\nfrom .kernel import router as kernel_router\n',
)
s = s.replace('app.include_router(kernel.router, prefix="/api/v1")', 'app.include_router(kernel_router, prefix="/api/v1")')
main.write_text(s)

page = ROOT / 'apps/web/app/business-engine/page.tsx'
p = page.read_text().replace('quantity:1,unit_price:txAmount', 'quantity:"1",unit_price:txAmount')
page.write_text(p)

print('Applied LEXA deployment repairs: Render kernel import, Vercel transaction quantity contract.')
