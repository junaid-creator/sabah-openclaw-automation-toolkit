"""Shared language contract for job creation, local previews and draft preparation."""
from __future__ import annotations
import re

MODES = ('ENGLISH', 'ARABIC', 'BILINGUAL')
AR = re.compile(r'[\u0620-\u064a\u066e-\u06d3\u06fa-\u06ff]')
EN = re.compile(r'[A-Za-z]')

def select_language(explicit=None, request_text=''):
    value = str(explicit or '').strip().upper()
    aliases = {'EN':'ENGLISH','ENGLISH':'ENGLISH','AR':'ARABIC','ARABIC':'ARABIC',
               'BOTH':'BILINGUAL','BILINGUAL':'BILINGUAL','ENGLISH AND ARABIC':'BILINGUAL',
               'عربي':'ARABIC','العربية':'ARABIC','عربية':'ARABIC','ثنائي اللغة':'BILINGUAL'}
    if value:
        if value not in aliases: raise ValueError('Language must be ENGLISH, ARABIC or BILINGUAL')
        return aliases[value]
    text = str(request_text or '').lower()
    both = r'\bbilingual\b|\bboth\s+languages\b|\b(?:english\s*(?:and|&|\+|/)\s*arabic|arabic\s*(?:and|&|\+|/)\s*english)\b|ثنائي(?:ة)?\s+اللغة|باللغتين|(?:العربية|العربي|عربي)\s*و\s*(?:الإنجليزية|الانجليزية|الانجليزي|إنجليزي)|(?:الإنجليزية|الانجليزية|الانجليزي|إنجليزي)\s*و\s*(?:العربية|العربي|عربي)'
    if re.search(both,text): return 'BILINGUAL'
    if re.search(r'\benglish(?:[- ]only)?\b|بالإنجليزية|بالانجليزية|بالانجليزي',text): return 'ENGLISH'
    if re.search(r'\bin\s+arabic\b|\barabic[- ]only\b|\barabic\s+(?:(?:social|media)\s+){0,2}(?:post|poster|caption|headlines?|content)\b|\b(?:language|mode)\s*[:=]?\s*arabic\b|^arabic$|بالعربية|بالعربي|(?:منشور|بوست)\s+(?:عربي|باللغة العربية)|باللغة\s+العربية',text): return 'ARABIC'
    return 'ENGLISH'

def select_text(en, ar, language):
    if language not in MODES: raise ValueError("Invalid language")
    return en if language == 'ENGLISH' else ar if language == 'ARABIC' else en+'\n'+ar

def validate_copy(text, language, field='text'):
    if language not in MODES: raise ValueError("Invalid language")
    # Identity strings, URLs, handles and product numbers do not determine copy language.
    cleaned = re.sub(r'https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+|@\w+', '', str(text), flags=re.I)
    has_ar,has_en=bool(AR.search(cleaned)),bool(EN.search(cleaned))
    if language=='ENGLISH' and (has_ar or not has_en):
        raise ValueError(field+' must contain English-only campaign copy')
    if language=='ARABIC' and (has_en or not has_ar):
        raise ValueError(field+' must contain Arabic campaign copy')
    if language=='BILINGUAL' and not (has_ar and has_en):
        raise ValueError(field+' must contain both English and Arabic campaign copy')
    return str(text)
