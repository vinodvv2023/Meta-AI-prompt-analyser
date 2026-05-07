import sys
sys.path.insert(0, '.')
from parser import parse_json_file
from classifier import classify_document

docs = parse_json_file('../sample.json')
print(f'Parsed {len(docs)} documents')
for doc in docs:
    cd = classify_document(doc)
    t = cd['type']
    mj = cd['is_midjourney_style']
    vid = cd['has_video']
    label = cd['label'][:60]
    turns = len(cd.get('turns', []))
    print(f'  [{t:15}] MJ={mj} Video={vid} turns={turns}  {label}')
    if cd.get('image_aspects'):
        print(f'    aspects: {cd["image_aspects"]}')
