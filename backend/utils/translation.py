import re
from deep_translator import GoogleTranslator

def is_arabic(text: str) -> bool:
    """
    Check if the text contains Arabic characters.
    """
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+')
    return bool(arabic_pattern.search(text))

def translate_text(text: str) -> dict:
    """
    Detect language and translate.
    Returns a dictionary with 'name_en' and 'name_ar'.
    """
    translator_to_en = GoogleTranslator(source='auto', target='en')
    translator_to_ar = GoogleTranslator(source='auto', target='ar')

    if is_arabic(text):
        name_ar = text
        try:
            name_en = translator_to_en.translate(text)
        except Exception:
            # Fallback if translation fails
            name_en = text
    else:
        name_en = text
        try:
            name_ar = translator_to_ar.translate(text)
        except Exception:
            # Fallback if translation fails
            name_ar = text
            
    return {
        "name_en": name_en,
        "name_ar": name_ar
    }
