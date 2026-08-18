# company_electronic_invoicing_base

Motor base de facturación electrónica para Perú (SUNAT), compatible con **Odoo 18 Community** (no requiere Odoo Enterprise).

## Qué hace

- Genera y controla el ciclo de vida de Factura, Boleta, Nota de Crédito y Nota de Débito electrónica (series, correlativos, validaciones SUNAT antes de confirmar el comprobante).
- Guía de Remisión Electrónica (remitente y transportista) como documento propio (`guia.remision`), con validaciones de datos de partida/llegada, transporte público/privado, vehículos y conductores.
- Comunicación de baja / anulación de comprobantes.
- Retenciones y detracciones (registro, cálculo de montos, cuenta bancaria de detracción).
- Consulta de validez de comprobante ante SUNAT (cron + acción manual).
- Catálogos SUNAT editables desde Odoo (Catálogo 51 tipo de operación, 53 cargos/descuentos, 54 detracciones, 59 medios de pago, motivo de traslado, tipo de transporte, documento relacionado).

Este módulo **no envía comprobantes a SUNAT por sí mismo** (no incluye un OSE/PSE) — provee el modelo de datos, las validaciones y la UI. El envío real lo agrega un módulo de integración con un proveedor, como [`pecano_fact`](../../integration/pecano_fact).

## Nota sobre compatibilidad con Community

La versión original de este módulo (desarrollado por JANAQ para AMPCO) dependía de `l10n_pe_edi` y `l10n_pe_edi_stock`, que son módulos de **Odoo Enterprise**. Para poder instalarse en Community 18, esos campos y modelos se reimplementaron como propios en `models/compat/` (mismo nombre técnico de campo, para no romper la lógica de negocio ya escrita):

- Modelo `l10n_pe_edi.vehicle` (antes provisto por Enterprise).
- Campos en `res.partner`, `res.company`, `account.tax`, `account.tax.group`, `stock.picking`, `stock.picking.type`, `account.move` / `account.move.reversal`.
- Modelo `sunat.product.code` (código SUNAT de producto, usado solo en comprobantes de exportación).

Validado con una instalación real sobre Odoo 18 Community (sin Enterprise).

## Dependencias

`base`, `stock`, `account`, `purchase`, `product`, `sale_stock`, `l10n_pe`, `l10n_latam_base`, `l10n_latam_invoice_document`, [`odoo_customize_partner_name`](../../contact/odoo_customize_partner_name).

## Configuración mínima antes de emitir comprobantes

En la compañía (Contabilidad → Configuración → Compañías):
- **Tipo de envío** (`electronic_invoicing_type_environment`): Pruebas o Producción.
- **Código de establecimiento SUNAT** (`l10n_pe_edi_address_type_code`, 4 dígitos).
- Datos del partner de la compañía: RUC, tipo de documento (RUC), Ubigeo, dirección, razón social.

En cada Diario de venta con `electronic_invoice = True`:
- **Tipo de Documento** (`invoice_type_code`): 01 Factura, 03 Boleta, 07 Nota de crédito, 08 Nota de débito, 09/31 Guía de Remisión.
- Serie (`code`) siguiendo el patrón por tipo de documento (F/B/T/V/R/P según catálogo SUNAT).

Por producto: código SUNAT de unidad de medida (`uom.uom.l10n_pe_edi_measure_unit_code`) y, si aplica, código de detracción.

## Grupos de seguridad

- `res_groups_anulacion_buttons`: puede dar de baja/anular comprobantes.
- `group_validate_cpe_sale_sunat`: puede consultar validez de comprobantes de venta.
- `group_user_sunat_send_out_date`: puede emitir comprobantes fuera del plazo permitido.
