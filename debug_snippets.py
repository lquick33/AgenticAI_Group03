import asyncio
import os
from app.services.storage import get_supabase_client
from app.services.snippet_service import get_snippets_for_material, get_snippet_public_url

MATERIAL_ID = "63831504-97ec-4def-96a2-5051ba7e6f8e"

async def main():
    print(f"Checking snippets for material: {MATERIAL_ID}")
    client = get_supabase_client()
    
    # 1. Get User ID for this material
    try:
        resp = client.table("course_materials").select("user_id").eq("id", MATERIAL_ID).single().execute()
        if not resp.data:
            print("Material not found!")
            return
        user_id = resp.data["user_id"]
        print(f"Found User ID: {user_id}")
    except Exception as e:
        print(f"Error fetching material: {e}")
        return

    # 2. Check Snippets
    try:
        snippets = get_snippets_for_material(MATERIAL_ID, user_id)
        print(f"Found {len(snippets)} snippets.")
        for s in snippets:
            print(f" - Page {s['page_number']}: {s['image_path']}")
            
            # 3. Try URL generation
            try:
                url = get_snippet_public_url(s['image_path'])
                print(f"   -> URL generated: {url[:50]}...")
            except Exception as e:
                print(f"   -> URL generation FAILED: {e}")
                
    except Exception as e:
        print(f"Error fetching snippets: {e}")

if __name__ == "__main__":
    asyncio.run(main())
