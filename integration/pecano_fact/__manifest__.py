{
    'name': "JANAQ: Integracion con PSE Pecano Fact",
    "version": "18.0.1.1.0",
    'author': 'Janaq',
    'description': """
        Integración de comprobantes de pago electronicos con PSE Pecano Fact.
    """,
    'depends': [
        'base',
        'web',
        'account',
        'company_electronic_invoicing_base',
        'l10n_pe',
        'l10n_latam_base'
    ],
    'license':'LGPL-3',
    'website': "www.janaq.com",
    'data': [
        'views/company/company_views.xml',
        'views/company/res_currency_views.xml',
        'views/account/view_acc_log_status.xml',
        'views/account/view_account_move.xml',
        'views/guia_remision/guia_remision_electronica.xml',
        'views/catalogs/sunat_catalogs.xml',
        'data/res_currency.xml',
        'data/l10n.xml',
        'data/transfer_reason.xml',
        'data/transport_type.xml',
        'data/related_document.xml',
        'data/detraction.xml',
        'data/report.xml',
        'cron/validez_comprobante_cron.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'pecano_fact/static/**/*',
            'https://printjs-4de6.kxcdn.com/print.min.js',
            'https://printjs-4de6.kxcdn.com/print.min.css'
        ],
    }
}