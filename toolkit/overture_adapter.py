"""Source-derived Overture CLI adapter and construction-prospect conversion.
The upstream downloader is not vendored; downloading is explicitly opt-in.
"""
import json,re,subprocess
from pathlib import Path
from .lead_qualification import qualify_overture,normalized,domain

def convert_feature(feature,area):
    p=feature.get('properties') or {};name=(p.get('names') or {}).get('primary') or ''
    category=(p.get('taxonomy') or {}).get('primary') or ''
    if category not in {'contractor','building_or_construction_service','hvac_service','property_management'} or not re.search(r'contract|construction|maintenance|facilit|fit.?out|mep|electro.?mechanical|hvac',name,re.I):return None
    coords=(feature.get('geometry') or {}).get('coordinates')
    if (feature.get('geometry') or {}).get('type')!='Point' or not isinstance(coords,list) or len(coords)<2:return None
    address=(p.get('addresses') or [{}])[0]
    return {'id':feature.get('id'),'name':name,'category':category,'phone':(p.get('phones') or [''])[0],'website':(p.get('websites') or [''])[0],'email':(p.get('emails') or [''])[0],'locality':address.get('locality') or '','address':address.get('freeform') or '','area':area,'longitude':coords[0],'latitude':coords[1]}

def download(executable,bbox,output,*,allow_download=False,runner=subprocess.run):
    if not allow_download:raise RuntimeError('Overture download disabled')
    if len(bbox)!=4 or not (-180<=bbox[0]<bbox[2]<=180 and -90<=bbox[1]<bbox[3]<=90):raise ValueError('Valid west,south,east,north bounding box required')
    binary=Path(executable)
    if not binary.is_absolute() or not binary.is_file():raise ValueError('Explicit installed Overture executable required')
    output=Path(output)
    if output.exists():raise ValueError('Use a fresh output path')
    command=[str(binary),'download','--bbox='+','.join(map(str,bbox)),'-f','geojson','--type=place','-o',str(output)]
    result=runner(command,text=True,capture_output=True,timeout=180,check=False)
    if result.returncode:raise RuntimeError('Overture downloader failed; no retry performed')
    return json.loads(output.read_text())

def qualify_features(geojson,profile,today):
    rows=[];seen=[set() for _ in range(4)]
    for feature in geojson.get('features',[]):
        item=convert_feature(feature,profile['geographic_targets']['area'])
        row=qualify_overture(item,profile,today) if item else None
        if row is None:continue
        keys=(row[0],domain(row[5]),normalized(row[6]),normalized(row[1]))
        if any(k and k in bucket for k,bucket in zip(keys,seen)):continue
        rows.append(row)
        for k,bucket in zip(keys,seen):
            if k:bucket.add(k)
    return rows
