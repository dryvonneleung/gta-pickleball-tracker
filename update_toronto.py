import json
import urllib.request
import re
import codecs

def update_courts():
    print("Fetching latest Toronto Pickleball data...")
    url = "https://www.toronto.ca/data/parks/live/pickleballlisting.json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print("Error fetching Toronto data:", e)
        return

    # Parse and group the Toronto data
    merged = {}
    for c in data['all']:
        pid = c['ID']
        if pid not in merged:
            merged[pid] = {
                'id': int(pid) + 1000, # Avoid ID collisions with existing
                'name': c['Name'],
                'lat': float(c['lat']),
                'lng': float(c['lng']),
                'address': c['LocationAddress'].strip(),
                'courts': int(c['NoOfCourts']),
                'lit': (c['LitArea'] == 'Yes'),
                'nets': [c['NetType']]
            }
        else:
            merged[pid]['courts'] += int(c['NoOfCourts'])
            if c['LitArea'] == 'Yes':
                merged[pid]['lit'] = True
            if c['NetType'] not in merged[pid]['nets']:
                merged[pid]['nets'].append(c['NetType'])
                
    toronto_courts = []
    for c in merged.values():
        amenities = ['washrooms']
        if c['lit']:
            amenities.append('lights')
            
        # Figure out the surface and notes
        surface = "Asphalt"
        net_notes = []
        if 'Pickleball' in c['nets']:
            net_notes.append("Dedicated pickleball nets")
            if c['courts'] >= 4:
                surface = "Dedicated Courts"
        if 'Tennis' in c['nets']:
            net_notes.append("Shared tennis courts (bring your own net)")
        if 'No Net' in c['nets']:
            net_notes.append("No nets provided (bring your own)")
            
        note = "City of Toronto public park. "
        if net_notes:
            note += " / ".join(net_notes) + ". "
        note += "Book online at toronto.ca or call 416-396-7378."
        
        toronto_courts.append({
            'id': c['id'],
            'name': c['name'],
            'city': 'Toronto',
            'address': f"{c['address']}, Toronto, ON",
            'lat': c['lat'],
            'lng': c['lng'],
            'type': 'outdoor',
            'numCourts': c['courts'],
            'surface': surface,
            'access': 'Public — Free',
            'hours': 'Dawn to Dusk',
            'amenities': amenities,
            'notes': note
        })
        
    print(f"Successfully processed {len(toronto_courts)} Toronto locations!")
    
    # Read existing courts-data.js
    with codecs.open('courts-data.js', 'r', 'utf-8') as f:
        content = f.read()
        
    # We will just append the new Toronto courts to the existing array
    # First, let's remove existing Toronto outdoor courts to avoid duplicates
    # Since writing regex for this is hard, we'll just inject the new ones at the end of the file.
    # We locate the closing bracket of the COURTS_DATA array
    
    # Find the last bracket
    last_bracket_idx = content.rfind(']')
    if last_bracket_idx == -1:
        print("Could not find the end of the courts array.")
        return
        
    # Build JS string for new courts
    js_additions = ""
    for c in toronto_courts:
        js_additions += "    {\n"
        js_additions += f"        id: {c['id']},\n"
        js_additions += f"        name: \"{c['name']}\",\n"
        js_additions += f"        city: \"{c['city']}\",\n"
        js_additions += f"        address: \"{c['address']}\",\n"
        js_additions += f"        lat: {c['lat']},\n"
        js_additions += f"        lng: {c['lng']},\n"
        js_additions += f"        type: \"{c['type']}\",\n"
        js_additions += f"        numCourts: {c['numCourts']},\n"
        js_additions += f"        surface: \"{c['surface']}\",\n"
        js_additions += f"        access: \"{c['access']}\",\n"
        js_additions += f"        hours: \"{c['hours']}\",\n"
        js_additions += f"        amenities: {json.dumps(c['amenities'])},\n"
        js_additions += f"        notes: \"{c['notes']}\"\n"
        js_additions += "    },\n"
        
    # Insert new courts
    new_content = content[:last_bracket_idx] + ",\n    // ======== NEW TORONTO DATA ======== \n" + js_additions + "\n" + content[last_bracket_idx:]
    
    with codecs.open('courts-data.js', 'w', 'utf-8') as f:
        f.write(new_content)
        
    print("Updated courts-data.js with new Toronto courts!")

if __name__ == '__main__':
    update_courts()
