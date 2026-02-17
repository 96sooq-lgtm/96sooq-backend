
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.supabase_client import db

locations_data = [
    {
        "name_en": "Muscat Governorate",
        "name_ar": "محافظة مسقط",
        "type": "state",
        "children": [
            {"name_en": "Muscat", "name_ar": "مسقط"},
            {"name_en": "Muttrah", "name_ar": "مطرح"},
            {"name_en": "Bawshar", "name_ar": "بوشر"},
            {"name_en": "Seeb", "name_ar": "السيب"},
            {"name_en": "Al Amarat", "name_ar": "العامرات"},
            {"name_en": "Quriyat", "name_ar": "قريات"}
        ]
    },
    {
        "name_en": "Dhofar Governorate",
        "name_ar": "محافظة ظفار",
        "type": "state",
        "children": [
            {"name_en": "Salalah", "name_ar": "صلالة"},
            {"name_en": "Taqah", "name_ar": "طاقة"},
            {"name_en": "Mirbat", "name_ar": "مرباط"},
            {"name_en": "Rakhyut", "name_ar": "رخيوت"},
            {"name_en": "Thumrait", "name_ar": "ثمريت"},
            {"name_en": "Dalkut", "name_ar": "ضلكوت"},
            {"name_en": "Al Mazyunah", "name_ar": "المزيونة"},
            {"name_en": "Maqshin", "name_ar": "مقشن"},
            {"name_en": "Shalim and the Hallaniyat Islands", "name_ar": "شليم وجزر الحلانيات"},
            {"name_en": "Sadah", "name_ar": "سدح"}
        ]
    },
    {
        "name_en": "Al Dakhiliyah Governorate",
        "name_ar": "محافظة الداخلية",
        "type": "state",
        "children": [
            {"name_en": "Nizwa", "name_ar": "نزوى"},
            {"name_en": "Bahla", "name_ar": "بهلاء"},
            {"name_en": "Manah", "name_ar": "منح"},
            {"name_en": "Al Hamra", "name_ar": "الحمراء"},
            {"name_en": "Adam", "name_ar": "أدم"},
            {"name_en": "Bidbid", "name_ar": "بدبد"},
            {"name_en": "Samail", "name_ar": "سمائل"},
            {"name_en": "Izki", "name_ar": "إزكي"},
            {"name_en": "Jabal Al Akhdar", "name_ar": "الجبل الأخضر"}
        ]
    },
    {
        "name_en": "North Al Batinah Governorate",
        "name_ar": "محافظة شمال الباطنة",
        "type": "state",
        "children": [
            {"name_en": "Sohar", "name_ar": "صحار"},
            {"name_en": "Shinas", "name_ar": "شناص"},
            {"name_en": "Liwa", "name_ar": "لوى"},
            {"name_en": "Saham", "name_ar": "صحم"},
            {"name_en": "Al Khaburah", "name_ar": "الخابورة"},
            {"name_en": "Al Suwaiq", "name_ar": "السويق"}
        ]
    },
    {
        "name_en": "South Al Batinah Governorate",
        "name_ar": "محافظة جنوب الباطنة",
        "type": "state",
        "children": [
            {"name_en": "Rustaq", "name_ar": "الرستاق"},
            {"name_en": "Al Awabi", "name_ar": "العوابي"},
            {"name_en": "Nakhal", "name_ar": "نخل"},
            {"name_en": "Barka", "name_ar": "بركاء"},
            {"name_en": "Wadi Al Maawil", "name_ar": "وادي المعاول"},
            {"name_en": "Al Musannah", "name_ar": "المصنعة"}
        ]
    },
    {
        "name_en": "North Al Sharqiyah Governorate",
        "name_ar": "محافظة شمال الشرقية",
        "type": "state",
        "children": [
            {"name_en": "Ibra", "name_ar": "إبراء"},
            {"name_en": "Al Mudhaibi", "name_ar": "المضيبي"},
            {"name_en": "Bidiyah", "name_ar": "بدية"},
            {"name_en": "Al Qabil", "name_ar": "القابل"},
            {"name_en": "Wadi Bani Khalid", "name_ar": "وادي بني خالد"},
            {"name_en": "Dima Wa Al Taaiyeen", "name_ar": "دماء والطائيين"}
        ]
    },
    {
        "name_en": "South Al Sharqiyah Governorate",
        "name_ar": "محافظة جنوب الشرقية",
        "type": "state",
        "children": [
            {"name_en": "Sur", "name_ar": "صور"},
            {"name_en": "Al Kamil Wa Al Wafi", "name_ar": "الكامل والوافي"},
            {"name_en": "Jalan Bani Bu Ali", "name_ar": "جعلان بني بو علي"},
            {"name_en": "Jalan Bani Bu Hassan", "name_ar": "جعلان بني بو حسن"},
            {"name_en": "Masirah", "name_ar": "مصيرة"}
        ]
    },
    {
        "name_en": "Al Dhahirah Governorate",
        "name_ar": "محافظة الظاهرة",
        "type": "state",
        "children": [
            {"name_en": "Ibri", "name_ar": "عبري"},
            {"name_en": "Yanqul", "name_ar": "ينقل"},
            {"name_en": "Dhank", "name_ar": "ضنك"}
        ]
    },
    {
        "name_en": "Al Buraimi Governorate",
        "name_ar": "محافظة البريمي",
        "type": "state",
        "children": [
            {"name_en": "Al Buraimi", "name_ar": "البريمي"},
            {"name_en": "Mahdah", "name_ar": "محضة"},
            {"name_en": "Al Sunaynah", "name_ar": "السنينة"}
        ]
    },
    {
        "name_en": "Al Wusta Governorate",
        "name_ar": "محافظة الوسطى",
        "type": "state",
        "children": [
            {"name_en": "Haima", "name_ar": "هيماء"},
            {"name_en": "Duqm", "name_ar": "الدقم"},
            {"name_en": "Mahout", "name_ar": "محوت"},
            {"name_en": "Al Jazir", "name_ar": "الجازر"}
        ]
    },
    {
        "name_en": "Musandam Governorate",
        "name_ar": "محافظة مسندم",
        "type": "state",
        "children": [
            {"name_en": "Khasab", "name_ar": "خصب"},
            {"name_en": "Dibba", "name_ar": "دبا"},
            {"name_en": "Bukha", "name_ar": "بخاء"},
            {"name_en": "Madha", "name_ar": "مدحاء"}
        ]
    }
]

def seed_locations():
    print("Seeding locations...")
    
    # Optional: Clear existing locations?
    # db.delete("locations", filters={"is_active": True}) # Risky, better append or check existance
    
    for state in locations_data:
        # Check if state exists
        # Assuming unique by name_en
        existing_state = db.select("locations", filters={"name_en": state["name_en"], "type": "state"})
        
        if existing_state:
            state_id = existing_state[0]["id"]
            print(f"State exists: {state['name_en']}")
        else:
            state_payload = {
                "name_en": state["name_en"],
                "name_ar": state["name_ar"],
                "type": "state",
                "is_active": True
            }
            new_state = db.insert("locations", state_payload)
            if new_state:
                state_id = new_state["id"]
                print(f"Created State: {state['name_en']}")
            else:
                print(f"Failed to create State: {state['name_en']}")
                continue
                
        # Handle children (cities)
        for city in state["children"]:
            existing_city = db.select("locations", filters={
                "name_en": city["name_en"], 
                "type": "city",
                "parent_id": state_id
            })
            
            if not existing_city:
                city_payload = {
                    "name_en": city["name_en"],
                    "name_ar": city["name_ar"],
                    "type": "city",
                    "parent_id": state_id,
                    "is_active": True
                }
                new_city = db.insert("locations", city_payload)
                if new_city:
                    print(f"  Created City: {city['name_en']}")
                else:
                    print(f"  Failed to create City: {city['name_en']}")
            else:
                 print(f"  City exists: {city['name_en']}")

if __name__ == "__main__":
    seed_locations()
