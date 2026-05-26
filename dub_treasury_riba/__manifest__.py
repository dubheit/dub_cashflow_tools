{
    "name": "Treasury - RiBa Credit Line",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Lega le configurazioni Ri.Ba. a un castelletto (linea di credito): "
               "l'utilizzo SBF è calcolato dagli effetti presentati e il residuo/"
               "scadenza del castelletto sono mostrati in fase di emissione.",
    "author": "Dubhe S.r.l.",
    "website": "https://www.dubhe.it",
    "license": "AGPL-3",
    "depends": [
        "l10n_it_riba_oca",
        "dub_treasury_base",
    ],
    "data": [
        "views/riba_configuration_views.xml",
        "views/riba_issue_views.xml",
    ],
    "installable": True,
}
