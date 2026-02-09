# Kontrakt – EXO push (webb/admin)

Detta kontrakt beskriver hur EXO-push styrs från adminpanelen och hur den ska skyddas.

## Roll

- Webben kan:
  - bygga payload från DB (preview/dry-run)
  - göra push till EXO om konfig finns

- Webben ska inte behöva kunna logga in mot Arrigo (se Arrigo-kontrakt).

## Konfig

Miljövariabler:
- `EXO_URL` – base URL till EXO endpoint
- `EXO_TOKEN` – bearer token

Om `EXO_URL`/`EXO_TOKEN` saknas:
- UI ska visa tydligt att push inte är aktivt
- preview/dry-run ska fortfarande fungera

## Skydd (admin)

Admin-sidor och API-endpoints som kan trigga push bör kunna skyddas med Basic Auth:
- `SMARTWEB_ADMIN_USER`
- `SMARTWEB_ADMIN_PASS`

Krav:
- Om user/pass inte är satta ska sidan fortfarande fungera (skydd av).
- Om user/pass är satta ska endpoints kräva Basic Auth.

## Acceptanskriterier

- Det går att köra preview/dry-run utan EXO.
- Push görs bara när EXO-konfig är satt.
- (Valfritt) Basic Auth går att slå på utan att bryta annat.
