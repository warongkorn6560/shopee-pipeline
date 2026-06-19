#!/usr/bin/env bash
# Submit one test render directly to JSON2Video, bypassing Make.
# Proves the video payload is valid before burning Make ops.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

SCRIPT_TH="ของเล่นยางกัดได้สำหรับสุนัข เสียงน่ารัก ทนทาน ราคา 99 บาท ช่วยให้น้องหมามีของเล่นที่ปลอดภัย ทำจากยางเกรดดี ไม่หลุดเป็นเม็ดโฟม กดลิงก์ในไบโอ ค้นหาโค้ดในร้าน Shopee ของฉัน"
HOOK_TH="สุนัขกัดของเล่นพังบ่อยไหม"

PAYLOAD=$(python3 <<PY
import json
print(json.dumps({
  "resolution": "instagram-story",
  "quality": "high",
  "scenes": [
    {
      "comment": "hook",
      "duration": 3,
      "elements": [
        {"type":"video","src":"https://videos.pexels.com/video-files/5876708/5876708-uhd_2160_3840_30fps.mp4","fit":"cover","duration":3},
        {"type":"text","text":"$HOOK_TH","x":540,"y":768,"width":864,"font-family":"Noto Sans Thai","font-size":72,"font-weight":"bold","color":"#FFFFFF","background":"#000000AA","text-align":"center","duration":3}
      ]
    },
    {
      "comment":"body","duration":47,
      "elements":[
        {"type":"video","src":"https://videos.pexels.com/video-files/5876708/5876708-uhd_2160_3840_30fps.mp4","fit":"cover","duration":47},
        {"type":"voice","text":"$SCRIPT_TH","voice":"th-TH-PremwadeeNeural","model":"azure"}
      ]
    },
    {
      "comment":"cta","duration":5,"background-color":"#EE4D2D",
      "elements":[
        {"type":"text","text":"คลิกลิงก์ใต้คลิป Shopee","x":540,"y":864,"width":920,"font-family":"Noto Sans Thai","font-size":88,"font-weight":"bold","color":"#FFFFFF","text-align":"center"},
        {"type":"text","text":"@flickfixsummaries","x":540,"y":1440,"width":920,"font-family":"Noto Sans Thai","font-size":48,"color":"#FFFFFF","text-align":"center"}
      ]
    }
  ]
}, ensure_ascii=False))
PY
)

echo "--- submitting render ---"
RESP=$(curl -sS -X POST "https://api.json2video.com/v2/movies" \
  -H "x-api-key: $JSON2VIDEO_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")
echo "$RESP" | python3 -m json.tool
PROJECT=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('project',''))")
if [[ -z "$PROJECT" ]]; then echo "FAILED to submit"; exit 1; fi
echo ""
echo "--- polling status (project=$PROJECT) ---"
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 15
  RESP=$(curl -sS -H "x-api-key: $JSON2VIDEO_API_KEY" "https://api.json2video.com/v2/movies?project=$PROJECT")
  STATUS=$(echo "$RESP" | python3 -c "import json,sys;m=json.load(sys.stdin).get('movie',{});print(m.get('status','?'),'|',m.get('url','-'),'|',m.get('message',''))")
  echo "[t+${i}5s] $STATUS"
  if echo "$STATUS" | grep -qE "^(done|error)"; then
    echo ""
    echo "--- final ---"
    echo "$RESP" | python3 -m json.tool
    break
  fi
done
