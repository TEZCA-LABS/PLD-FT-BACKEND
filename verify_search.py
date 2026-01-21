import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.session import engine 
from app.models.sanction import Sanction
from app.services.xml_handler import parse_un_sanctions_xml

# XML Snippet to insert if DB is empty (from User's prompt)
SAMPLE_XML = """<CONSOLIDATED_LIST xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://www.un.org/sc/resources/sc-sanctions.xsd" dateGenerated="2026-01-20T00:00:01.474Z">
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
</INDIVIDUAL>
</INDIVIDUALS>
</CONSOLIDATED_LIST>"""

async def run_search_test():
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 1. Check if we have data
        result = await session.execute(select(Sanction).filter(Sanction.entity_name.ilike("%ERIC BADEGE%")))
        found_sanction = result.scalars().first()
        
        if not found_sanction:
            print("\n[INFO] 'ERIC BADEGE' not found initially. Installing sample data...")
            
            # Parse and Insert
            parsed_items = parse_un_sanctions_xml(SAMPLE_XML.encode('utf-8'))
            for item in parsed_items:
                # Check for duplicate before inserting
                existing = await session.execute(select(Sanction).filter(Sanction.data_id == item['data_id']))
                if not existing.scalars().first():
                    new_sanction = Sanction(**item)
                    session.add(new_sanction)
            
            await session.commit()
            print("[INFO] Sample data inserted.")
            
            # Search again
            result = await session.execute(select(Sanction).filter(Sanction.entity_name.ilike("%ERIC BADEGE%")))
            found_sanction = result.scalars().first()

        if found_sanction:
            print("\n" + "="*50)
            print(f"✅ MATCH FOUND IN PLD/FT SANCTIONS LIST")
            print("="*50)
            print(f"Name: {found_sanction.entity_name}")
            print(f"List Type: {found_sanction.un_list_type}")
            print(f"Reference: {found_sanction.reference_number}")
            print(f"Nationality: {found_sanction.nationality}")
            print(f"Remarks: {found_sanction.remarks}")
            print("="*50 + "\n")
        else:
            print("❌ No match found after insertion attempt.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_search_test())
