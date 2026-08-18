{
    'name': "JANAQ: Personalizar nombre de socio",
    "version": "18.0.1.1.0",
    'author': 'Janaq',
    'description': """
        Separar el nombre completo del socio en los campos nombre, apellido paterno y materno.
    """,
    'depends': [
        'base', 
        'contacts', 
        'l10n_latam_base'
    ],
    'license':'LGPL-3',
    'website': "www.janaq.com",
    'data': [
        'views/partner_views.xml',
    ],
}