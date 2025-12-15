# api.py (samenvatting toegevoegd)
# LET OP: functionele logica ongewijzigd, alleen kernsamenvatting toegevoegd in PDF-opbouw

# ... bestaande imports en code blijven gelijk ...

def build_kernsamenvatting(context):
    return (
        f"Deze locatie ligt in het {context.get('fgr')}, "
        f"op een {context.get('geomorfologie')} met een {context.get('bodem')} bodem. "
        f"De grondwaterstand ({context.get('gt')}) en hoogteligging "
        f"({context.get('ahn')} m NAP) zijn bepalend voor de beplantingskeuze."
    )

# In PDF-sectie:
# voeg vóór 'Toelichting op locatiecontext' een blok 'Kernsamenvatting locatie' toe
