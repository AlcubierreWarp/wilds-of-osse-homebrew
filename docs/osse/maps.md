# Maps (Atlas)

`Atlas/` in the vault holds the Leaflet maps: `World map.md` and one `<Place> map.md` per map image from Notion's Locations database, with their images. The build ignores the folder. A place with a map has `map: "[[<Place> map]]"`.

- **Bounds.** Each map block sets `bounds: [[-H/2, -W/2], [H/2, W/2]]`, with the image's long side scaled to 100 and its centre at 0,0 (Leaflet opens on 0,0 whatever `lat` and `long` say). A point x pixels from the left and y from the top is lat `H/2 - y·k`, long `x·k - W/2`, where k = 100 / long side.
- **Markers go in ONE list**, never repeated `marker:` lines (Leaflet's YAML reader fails on repeated keys and the map turns grey):
  ```
  marker:
    - "city, 12.5, -30.2, [[Port Wren]]"
  ```
- Marker types: city, district, building, landmark, region, danger, party. Leaflet's icons are Font Awesome 5: check a new icon name exists in the plugin's `main.js` before adding a type, or the plugin crashes on load.
- Edit Leaflet's `data.json` only while Obsidian is closed; it overwrites the file on reload.
- Markers are placed by hand and stored by the plugin. Never use Leaflet's `markerFolder` or `markerTag`: they read the `location` property as coordinates, and here it is a link.
- Never touch `.obsidian/` unless Tom asks.
