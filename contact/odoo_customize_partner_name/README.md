# odoo_customize_partner_name

Separa el nombre completo de un contacto persona (`res.partner` / `res.users`) en tres campos: **Nombres**, **Apellido Paterno** y **Apellido Materno**, manteniendo sincronizado el campo estándar `name` (razón social / nombre completo).

## Qué hace

- Agrega los campos `names`, `fathers_last_name`, `mothers_last_name` a `res.partner` y `res.users`.
- Reemplaza el encabezado del formulario de contacto (y de usuario) para personas físicas: en vez de un único campo "Nombre", muestra los tres campos por separado.
- Recalcula automáticamente `name` = `names + fathers_last_name + mothers_last_name` cada vez que se edita alguno de los tres.
- Sincroniza los datos entre `res.partner` y su `res.users` asociado en ambos sentidos (evita loops de escritura con contexto `skip_partner_sync` / `skip_user_sync`).
- Para contactos tipo Compañía, estos tres campos se limpian automáticamente y se usa `name` como razón social.

## Dependencias

`base`, `contacts`, `l10n_latam_base`.

## Por qué existe

Es requisito de [`company_electronic_invoicing_base`](../../accounting/company_electronic_invoicing_base) (comprobantes electrónicos a personas naturales en Perú suelen requerir apellido paterno/materno por separado), pero es independiente y reutilizable en cualquier instalación de Odoo Community 18 que necesite este desglose de nombre, sin relación con la localización peruana.
