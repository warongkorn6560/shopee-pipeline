#!/usr/bin/env bash
# 10-second test render to validate end-to-end JSON2Video pipeline cheaply.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

PAYLOAD=$(python3 <<'PY'
import json
print(json.dumps({
  "resolution": "instagram-story",
  "quality": "high",
  "scenes": [
    {
      "comment": "hook",
      "duration": 3,
      "elements": [
        {"type":"video","src":"https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4","fit":"cover","duration":3},
        {"type":"text","text":"สุนัขกัดของเล่นพังบ่อยไหม","x":540,"y":768,"width":864,"font-family":"Noto Sans Thai","font-size":72,"font-weight":"bold","color":"#FFFFFF","background":"#000000AA","text-align":"center","duration":3}
      ]
    },
    {
      "comment":"body","duration":4,
      "elements":[
        {"type":"video","src":"https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4","fit":"cover","duration":4},
        {"type":"voice","text":"ของเล่นยางกัด ทนทาน ราคาเก้าสิบเก้าบาท","voice":"th-TH-PremwadeeNeural","model":"azure"}
      ]
    },
    {
      "comment":"cta","duration":3,"background-color":"#EE4D2D",
      "elements":[
        {"type":"text","text":"คลิกลิงก์ใต้คลิป Shopee","x":540,"y":864,"width":920,"font-family":"Noto Sans Thai","font-size":88,"font-weight":"bold","color":"#FFFFFF","text-align":"center"},
        {"type":"text","text":"@flickfixsummaries","x":540,"y":1440,"width":920,"font-family":"Noto Sans Thai","font-size":48,"color":"#FFFFFF","text-align":"center"}
      ]
    }
  ]
}, ensure_ascii=False))
PY
)

echo "--- submit 10-sec render ---"
RESP=$(curl -sS -X POST "https://api.json2video.com/v2/movies" \
  -H "x-api-key: $JSON2VIDEO_API_KEY" -H "Content-Type: application/json" -d "$PAYLOAD")
PROJECT=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('project',''))")
[[ -z "$PROJECT" ]] && { echo "submit failed: $RESP"; exit 1; }
echo "project=$PROJECT"
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 15
  RESP=$(curl -sS -H "x-api-key: $JSON2VIDEO_API_KEY" "https://api.json2video.com/v2/movies?project=$PROJECT")
  LINE=$(echo "$RESP" | python3 -c "import json,sys;m=json.load(sys.stdin).get('movie',{});print(m.get('status'),'|',m.get('url','-'),'|',m.get('message',''))")
  echo "[t+${i}5s] $LINE"
  if echo "$LINE" | grep -qE "^(done|error)"; then
    echo ""
    echo "$RESP" | python3 -m json.tool
    break
  fi
done
