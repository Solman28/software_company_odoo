# pecano_fact

Integración con el PSE (Proveedor de Servicios Electrónicos) **PecanoFact** para el envío de comprobantes de pago electrónicos a SUNAT.

## Qué hace

Sobre el modelo de datos de [`company_electronic_invoicing_base`](../../accounting/company_electronic_invoicing_base), agrega:

- Envío de Factura, Boleta y Nota de Crédito a la API de PecanoFact (`/api/v2/cpe/factura`, `/boleta`, `/notacredito`).
- Envío de Guía de Remisión (remitente y transportista) a PecanoFact (`/api/v2/cpe/guiaremitente`, `/guiatransportista`).
- Consulta de estado del comprobante/guía en PecanoFact, descarga y adjunto de PDF, XML y CDR.
- Botón "Consulta Validez CPE/GRE" y acciones para generar, previsualizar e imprimir el PDF del comprobante.
- Cron de actualización periódica del estado de comprobantes y guías pendientes en PecanoFact.
- Manejo de token de autenticación con PecanoFact (generación y renovación automática).

Se activa por compañía seleccionando **Proveedor = PecanoFact** (`sunat_provider`) en la configuración de la compañía; si no está seleccionado, `account.move` y `guia.remision` usan el flujo por defecto de `company_electronic_invoicing_base`.

## Dependencias

`base`, `web`, `account`, `l10n_pe`, `l10n_latam_base`, [`company_electronic_invoicing_base`](../../accounting/company_electronic_invoicing_base).

## Configuración requerida

En la compañía (una vez seleccionado **Proveedor = PecanoFact**):

| Campo | Descripción |
|---|---|
| `pecano_base_url_prod` / `pecano_base_url_test` | URL base de la API de PecanoFact (producción / pruebas). |
| `pecano_key_comercio_prod` / `pecano_key_comercio_test` | Key de comercio entregada por PecanoFact. |

El RUC de la compañía (`vat`) se usa para generar el token; el ambiente (pruebas/producción) lo determina el campo `electronic_invoicing_type_environment` de `company_electronic_invoicing_base`.

Por moneda (Contabilidad → Configuración → Monedas): código PecanoFact (`jnq_code_pecanofact`, "1" Soles / "2" Dólares) — obligatorio para poder emitir en esa moneda.

Por motivo de traslado / tipo de transporte / documento relacionado: código PecanoFact equivalente (`jnq_code_pecanofact`) en los catálogos correspondientes.

## Notas

- Usa `printjs` (CDN) para la impresión del PDF desde el navegador — requiere conexión a internet del cliente.
- No depende de Odoo Enterprise ni de `l10n_pe_edi`/`l10n_pe_edi_stock`.
