"""Read-only assessment of supplied Google API evidence; makes no API calls."""
def assess(metadata, expected_title, *, drive_evidence=None, scopes=()):
    if not isinstance(metadata,dict) or not metadata.get('spreadsheetId') or metadata.get('properties',{}).get('title')!=expected_title:
        raise ValueError('Spreadsheet identity/title not verified')
    sheets=metadata.get('sheets')
    if not isinstance(sheets,list) or any(not isinstance(s,dict) or not s.get('properties',{}).get('title') for s in sheets):
        raise ValueError('Worksheet metadata incomplete')
    value=(drive_evidence or {}).get('capabilities',{}).get('canEdit')
    if drive_evidence and drive_evidence.get('id')!=metadata['spreadsheetId']:
        raise ValueError('Drive evidence identifies another file')
    return {'read_access':'VERIFIED','worksheets':[s['properties']['title'] for s in sheets],
            'edit_permission':value if type(value) is bool else None,
            'write_scope':'https://www.googleapis.com/auth/spreadsheets' in scopes,
            'write_readback_test':'NOT PERFORMED'}
