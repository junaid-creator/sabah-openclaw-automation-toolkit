"""Source-procedure-derived local content preservation checks; no CMS writes."""
import re

def additive_candidate(original, addition, marker):
    if not addition or not marker or original.count(marker)!=1:raise ValueError('One exact insertion marker and nonempty addition required')
    candidate=original.replace(marker,addition+marker,1)
    verify_addition(original,candidate,addition)
    return candidate

def verify_addition(original,candidate,addition):
    if not addition or candidate.count(addition)!=1 or candidate.replace(addition,'',1)!=original:raise ValueError('Original bytes were not preserved')
    return True

def verify_style_only(original,candidate):
    pattern=re.compile(r'(<style\b[^>]*>)(.*?)(</style\s*>)',re.I|re.S)
    a=list(pattern.finditer(original));b=list(pattern.finditer(candidate))
    if len(a)!=1 or len(b)!=1:raise ValueError('Exactly one embedded style required')
    def mask(text,m):return text[:m.start(2)]+'CSS_PLACEHOLDER'+text[m.end(2):]
    if mask(original,a[0])!=mask(candidate,b[0]):raise ValueError('Non-style content or style attributes changed')
    return True

def verify_protected_fields(before,after,allowed_changes=()):
    changed=[k for k in set(before)|set(after) if k not in allowed_changes and (k not in before or k not in after or before[k]!=after[k])]
    if changed:raise ValueError('Protected fields changed: '+', '.join(sorted(changed)))
    return True

def narrow_markup_equivalent(before,after):
    """Only inter-tag whitespace; not safe where that whitespace is significant."""
    normalize=lambda s:re.sub(r'>\s+<','><',s).strip()
    return normalize(before)==normalize(after)
