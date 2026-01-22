from app.services.xml_handler import parse_un_sanctions_xml
import json

xml_content = """<CONSOLIDATED_LIST xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://www.un.org/sc/resources/sc-sanctions.xsd" dateGenerated="2026-01-20T00:00:01.474Z">
<INDIVIDUALS>
<INDIVIDUAL>
<DATAID>6907993</DATAID>
<VERSIONNUM>1</VERSIONNUM>
<FIRST_NAME>ERIC</FIRST_NAME>
<SECOND_NAME>BADEGE</SECOND_NAME>
<UN_LIST_TYPE>DRC</UN_LIST_TYPE>
<REFERENCE_NUMBER>CDi.001</REFERENCE_NUMBER>
<LISTED_ON>2012-12-31</LISTED_ON>
<GENDER>Masculino</GENDER>
<COMMENTS1>la notificación especial de la INTERPOL y el Consejo de Seguridad de las Naciones Unidas en el sitio web:https://www.interpol.int/en/How-we-work/Notices/View-UN-Notices-Individuals</COMMENTS1>
<NATIONALITY>
<VALUE>Democratic Republic of the Congo</VALUE>
</NATIONALITY>
<LIST_TYPE>
<VALUE>UN List</VALUE>
</LIST_TYPE>
<LAST_DAY_UPDATED>
<VALUE>2016-10-13</VALUE>
</LAST_DAY_UPDATED>
<INDIVIDUAL_ALIAS>
<QUALITY/>
<ALIAS_NAME/>
</INDIVIDUAL_ALIAS>
<INDIVIDUAL_ADDRESS>
<COUNTRY>Rwanda</COUNTRY>
<NOTE>Huyó en marzo de 2013 a Rwanda, donde aún residía a principios de 2016.</NOTE>
</INDIVIDUAL_ADDRESS>
<INDIVIDUAL_DATE_OF_BIRTH>
<TYPE_OF_DATE>EXACT</TYPE_OF_DATE>
<YEAR>1971</YEAR>
</INDIVIDUAL_DATE_OF_BIRTH>
<INDIVIDUAL_PLACE_OF_BIRTH>
<COUNTRY/>
</INDIVIDUAL_PLACE_OF_BIRTH>
<INDIVIDUAL_DOCUMENT/>
<SORT_KEY/>
<SORT_KEY_LAST_MOD/>
</INDIVIDUAL>
</INDIVIDUALS>
</CONSOLIDATED_LIST>"""

try:
    result = parse_un_sanctions_xml(xml_content.encode('utf-8'))
    print(json.dumps(result, indent=2, default=str))
except Exception as e:
    print(f"Error: {e}")
